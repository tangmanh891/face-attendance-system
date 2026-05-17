"""Router quản lý nhân viên (CRUD)."""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserFaceUpdate,
    UserList,
    UserResponse,
    UserUpdate,
)
from app.security import require_admin_token
from app.services.face_service import get_face_service
from app.utils.image_utils import save_base64_image, validate_image

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_admin_token)])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Đăng ký nhân viên mới với ảnh khuôn mặt (tuỳ chọn)."""
    # Kiểm tra employee_id đã tồn tại chưa
    existing = await db.execute(
        select(User).where(User.employee_id == user_data.employee_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã nhân viên '{user_data.employee_id}' đã tồn tại",
        )

    # Kiểm tra email đã tồn tại chưa
    if user_data.email:
        existing_email = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if existing_email.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{user_data.email}' đã được sử dụng",
            )

    face_embedding = None
    face_image_path = None

    # Xử lý ảnh khuôn mặt nếu có
    if user_data.face_image_base64:
        is_valid, error_msg = validate_image(user_data.face_image_base64)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ảnh không hợp lệ: {error_msg}",
            )

        face_image_path, image = save_base64_image(
            user_data.face_image_base64,
            subfolder="faces",
            filename=f"{user_data.employee_id}.jpg",
        )

        face_service = get_face_service()
        embedding = face_service.get_embedding(image)
        if embedding is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không tìm thấy khuôn mặt trong ảnh. Vui lòng chụp rõ mặt.",
            )
        face_embedding = embedding.tolist()

    # Tạo nhân viên mới
    user = User(
        employee_id=user_data.employee_id,
        full_name=user_data.full_name,
        email=user_data.email,
        department=user_data.department,
        position=user_data.position,
        face_embedding=face_embedding,
        face_image_path=face_image_path,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info(f"Đã tạo nhân viên mới: {user.employee_id} - {user.full_name}")
    return _to_response(user)


@router.get("/", response_model=UserList)
async def list_users(
    page: int = Query(1, ge=1, description="Số trang"),
    size: int = Query(20, ge=1, le=100, description="Số bản ghi mỗi trang"),
    search: str | None = Query(None, description="Tìm kiếm theo tên/mã NV"),
    department: str | None = Query(None, description="Lọc theo phòng ban"),
    is_active: bool | None = Query(None, description="Lọc theo trạng thái"),
    db: AsyncSession = Depends(get_db),
):
    """Lấy danh sách nhân viên có phân trang và bộ lọc."""
    query = select(User)

    if search:
        query = query.where(
            (User.full_name.ilike(f"%{search}%"))
            | (User.employee_id.ilike(f"%{search}%"))
        )
    if department:
        query = query.where(User.department == department)
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # Đếm tổng
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    # Lấy dữ liệu phân trang
    query = query.offset((page - 1) * size).limit(size).order_by(User.created_at.desc())
    result = await db.execute(query)
    users = result.scalars().all()

    pages = (total + size - 1) // size if total > 0 else 0

    return UserList(
        items=[_to_response(u) for u in users],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Lấy thông tin một nhân viên theo ID."""
    user = await _get_user_or_404(db, user_id)
    return _to_response(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Cập nhật thông tin nhân viên."""
    user = await _get_user_or_404(db, user_id)

    update_data = user_data.model_dump(exclude_unset=True)

    # Kiểm tra email trùng khi update
    if "email" in update_data and update_data["email"] is not None:
        existing_email = await db.execute(
            select(User).where(
                User.email == update_data["email"],
                User.id != user_id,
            )
        )
        if existing_email.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{update_data['email']}' đã được sử dụng",
            )

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)

    logger.info(f"Đã cập nhật nhân viên: {user.employee_id}")
    return _to_response(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Xoá nhân viên (soft delete - set is_active=False)."""
    user = await _get_user_or_404(db, user_id)
    user.is_active = False
    await db.flush()

    logger.info(f"Đã xoá nhân viên: {user.employee_id}")


@router.put("/{user_id}/face", response_model=UserResponse)
async def update_user_face(
    user_id: uuid.UUID,
    face_data: UserFaceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Cập nhật ảnh khuôn mặt và embedding cho nhân viên."""
    user = await _get_user_or_404(db, user_id)

    # Validate ảnh
    is_valid, error_msg = validate_image(face_data.face_image_base64)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ảnh không hợp lệ: {error_msg}",
        )

    # Lưu ảnh và trích xuất embedding
    face_image_path, image = save_base64_image(
        face_data.face_image_base64,
        subfolder="faces",
        filename=f"{user.employee_id}.jpg",
    )

    face_service = get_face_service()
    embedding = face_service.get_embedding(image)
    if embedding is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không tìm thấy khuôn mặt trong ảnh",
        )

    user.face_embedding = embedding.tolist()
    user.face_image_path = face_image_path

    await db.flush()
    await db.refresh(user)

    logger.info(f"Đã cập nhật face embedding cho nhân viên: {user.employee_id}")
    return _to_response(user)


async def _get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Lấy nhân viên theo ID hoặc trả về 404."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy nhân viên với ID: {user_id}",
        )
    return user


def _to_response(user: User) -> UserResponse:
    """Chuyển đổi User model sang UserResponse schema."""
    # Chỉ trả về URL tương đối, không leak đường dẫn file system
    face_url = None
    if user.face_image_path:
        face_url = f"/uploads/{'/'.join(user.face_image_path.replace(chr(92), '/').split('/')[-2:])}"

    return UserResponse(
        id=user.id,
        employee_id=user.employee_id,
        full_name=user.full_name,
        email=user.email,
        department=user.department,
        position=user.position,
        is_active=user.is_active,
        face_image_path=face_url,
        has_face_embedding=user.face_embedding is not None,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )

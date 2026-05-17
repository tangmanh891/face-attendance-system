"""Router điểm danh - check-in, check-out, lịch sử, thống kê."""
import csv
import io
import logging
import uuid
from datetime import date, timedelta

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.attendance import Attendance, AttendanceStatus
from app.models.user import User
from app.schemas.attendance import (
    AttendanceCheckOut,
    AttendanceCreate,
    AttendanceResponse,
    AttendanceStats,
    RecognitionResult,
)
from app.security import optional_admin_token, require_admin_token
from app.services.attendance_service import AttendanceService, _today
from app.services.face_service import get_face_service
from app.utils.image_utils import decode_base64_image, save_base64_image, validate_image

logger = logging.getLogger(__name__)
router = APIRouter()


def _sanitize_path(path: str | None) -> str | None:
    """Chuyển đường dẫn file system thành URL tương đối."""
    if not path:
        return None
    parts = path.replace("\\", "/").split("/")
    # Lấy 2 phần cuối: subfolder/filename
    return f"/uploads/{'/'.join(parts[-2:])}" if len(parts) >= 2 else None


@router.post("/check-in", response_model=RecognitionResult)
async def check_in(
    data: AttendanceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Thực hiện check-in bằng nhận diện khuôn mặt."""
    # Validate ảnh
    is_valid, error_msg = validate_image(data.image_base64)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ảnh không hợp lệ: {error_msg}",
        )

    # Giải mã ảnh
    image = decode_base64_image(data.image_base64)

    # Lấy tất cả embedding nhân viên active
    result = await db.execute(
        select(User).where(
            User.is_active == True,  # noqa: E712
            User.face_embedding.is_not(None),
        )
    )
    users = result.scalars().all()

    if not users:
        return RecognitionResult(
            success=False,
            message="Chưa có nhân viên nào đăng ký khuôn mặt",
        )

    known_embeddings = {
        str(u.id): np.array(u.face_embedding, dtype=np.float32)
        for u in users
    }

    # Nhận diện khuôn mặt
    face_service = get_face_service()
    match = face_service.recognize_face(
        image,
        known_embeddings,
        threshold=settings.face_recognition_threshold,
    )

    if not match:
        return RecognitionResult(
            success=False,
            message="Không nhận diện được khuôn mặt. Độ tin cậy quá thấp.",
        )

    # Tìm thông tin nhân viên
    user = next((u for u in users if str(u.id) == match["user_id"]), None)
    if not user:
        return RecognitionResult(success=False, message="Không tìm thấy nhân viên")

    # Lưu ảnh check-in
    captured_path, _ = save_base64_image(data.image_base64, subfolder="checkins")

    # Thực hiện check-in
    attendance_service = AttendanceService(db)
    try:
        attendance = await attendance_service.check_in(
            user_id=user.id,
            confidence_score=match["confidence"],
            captured_image_path=captured_path,
            notes=data.notes,
        )
        return RecognitionResult(
            success=True,
            user_id=user.id,
            employee_id=user.employee_id,
            full_name=user.full_name,
            confidence=match["confidence"],
            message=f"Check-in thành công! Xin chào {user.full_name}",
            attendance_id=attendance.id,
            already_checked_in=False,
        )
    except ValueError as e:
        error_msg = str(e)
        if "đã check-in" in error_msg.lower() or "cooldown" in error_msg.lower():
            return RecognitionResult(
                success=True,
                user_id=user.id,
                employee_id=user.employee_id,
                full_name=user.full_name,
                confidence=match["confidence"],
                message=error_msg,
                already_checked_in=True,
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg) from None
    except IntegrityError:
        return RecognitionResult(
            success=True,
            user_id=user.id,
            employee_id=user.employee_id,
            full_name=user.full_name,
            confidence=match["confidence"],
            message="Nhân viên đã check-in hôm nay rồi.",
            already_checked_in=True,
        )


@router.post("/check-out", response_model=RecognitionResult)
async def check_out(
    data: AttendanceCheckOut,
    admin_token: str | None = Depends(optional_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Thực hiện check-out.

    Nhân viên tự check-out bằng ảnh khuôn mặt. Check-out thủ công bằng user_id
    cần admin token để tránh giả mạo từ client.
    """
    user_id = data.user_id
    captured_path = None
    confidence = None

    if data.image_base64:
        is_valid, error_msg = validate_image(data.image_base64)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ảnh không hợp lệ: {error_msg}",
            )

        image = decode_base64_image(data.image_base64)

        result = await db.execute(
            select(User).where(
                User.is_active == True,  # noqa: E712
                User.face_embedding.is_not(None),
            )
        )
        users = result.scalars().all()
        known_embeddings = {
            str(u.id): np.array(u.face_embedding, dtype=np.float32)
            for u in users
        }

        face_service = get_face_service()
        match = face_service.recognize_face(
            image,
            known_embeddings,
            threshold=settings.face_recognition_threshold,
        )
        if not match:
            return RecognitionResult(
                success=False,
                message="Không nhận diện được khuôn mặt",
            )

        recognized_user_id = uuid.UUID(match["user_id"])
        if user_id and user_id != recognized_user_id:
            return RecognitionResult(
                success=False,
                message="Khuôn mặt không khớp với nhân viên được chọn",
            )
        user_id = recognized_user_id
        confidence = match["confidence"]

        captured_path, _ = save_base64_image(data.image_base64, subfolder="checkouts")
    elif not admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Check-out bằng user_id cần admin token hoặc ảnh khuôn mặt",
        )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cần cung cấp ảnh khuôn mặt hoặc user_id cho admin check-out",
        )

    # Lấy thông tin nhân viên
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy nhân viên",
        )

    attendance_service = AttendanceService(db)
    try:
        attendance = await attendance_service.check_out(
            user_id=user_id,
            captured_image_path=captured_path,
        )
        return RecognitionResult(
            success=True,
            user_id=user.id,
            employee_id=user.employee_id,
            full_name=user.full_name,
            confidence=confidence,
            message=f"Check-out thành công! Tạm biệt {user.full_name}",
            attendance_id=attendance.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None


@router.get("/today", response_model=list[AttendanceResponse])
async def get_today_attendance(db: AsyncSession = Depends(get_db)):
    """Lấy danh sách điểm danh hôm nay."""
    attendance_service = AttendanceService(db)
    records = await attendance_service.get_today_attendance()
    return [AttendanceResponse(**r) for r in records]


@router.get("/history", response_model=list[AttendanceResponse])
async def get_attendance_history(
    start_date: date | None = Query(None, description="Ngày bắt đầu"),
    end_date: date | None = Query(None, description="Ngày kết thúc"),
    department: str | None = Query(None, description="Phòng ban"),
    status_filter: AttendanceStatus | None = Query(None, alias="status", description="Trạng thái"),
    user_id: uuid.UUID | None = Query(None, description="ID nhân viên"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    _: str = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Lấy lịch sử điểm danh với bộ lọc."""
    # Mặc định: 30 ngày gần nhất
    if not end_date:
        end_date = _today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày bắt đầu phải trước ngày kết thúc",
        )

    query = (
        select(Attendance, User)
        .join(User, Attendance.user_id == User.id)
        .where(Attendance.date.between(start_date, end_date))
    )

    if department:
        query = query.where(User.department == department)
    if status_filter:
        query = query.where(Attendance.status == status_filter)
    if user_id:
        query = query.where(Attendance.user_id == user_id)

    query = query.order_by(Attendance.date.desc(), Attendance.check_in_time.desc())
    query = query.offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    records = []
    for attendance, user in result.all():
        records.append(AttendanceResponse(
            id=attendance.id,
            user_id=attendance.user_id,
            employee_id=user.employee_id,
            full_name=user.full_name,
            department=user.department,
            check_in_time=attendance.check_in_time,
            check_out_time=attendance.check_out_time,
            confidence_score=attendance.confidence_score,
            status=attendance.status,
            date=attendance.date,
            notes=attendance.notes,
            captured_image_path=_sanitize_path(attendance.captured_image_path),
            created_at=attendance.created_at,
        ))
    return records


@router.get("/stats", response_model=AttendanceStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Lấy thống kê điểm danh tổng quan."""
    attendance_service = AttendanceService(db)
    return await attendance_service.get_attendance_stats()


@router.get("/export")
async def export_attendance(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    department: str | None = Query(None),
    _: str = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Xuất dữ liệu điểm danh ra file CSV."""
    if not end_date:
        end_date = _today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày bắt đầu phải trước ngày kết thúc",
        )

    query = (
        select(Attendance, User)
        .join(User, Attendance.user_id == User.id)
        .where(Attendance.date.between(start_date, end_date))
    )
    if department:
        query = query.where(User.department == department)
    query = query.order_by(Attendance.date.desc())

    result = await db.execute(query)
    rows = result.all()

    # Tạo CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Ngày", "Mã NV", "Họ tên", "Phòng ban",
        "Giờ vào", "Giờ ra", "Trạng thái", "Độ tin cậy"
    ])

    for attendance, user in rows:
        writer.writerow([
            attendance.date.isoformat(),
            user.employee_id,
            user.full_name,
            user.department or "",
            attendance.check_in_time.strftime("%H:%M:%S") if attendance.check_in_time else "",
            attendance.check_out_time.strftime("%H:%M:%S") if attendance.check_out_time else "",
            attendance.status.value,
            f"{attendance.confidence_score:.3f}" if attendance.confidence_score else "",
        ])

    output.seek(0)
    filename = f"attendance_{start_date.isoformat()}_{end_date.isoformat()}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

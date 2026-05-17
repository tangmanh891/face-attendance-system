"""Pydantic schemas cho User (Nhân viên)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base schema chứa các trường chung."""

    employee_id: str = Field(..., min_length=1, max_length=50, description="Mã nhân viên")
    full_name: str = Field(..., min_length=1, max_length=255, description="Họ và tên")
    email: EmailStr | None = Field(None, description="Email")
    department: str | None = Field(None, max_length=100, description="Phòng ban")
    position: str | None = Field(None, max_length=100, description="Chức vụ")


class UserCreate(UserBase):
    """Schema để tạo nhân viên mới."""

    face_image_base64: str | None = Field(
        None, description="Ảnh khuôn mặt dạng base64"
    )


class UserUpdate(BaseModel):
    """Schema để cập nhật thông tin nhân viên."""

    full_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    department: str | None = Field(None, max_length=100)
    position: str | None = Field(None, max_length=100)
    is_active: bool | None = None


class UserFaceUpdate(BaseModel):
    """Schema để cập nhật ảnh khuôn mặt."""

    face_image_base64: str = Field(..., description="Ảnh khuôn mặt dạng base64")


class UserResponse(UserBase):
    """Schema trả về thông tin nhân viên."""

    id: uuid.UUID
    is_active: bool
    face_image_path: str | None = None
    has_face_embedding: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Override để tính toán has_face_embedding."""
        instance = super().model_validate(obj, **kwargs)
        if hasattr(obj, "face_embedding"):
            instance.has_face_embedding = obj.face_embedding is not None
        return instance


class UserList(BaseModel):
    """Schema danh sách nhân viên có phân trang."""

    items: list[UserResponse]
    total: int
    page: int
    size: int
    pages: int

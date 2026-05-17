"""Pydantic schemas cho Attendance (Điểm danh)."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.attendance import AttendanceStatus


class AttendanceBase(BaseModel):
    """Base schema cho điểm danh."""

    user_id: uuid.UUID
    date: date
    status: AttendanceStatus = AttendanceStatus.ON_TIME


class AttendanceCreate(BaseModel):
    """Schema để tạo bản ghi điểm danh (check-in qua nhận diện khuôn mặt)."""

    image_base64: str = Field(..., description="Ảnh khuôn mặt dạng base64")
    notes: str | None = Field(None, max_length=500)


class AttendanceCheckOut(BaseModel):
    """Schema để check-out."""

    image_base64: str | None = Field(None, description="Ảnh khuôn mặt khi check-out")
    user_id: uuid.UUID | None = Field(None, description="ID nhân viên (nếu biết)")


class AttendanceResponse(BaseModel):
    """Schema trả về thông tin điểm danh."""

    id: uuid.UUID
    user_id: uuid.UUID
    employee_id: str
    full_name: str
    department: str | None = None
    check_in_time: datetime | None = None
    check_out_time: datetime | None = None
    confidence_score: float | None = None
    status: AttendanceStatus
    date: date
    notes: str | None = None
    captured_image_path: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AttendanceStats(BaseModel):
    """Schema thống kê điểm danh."""

    total_employees: int
    present_today: int
    late_today: int
    absent_today: int
    on_time_rate: float
    weekly_data: list[dict]
    monthly_data: list[dict]


class RecognitionResult(BaseModel):
    """Kết quả nhận diện khuôn mặt."""

    success: bool
    user_id: uuid.UUID | None = None
    employee_id: str | None = None
    full_name: str | None = None
    confidence: float | None = None
    message: str
    attendance_id: uuid.UUID | None = None
    already_checked_in: bool = False

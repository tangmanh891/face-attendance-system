"""SQLAlchemy model cho Attendance (Điểm danh)."""
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AttendanceStatus(str, enum.Enum):
    """Trạng thái điểm danh."""

    ON_TIME = "ON_TIME"       # Đúng giờ
    LATE = "LATE"             # Đi muộn
    ABSENT = "ABSENT"         # Vắng mặt
    EARLY_LEAVE = "EARLY_LEAVE"  # Về sớm


class Attendance(Base):
    """Model điểm danh nhân viên."""

    __tablename__ = "attendances"

    # Khoá chính
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Khoá ngoại
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Thời gian điểm danh
    check_in_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Thời gian check-in"
    )
    check_out_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Thời gian check-out"
    )

    # Thông tin nhận diện
    confidence_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Điểm tin cậy nhận diện khuôn mặt"
    )
    captured_image_path: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Đường dẫn ảnh chụp lúc điểm danh"
    )

    # Trạng thái và ngày
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus),
        default=AttendanceStatus.ON_TIME,
        nullable=False,
    )
    date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True, comment="Ngày điểm danh"
    )

    # Ghi chú
    notes: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Ghi chú bổ sung"
    )

    # Thời gian tạo
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Quan hệ
    user: Mapped["User"] = relationship("User", back_populates="attendances")  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return f"<Attendance user={self.user_id} date={self.date} status={self.status}>"

"""SQLAlchemy model cho User (Nhân viên)."""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """Model nhân viên với face embedding vector 512 chiều."""

    __tablename__ = "users"

    # Khoá chính
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Thông tin nhân viên
    employee_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Dữ liệu khuôn mặt
    face_embedding: Mapped[list | None] = mapped_column(
        Vector(512), nullable=True, comment="ArcFace embedding vector 512 chiều"
    )
    face_image_path: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Đường dẫn ảnh khuôn mặt đã lưu"
    )

    # Trạng thái
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Thời gian
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Quan hệ
    attendances: Mapped[list["Attendance"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Attendance", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.employee_id}: {self.full_name}>"

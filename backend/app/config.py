"""Cấu hình ứng dụng sử dụng pydantic-settings."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cài đặt ứng dụng được load từ biến môi trường."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Thông tin ứng dụng
    app_name: str = "Face Attendance System"
    app_version: str = "1.0.0"
    debug: bool = False

    # Cơ sở dữ liệu
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/face_attendance"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Cài đặt mô hình AI
    insightface_model: str = "buffalo_l"
    insightface_det_thresh: float = 0.5
    face_recognition_threshold: float = 0.4
    max_face_image_size_mb: int = 5

    # Cài đặt điểm danh
    work_start_time: str = "08:00"
    work_end_time: str = "17:00"
    late_threshold_minutes: int = 15
    checkin_cooldown_minutes: int = 5
    timezone: str = "Asia/Ho_Chi_Minh"

    # Cài đặt file
    upload_dir: str = "uploads"
    max_image_size: int = 1024  # pixels

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Bảo vệ API demo/portfolio
    admin_api_key: str = "dev-admin-token"
    camera_stream_token: str | None = None

    # JWT (tuỳ chọn, cho xác thực admin nâng cao)
    secret_key: str = "change-this-secret-key-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Redis (tuỳ chọn, cache embedding)
    redis_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Trả về instance Settings đã được cache."""
    return Settings()


settings = get_settings()

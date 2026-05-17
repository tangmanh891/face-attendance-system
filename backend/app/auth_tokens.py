"""Hàm kiểm tra token thuần Python, dùng lại cho API và tests."""
import secrets

from app.config import settings


def is_admin_token(token: str | None) -> bool:
    """Kiểm tra token quản trị."""
    if not token or not settings.admin_api_key:
        return False
    return secrets.compare_digest(token, settings.admin_api_key)


def is_camera_token(token: str | None) -> bool:
    """Kiểm tra token camera, fallback sang admin token nếu chưa cấu hình riêng."""
    expected = settings.camera_stream_token or settings.admin_api_key
    if not token or not expected:
        return False
    return secrets.compare_digest(token, expected)

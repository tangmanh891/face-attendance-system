"""Tests cho bảo vệ token và validation ảnh."""
import base64

import cv2
import numpy as np

from app.config import settings
from app.auth_tokens import is_admin_token, is_camera_token
from app.utils.image_utils import validate_image


def test_invalid_base64_returns_validation_error():
    """Base64 sai định dạng phải trả lỗi validation, không rơi vào exception 500."""
    is_valid, error = validate_image("not-valid-base64")

    assert is_valid is False
    assert "base64" in error.lower()


def test_valid_base64_image_still_passes_validation():
    """Ảnh JPEG hợp lệ vẫn được chấp nhận sau khi bật validate=True."""
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok is True

    image_base64 = base64.b64encode(buffer).decode("utf-8")
    is_valid, error = validate_image(image_base64)

    assert is_valid is True
    assert error == ""


def test_admin_token_matches_config(monkeypatch):
    """Admin token chỉ hợp lệ khi khớp cấu hình."""
    monkeypatch.setattr(settings, "admin_api_key", "secret-token")

    assert is_admin_token("secret-token") is True
    assert is_admin_token("wrong-token") is False
    assert is_admin_token(None) is False


def test_camera_token_can_be_separate_from_admin(monkeypatch):
    """Camera stream token có thể tách riêng khỏi admin token."""
    monkeypatch.setattr(settings, "admin_api_key", "admin-token")
    monkeypatch.setattr(settings, "camera_stream_token", "camera-token")

    assert is_camera_token("camera-token") is True
    assert is_camera_token("admin-token") is False

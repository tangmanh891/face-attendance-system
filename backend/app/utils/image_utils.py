"""Tiện ích xử lý ảnh - encode/decode base64, validation, resize, lưu file."""
import base64
import binascii
import logging
import uuid
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)


def _strip_data_url(image_base64: str) -> str:
    """Bỏ data URL prefix nếu client gửi kèm."""
    if "," in image_base64:
        return image_base64.split(",", 1)[1]
    return image_base64


def decode_base64_image(image_base64: str) -> np.ndarray:
    """Giải mã ảnh từ chuỗi base64 sang numpy array (BGR)."""
    try:
        # Xử lý data URL prefix (ví dụ: data:image/jpeg;base64,...)
        image_base64 = _strip_data_url(image_base64)

        # Giải mã base64
        image_bytes = base64.b64decode(image_base64, validate=True)
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Không thể giải mã ảnh từ base64")

        return image
    except Exception as e:
        logger.error(f"Lỗi giải mã base64: {e}")
        raise ValueError(f"Ảnh base64 không hợp lệ: {e}") from e


def encode_image_to_base64(image: np.ndarray, format: str = "JPEG") -> str:
    """Mã hoá numpy array sang chuỗi base64."""
    _, buffer = cv2.imencode(f".{format.lower()}", image)
    return base64.b64encode(buffer).decode("utf-8")


def validate_image(image_base64: str, max_size_mb: int = 5) -> tuple[bool, str]:
    """Kiểm tra tính hợp lệ của ảnh.

    Returns:
        Tuple (is_valid, error_message)
    """
    # Kiểm tra kích thước base64
    data = _strip_data_url(image_base64)
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as e:
        return False, f"Ảnh base64 không hợp lệ: {e}"

    size_bytes = len(raw)
    max_bytes = max_size_mb * 1024 * 1024

    if size_bytes > max_bytes:
        return False, f"Kích thước ảnh vượt quá {max_size_mb}MB"

    # Kiểm tra có thể decode không
    try:
        image = decode_base64_image(image_base64)
        h, w = image.shape[:2]
        if h < 50 or w < 50:
            return False, "Ảnh quá nhỏ (tối thiểu 50x50 pixels)"
        if h > 4096 or w > 4096:
            return False, "Ảnh quá lớn (tối đa 4096x4096 pixels)"
        return True, ""
    except ValueError as e:
        return False, str(e)


def resize_image(
    image: np.ndarray, max_size: int = 1024
) -> np.ndarray:
    """Resize ảnh nếu lớn hơn max_size, giữ tỷ lệ khung hình."""
    h, w = image.shape[:2]
    if h <= max_size and w <= max_size:
        return image

    if h > w:
        new_h = max_size
        new_w = int(w * max_size / h)
    else:
        new_w = max_size
        new_h = int(h * max_size / w)

    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def save_image(
    image: np.ndarray,
    subfolder: str = "faces",
    filename: str | None = None,
) -> str:
    """Lưu ảnh vào thư mục upload và trả về đường dẫn tương đối."""
    upload_dir = Path(settings.upload_dir) / subfolder
    upload_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        filename = f"{uuid.uuid4()}.jpg"

    file_path = upload_dir / filename
    cv2.imwrite(str(file_path), image)

    return str(file_path)


def save_base64_image(
    image_base64: str,
    subfolder: str = "faces",
    filename: str | None = None,
) -> tuple[str, np.ndarray]:
    """Giải mã base64 và lưu ảnh, trả về (đường dẫn, numpy array)."""
    image = decode_base64_image(image_base64)
    image = resize_image(image, settings.max_image_size)
    path = save_image(image, subfolder, filename)
    return path, image


def pil_to_cv2(pil_image: Image.Image) -> np.ndarray:
    """Chuyển đổi PIL Image sang OpenCV numpy array (BGR)."""
    rgb = np.array(pil_image)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def cv2_to_pil(cv2_image: np.ndarray) -> Image.Image:
    """Chuyển đổi OpenCV numpy array sang PIL Image."""
    rgb = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def draw_face_boxes(
    image: np.ndarray,
    faces: list,
    color: tuple[int, int, int] = (0, 255, 0),
) -> np.ndarray:
    """Vẽ bounding box và nhãn lên ảnh."""
    result = image.copy()
    for face in faces:
        bbox = face.get("bbox", [])
        if len(bbox) == 4:
            x1, y1, x2, y2 = [int(v) for v in bbox]
            cv2.rectangle(result, (x1, y1), (x2, y2), color, 2)

            label = face.get("name", "Unknown")
            confidence = face.get("confidence", 0)
            text = f"{label} ({confidence:.2f})"
            cv2.putText(
                result, text, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
            )
    return result

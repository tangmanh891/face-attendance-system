"""Router nhận diện khuôn mặt - detect, identify, WebSocket streaming."""
import asyncio
import json
import logging
import time
import uuid
from datetime import timedelta
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.models.user import User
from app.schemas.attendance import RecognitionResult
from app.auth_tokens import is_camera_token
from app.security import require_admin_token
from app.services.attendance_service import AttendanceService, _checkin_cooldown, _now
from app.services.face_service import get_face_service
from app.utils.image_utils import decode_base64_image, validate_image

logger = logging.getLogger(__name__)
router = APIRouter()


class DetectRequest(BaseModel):
    """Request để phát hiện khuôn mặt."""

    image_base64: str


class IdentifyRequest(BaseModel):
    """Request để nhận diện khuôn mặt."""

    image_base64: str


@router.post("/detect")
async def detect_faces(data: DetectRequest):
    """Phát hiện khuôn mặt trong ảnh và trả về bounding boxes."""
    is_valid, error_msg = validate_image(data.image_base64)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ảnh không hợp lệ: {error_msg}",
        )

    image = decode_base64_image(data.image_base64)
    face_service = get_face_service()
    faces = face_service.detect_faces(image)

    return {
        "face_count": len(faces),
        "faces": [
            {
                "bbox": face["bbox"],
                "det_score": face["det_score"],
                "landmarks": face.get("landmarks", []),
            }
            for face in faces
        ],
    }


@router.post("/identify", response_model=RecognitionResult)
async def identify_face(
    data: IdentifyRequest,
    _: str = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Nhận diện khuôn mặt mà không check-in."""
    is_valid, error_msg = validate_image(data.image_base64)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ảnh không hợp lệ: {error_msg}",
        )

    image = decode_base64_image(data.image_base64)

    # Lấy tất cả embeddings
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

    face_service = get_face_service()
    match = face_service.recognize_face(
        image, known_embeddings,
        threshold=settings.face_recognition_threshold,
    )

    if not match:
        return RecognitionResult(
            success=False,
            message="Không nhận diện được khuôn mặt",
        )

    user = next((u for u in users if str(u.id) == match["user_id"]), None)
    if not user:
        return RecognitionResult(success=False, message="Không tìm thấy nhân viên")

    return RecognitionResult(
        success=True,
        user_id=user.id,
        employee_id=user.employee_id,
        full_name=user.full_name,
        confidence=match["confidence"],
        message=f"Nhận diện thành công: {user.full_name}",
    )


@router.websocket("/stream")
async def websocket_stream(websocket: WebSocket):
    """WebSocket endpoint cho nhận diện khuôn mặt real-time.

    Flow:
    1. Client gửi frame base64 JPEG mỗi ~100ms
    2. Server phát hiện và nhận diện khuôn mặt
    3. Server trả về JSON với faces, fps, face_count
    4. Tự động check-in khi confidence > threshold
    5. Cooldown: không check-in lại cùng người trong 5 phút
    """
    token = websocket.query_params.get("token")
    if not is_camera_token(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    logger.info("WebSocket kết nối mới")

    face_service = get_face_service()
    frame_count = 0
    start_time = time.time()

    # Cache embeddings để tránh query DB liên tục
    known_embeddings: dict[str, np.ndarray] = {}
    user_info: dict[str, Any] = {}
    last_cache_refresh = 0
    cache_ttl = 30  # Refresh cache mỗi 30 giây

    try:
        while True:
            # Nhận frame từ client
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            except TimeoutError:
                await websocket.send_json({"type": "ping"})
                continue

            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "JSON không hợp lệ"})
                continue

            # Xử lý các loại message
            if data.get("type") == "frame":
                image_base64 = data.get("image", "")

                # Tính FPS
                frame_count += 1
                elapsed = time.time() - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0

                # Refresh cache embedding nếu cần
                now = time.time()
                if now - last_cache_refresh > cache_ttl:
                    async with AsyncSessionLocal() as db:
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
                        user_info = {
                            str(u.id): {
                                "employee_id": u.employee_id,
                                "full_name": u.full_name,
                                "department": u.department,
                            }
                            for u in users
                        }
                    last_cache_refresh = now

                # Giải mã và xử lý frame
                try:
                    image = decode_base64_image(image_base64)
                    faces_raw = face_service.detect_faces(image)
                except Exception as e:
                    logger.warning(f"Lỗi xử lý frame: {e}")
                    await websocket.send_json({"type": "error", "message": "Lỗi xử lý frame"})
                    continue

                # Nhận diện từng khuôn mặt
                faces_result = []
                for face in faces_raw:
                    face_data = {
                        "bbox": face["bbox"],
                        "det_score": face["det_score"],
                        "user_id": None,
                        "employee_id": None,
                        "name": "Unknown",
                        "confidence": 0.0,
                        "checked_in": False,
                    }

                    if face.get("embedding") is not None and known_embeddings:
                        embedding = np.array(face["embedding"], dtype=np.float32)
                        norm = np.linalg.norm(embedding)
                        if norm > 0:
                            embedding = embedding / norm

                        # Tìm kết quả khớp tốt nhất
                        best_id = None
                        best_sim = -1.0
                        for uid, known_emb in known_embeddings.items():
                            sim = float(np.dot(embedding, known_emb))
                            if sim > best_sim:
                                best_sim = sim
                                best_id = uid

                        if best_id and best_sim >= settings.face_recognition_threshold:
                            info = user_info.get(best_id, {})
                            face_data.update({
                                "user_id": best_id,
                                "employee_id": info.get("employee_id"),
                                "name": info.get("full_name", "Unknown"),
                                "confidence": best_sim,
                            })

                            # Tự động check-in
                            last_checkin = _checkin_cooldown.get(best_id)
                            cooldown = timedelta(minutes=settings.checkin_cooldown_minutes)
                            if (
                                last_checkin is None
                                or _now() - last_checkin > cooldown
                            ):
                                try:
                                    async with AsyncSessionLocal() as auto_db:
                                        attendance_service = AttendanceService(auto_db)
                                        await attendance_service.check_in(
                                            user_id=uuid.UUID(best_id),
                                            confidence_score=best_sim,
                                        )
                                        await auto_db.commit()
                                    face_data["checked_in"] = True
                                    logger.info(
                                        f"Auto check-in: {info.get('full_name')} "
                                        f"(confidence={best_sim:.3f})"
                                    )
                                except Exception as e:
                                    logger.debug(f"Check-in không thực hiện được: {e}")

                    faces_result.append(face_data)

                # Gửi kết quả về client
                await websocket.send_json({
                    "type": "result",
                    "faces": faces_result,
                    "face_count": len(faces_result),
                    "fps": round(fps, 1),
                })

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WebSocket ngắt kết nối")
    except Exception as e:
        logger.error(f"Lỗi WebSocket: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": "Lỗi server nội bộ"})
        except (RuntimeError, ConnectionError):
            pass

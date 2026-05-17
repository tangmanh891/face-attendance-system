"""Face Service - Dịch vụ nhận diện khuôn mặt sử dụng InsightFace/ArcFace."""
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class FaceService:
    """Dịch vụ nhận diện khuôn mặt sử dụng InsightFace ArcFace model."""

    def __init__(
        self,
        model_name: str = "buffalo_l",
        det_thresh: float = 0.5,
    ) -> None:
        """Khởi tạo FaceService với InsightFace model.

        Args:
            model_name: Tên model InsightFace (mặc định: buffalo_l)
            det_thresh: Ngưỡng phát hiện khuôn mặt
        """
        self.model_name = model_name
        self.det_thresh = det_thresh
        self._app = None
        self._initialized = False

    def _initialize(self) -> None:
        """Lazy initialization - chỉ load model khi cần thiết."""
        if self._initialized:
            return

        try:
            import insightface  # noqa: F401
            from insightface.app import FaceAnalysis

            logger.info(f"Đang load InsightFace model: {self.model_name}")
            self._app = FaceAnalysis(
                name=self.model_name,
                providers=["CPUExecutionProvider"],
            )
            self._app.prepare(ctx_id=0, det_thresh=self.det_thresh)
            self._initialized = True
            logger.info("InsightFace model đã được load thành công")
        except ImportError:
            logger.warning(
                "InsightFace không được cài đặt. Sử dụng mock mode."
            )
            self._initialized = True
        except Exception as e:
            logger.error(f"Lỗi khi load InsightFace model: {e}")
            raise RuntimeError(f"Không thể load InsightFace model: {e}") from e

    @property
    def app(self):
        """Trả về InsightFace app, khởi tạo nếu chưa có."""
        if not self._initialized:
            self._initialize()
        return self._app

    def detect_faces(self, image: np.ndarray) -> list[dict]:
        """Phát hiện tất cả khuôn mặt trong ảnh.

        Args:
            image: Ảnh numpy array (BGR)

        Returns:
            Danh sách dict chứa thông tin từng khuôn mặt:
            - bbox: [x1, y1, x2, y2]
            - landmarks: 5 điểm landmark
            - det_score: Điểm tin cậy phát hiện
            - embedding: Vector embedding 512 chiều (nếu có)
        """
        if self.app is None:
            logger.warning("InsightFace không khả dụng, trả về danh sách rỗng")
            return []

        try:
            # Đảm bảo ảnh là RGB (InsightFace yêu cầu RGB)
            if len(image.shape) == 3 and image.shape[2] == 3:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                rgb_image = image

            faces = self.app.get(rgb_image)

            result = []
            for face in faces:
                face_dict = {
                    "bbox": face.bbox.tolist() if face.bbox is not None else [],
                    "landmarks": face.kps.tolist() if face.kps is not None else [],
                    "det_score": float(face.det_score) if face.det_score is not None else 0.0,
                    "embedding": face.embedding if face.embedding is not None else None,
                }
                result.append(face_dict)

            logger.debug(f"Phát hiện {len(result)} khuôn mặt trong ảnh")
            return result

        except Exception as e:
            logger.error(f"Lỗi phát hiện khuôn mặt: {e}")
            return []

    def get_embedding(self, image: np.ndarray) -> np.ndarray | None:
        """Trích xuất face embedding 512 chiều từ ảnh.

        Args:
            image: Ảnh numpy array chứa khuôn mặt (BGR)

        Returns:
            Vector embedding 512 chiều hoặc None nếu không tìm thấy khuôn mặt
        """
        faces = self.detect_faces(image)

        if not faces:
            logger.warning("Không tìm thấy khuôn mặt trong ảnh")
            return None

        if len(faces) > 1:
            logger.warning(
                f"Phát hiện {len(faces)} khuôn mặt, sử dụng khuôn mặt có điểm cao nhất"
            )
            # Chọn khuôn mặt có điểm tin cậy cao nhất
            faces = sorted(faces, key=lambda x: x["det_score"], reverse=True)

        embedding = faces[0].get("embedding")
        if embedding is None:
            logger.warning("Không thể trích xuất embedding từ khuôn mặt")
            return None

        # Chuẩn hoá embedding
        embedding = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def compare_faces(
        self,
        emb1: np.ndarray,
        emb2: np.ndarray,
        threshold: float = 0.4,
    ) -> tuple[bool, float]:
        """So sánh hai face embeddings sử dụng cosine similarity.

        Args:
            emb1: Embedding thứ nhất
            emb2: Embedding thứ hai
            threshold: Ngưỡng để xác định là cùng người (mặc định: 0.4)

        Returns:
            Tuple (is_same_person, similarity_score)
        """
        if emb1 is None or emb2 is None:
            return False, 0.0

        # Chuẩn hoá
        e1 = np.array(emb1, dtype=np.float32)
        e2 = np.array(emb2, dtype=np.float32)

        norm1 = np.linalg.norm(e1)
        norm2 = np.linalg.norm(e2)

        if norm1 == 0 or norm2 == 0:
            return False, 0.0

        e1 = e1 / norm1
        e2 = e2 / norm2

        # Tính cosine similarity
        similarity = float(np.dot(e1, e2))
        is_same = similarity >= threshold

        return is_same, similarity

    def recognize_face(
        self,
        image: np.ndarray,
        known_embeddings: dict[str, np.ndarray],
        threshold: float = 0.4,
    ) -> dict | None:
        """Nhận diện khuôn mặt so với danh sách embedding đã biết.

        Args:
            image: Ảnh cần nhận diện (BGR)
            known_embeddings: Dict {user_id: embedding}
            threshold: Ngưỡng cosine similarity

        Returns:
            Dict chứa {user_id, confidence} của kết quả khớp nhất,
            hoặc None nếu không tìm thấy
        """
        if not known_embeddings:
            return None

        # Trích xuất embedding từ ảnh đầu vào
        query_embedding = self.get_embedding(image)
        if query_embedding is None:
            return None

        # Tìm kết quả khớp tốt nhất
        best_match_id = None
        best_similarity = -1.0

        for user_id, known_emb in known_embeddings.items():
            if known_emb is None:
                continue

            _, similarity = self.compare_faces(query_embedding, known_emb, threshold=0.0)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match_id = user_id

        # Kiểm tra có vượt ngưỡng không
        if best_match_id is not None and best_similarity >= threshold:
            return {
                "user_id": best_match_id,
                "confidence": best_similarity,
            }

        logger.debug(
            f"Không tìm thấy kết quả khớp (best similarity: {best_similarity:.3f})"
        )
        return None

    def align_face(
        self, image: np.ndarray, landmarks: list[list[float]]
    ) -> np.ndarray:
        """Căn chỉnh khuôn mặt sử dụng facial landmarks để cải thiện chất lượng embedding.

        Args:
            image: Ảnh gốc (BGR)
            landmarks: Danh sách 5 điểm landmark [[x1,y1], ...]

        Returns:
            Ảnh khuôn mặt đã căn chỉnh
        """
        if not landmarks or len(landmarks) < 5:
            return image

        try:
            # Điểm chuẩn cho khuôn mặt 112x112 (ArcFace standard)
            arcface_dst = np.array(
                [
                    [38.2946, 51.6963],
                    [73.5318, 51.5014],
                    [56.0252, 71.7366],
                    [41.5493, 92.3655],
                    [70.7299, 92.2041],
                ],
                dtype=np.float32,
            )

            src = np.array(landmarks[:5], dtype=np.float32)

            # Tính toán affine transform
            tform = cv2.estimateAffinePartial2D(src, arcface_dst, method=cv2.LMEDS)
            if tform[0] is None:
                return image

            # Áp dụng transform
            aligned = cv2.warpAffine(image, tform[0], (112, 112))
            return aligned

        except Exception as e:
            logger.warning(f"Không thể căn chỉnh khuôn mặt: {e}")
            return image


# Singleton instance
_face_service: FaceService | None = None


def get_face_service() -> FaceService:
    """Trả về singleton FaceService instance."""
    global _face_service
    if _face_service is None:
        from app.config import settings
        _face_service = FaceService(
            model_name=settings.insightface_model,
            det_thresh=settings.insightface_det_thresh,
        )
    return _face_service

"""Test cơ bản cho FaceService."""
import numpy as np

from app.services.face_service import FaceService


class TestFaceService:
    """Kiểm tra FaceService."""

    def setup_method(self):
        """Khởi tạo FaceService với cấu hình test."""
        self.service = FaceService(model_name="buffalo_l", det_thresh=0.5)

    def test_compare_faces_same_embedding(self):
        """Hai embedding giống nhau phải có similarity = 1.0."""
        emb = np.random.rand(512).astype(np.float32)
        emb = emb / np.linalg.norm(emb)  # Chuẩn hoá

        is_same, similarity = self.service.compare_faces(emb, emb, threshold=0.4)
        assert is_same is True
        assert abs(similarity - 1.0) < 1e-5

    def test_compare_faces_different_embeddings(self):
        """Hai embedding khác nhau phải có similarity thấp."""
        emb1 = np.array([1.0] + [0.0] * 511, dtype=np.float32)
        emb2 = np.array([0.0, 1.0] + [0.0] * 510, dtype=np.float32)

        is_same, similarity = self.service.compare_faces(emb1, emb2, threshold=0.4)
        assert is_same is False
        assert similarity < 0.1

    def test_compare_faces_none_returns_false(self):
        """Embedding None phải trả về False."""
        emb = np.random.rand(512).astype(np.float32)
        is_same, similarity = self.service.compare_faces(None, emb)
        assert is_same is False
        assert similarity == 0.0

    def test_recognize_face_empty_embeddings(self):
        """recognize_face với embeddings rỗng phải trả về None."""
        dummy_image = np.zeros((100, 100, 3), dtype=np.uint8)
        result = self.service.recognize_face(dummy_image, {})
        assert result is None

    def test_recognize_face_finds_best_match(self):
        """recognize_face phải tìm kết quả khớp tốt nhất."""
        # Tạo embedding "query" và embedding đã biết
        query_emb = np.random.rand(512).astype(np.float32)
        query_emb = query_emb / np.linalg.norm(query_emb)

        # Embedding gần giống
        close_emb = query_emb + np.random.rand(512).astype(np.float32) * 0.01
        close_emb = close_emb / np.linalg.norm(close_emb)

        # Embedding hoàn toàn khác
        far_emb = np.random.rand(512).astype(np.float32)
        far_emb = far_emb / np.linalg.norm(far_emb)

        known_embeddings = {
            "user_close": close_emb,
            "user_far": far_emb,
        }

        # Monkey-patch get_embedding để trả về query_emb
        self.service.get_embedding = lambda img: query_emb

        result = self.service.recognize_face(
            np.zeros((100, 100, 3), dtype=np.uint8),
            known_embeddings,
            threshold=0.0,  # Threshold thấp để luôn match
        )

        assert result is not None
        assert result["user_id"] == "user_close"


class TestImageUtils:
    """Kiểm tra image_utils."""

    def test_decode_base64_image(self):
        """Decode base64 image phải trả về numpy array."""
        import base64

        import cv2

        # Tạo ảnh test
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".jpg", img)
        b64 = base64.b64encode(buffer).decode()

        from app.utils.image_utils import decode_base64_image
        result = decode_base64_image(b64)
        assert result is not None
        assert result.shape == (100, 100, 3)

    def test_decode_base64_with_data_url(self):
        """Decode data URL prefix phải hoạt động."""
        import base64

        import cv2

        img = np.zeros((50, 50, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".jpg", img)
        b64 = base64.b64encode(buffer).decode()
        data_url = f"data:image/jpeg;base64,{b64}"

        from app.utils.image_utils import decode_base64_image
        result = decode_base64_image(data_url)
        assert result is not None

    def test_resize_image(self):
        """Resize image phải giảm kích thước."""
        img = np.zeros((2000, 1500, 3), dtype=np.uint8)
        from app.utils.image_utils import resize_image
        result = resize_image(img, max_size=1024)
        assert max(result.shape[:2]) <= 1024

    def test_resize_image_small_unchanged(self):
        """Ảnh nhỏ không bị resize."""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        from app.utils.image_utils import resize_image
        result = resize_image(img, max_size=1024)
        assert result.shape == img.shape

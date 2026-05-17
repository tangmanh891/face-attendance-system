"""FastAPI entry point - Ứng dụng chính với CORS, lifespan, và routers."""
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.database import init_db
from app.routers import attendance, recognition, users


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter cho production."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)


# Cấu hình logging
handler = logging.StreamHandler()
if settings.debug:
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
else:
    handler.setFormatter(JSONFormatter())

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    handlers=[handler],
)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý lifecycle của ứng dụng - khởi tạo và dọn dẹp."""
    # Startup
    logger.info(f"Khởi động {settings.app_name} v{settings.app_version}")

    # Tạo thư mục upload
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(f"{settings.upload_dir}/faces", exist_ok=True)
    os.makedirs(f"{settings.upload_dir}/checkins", exist_ok=True)
    os.makedirs(f"{settings.upload_dir}/checkouts", exist_ok=True)

    # Khởi tạo database (chỉ development)
    try:
        await init_db(create_tables=settings.debug)
        logger.info("Kết nối database thành công")
    except Exception as e:
        logger.warning(f"Không thể kết nối database: {e}")

    # Pre-load InsightFace model để tránh chậm request đầu tiên
    try:
        from app.services.face_service import get_face_service
        face_service = get_face_service()
        face_service._initialize()
        logger.info("InsightFace model đã được pre-load")
    except Exception as e:
        logger.warning(f"Không thể pre-load InsightFace model: {e}")

    logger.info("Ứng dụng đã sẵn sàng")

    yield

    # Shutdown
    logger.info("Đang tắt ứng dụng...")


# Tạo FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Hệ thống điểm danh tự động sử dụng nhận diện khuôn mặt ArcFace",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Đăng ký routers
app.include_router(
    users.router,
    prefix="/api/users",
    tags=["Quản lý nhân viên"],
)
app.include_router(
    attendance.router,
    prefix="/api/attendance",
    tags=["Điểm danh"],
)
app.include_router(
    recognition.router,
    prefix="/api/recognition",
    tags=["Nhận diện khuôn mặt"],
)

# Global exception handler — tránh leak thông tin nội bộ
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Lỗi server nội bộ"},
    )


# Serve static files (ảnh upload)
if os.path.exists(settings.upload_dir):
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Chi tiết trạng thái hệ thống."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "database": "postgresql+pgvector",
        "ai_model": settings.insightface_model,
    }

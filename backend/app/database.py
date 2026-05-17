"""Cấu hình kết nối cơ sở dữ liệu async với SQLAlchemy và pgvector."""
import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class cho tất cả các SQLAlchemy models."""

    pass


# Tạo async engine
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_recycle=1800,
    pool_pre_ping=True,
    echo=settings.debug,
)

# Tạo session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency để lấy database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db(create_tables: bool | None = None) -> None:
    """Khởi tạo database tối thiểu; production dùng Alembic để tạo bảng."""
    if create_tables is None:
        create_tables = settings.debug

    async with engine.begin() as conn:
        # Kích hoạt pgvector extension
        await conn.execute(
            text("CREATE EXTENSION IF NOT EXISTS vector")
        )
        logger.info("pgvector extension đã được kích hoạt")

        if not create_tables:
            logger.info("Bỏ qua Base.metadata.create_all; sử dụng Alembic migrations")
            return

        # Tạo tất cả bảng chỉ khi development/debug.
        from app.models import Attendance, User  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Tất cả bảng đã được tạo")

"""Alembic environment configuration cho async SQLAlchemy."""
import asyncio
from logging.config import fileConfig
from os import getenv

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Thêm app vào path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base
from app.models import User, Attendance  # noqa: F401 - Cần import để Alembic biết về models

# Đây là đối tượng config Alembic, cung cấp quyền truy cập vào .ini file
config = context.config

# Cấu hình logging từ config file nếu có
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata target cho autogenerate
target_metadata = Base.metadata

# Lấy database URL từ biến môi trường (ưu tiên hơn alembic.ini)
database_url = getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres123@localhost:5433/face_attendance"
)
config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """Chạy migrations ở chế độ 'offline' (không kết nối database)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Thực thi migrations với kết nối đã cho."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Chạy migrations ở chế độ 'online' với async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Chạy migrations ở chế độ 'online'."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

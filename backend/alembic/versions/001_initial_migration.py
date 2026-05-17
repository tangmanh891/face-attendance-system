"""Migration ban đầu - Tạo extension pgvector và các bảng chính.

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Thông tin revision
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Tạo extension pgvector và các bảng cần thiết."""
    # Kích hoạt pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


    # Tạo bảng users
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("employee_id", sa.String(50), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True, unique=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("position", sa.String(100), nullable=True),
        # Vector 512 chiều cho ArcFace embedding
        sa.Column("face_embedding", sa.Text(), nullable=True),  # Stored as pgvector
        sa.Column("face_image_path", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Thêm cột vector riêng (pgvector cần cú pháp đặc biệt)
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS face_embedding_vec vector(512)")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS face_embedding")
    op.execute("ALTER TABLE users RENAME COLUMN face_embedding_vec TO face_embedding")

    # Tạo index cho employee_id
    op.create_index("ix_users_employee_id", "users", ["employee_id"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    # Tạo HNSW index trên face_embedding cho fast nearest neighbor search
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_users_face_embedding_hnsw
        ON users
        USING hnsw (face_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Tạo bảng attendances
    op.create_table(
        "attendances",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("check_in_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_out_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("captured_image_path", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ON_TIME", "LATE", "ABSENT", "EARLY_LEAVE", name="attendancestatus"),
            nullable=False,
            server_default="ON_TIME",
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Tạo các index cho attendances
    op.create_index("ix_attendances_user_id", "attendances", ["user_id"])
    op.create_index("ix_attendances_date", "attendances", ["date"])
    op.create_index(
        "ix_attendances_user_date",
        "attendances",
        ["user_id", "date"],
        unique=True,  # Mỗi nhân viên chỉ có 1 bản ghi mỗi ngày
    )

    # Trigger tự động cập nhật updated_at cho bảng users
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    op.execute("""
        CREATE TRIGGER update_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    """Xoá tất cả bảng và extension."""
    op.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    op.drop_index("ix_attendances_user_date", "attendances")
    op.drop_index("ix_attendances_date", "attendances")
    op.drop_index("ix_attendances_user_id", "attendances")
    op.drop_table("attendances")
    op.execute("DROP INDEX IF EXISTS ix_users_face_embedding_hnsw")
    op.drop_index("ix_users_is_active", "users")
    op.drop_index("ix_users_employee_id", "users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS attendancestatus")

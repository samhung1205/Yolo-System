"""create detection_batches table + detection_tasks.batch_id

Phase: batch image analysis (Phase 1). Adds a lightweight grouping table so a
single "upload folder / multiple images" request can be tracked as one unit
(progress, status, aggregate stats) while each image still gets its own
``detection_tasks`` row (fully reusing the existing single-image pipeline).

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-23 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "detection_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_key", sa.String(length=100), nullable=True),
        sa.Column("model_sha256", sa.String(length=64), nullable=True),
        sa.Column("confidence_threshold", sa.Float(), nullable=True),
        sa.Column("iou_threshold", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_files", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_detection_batches_user_id", "detection_batches", ["user_id"])
    op.create_index("idx_detection_batches_status", "detection_batches", ["status"])

    op.add_column(
        "detection_tasks",
        sa.Column("batch_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_detection_tasks_batch_id_detection_batches",
        "detection_tasks",
        "detection_batches",
        ["batch_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_detection_tasks_batch_id", "detection_tasks", ["batch_id"])


def downgrade() -> None:
    op.drop_index("idx_detection_tasks_batch_id", table_name="detection_tasks")
    op.drop_constraint(
        "fk_detection_tasks_batch_id_detection_batches",
        "detection_tasks",
        type_="foreignkey",
    )
    op.drop_column("detection_tasks", "batch_id")

    op.drop_index("idx_detection_batches_status", table_name="detection_batches")
    op.drop_index("idx_detection_batches_user_id", table_name="detection_batches")
    op.drop_table("detection_batches")

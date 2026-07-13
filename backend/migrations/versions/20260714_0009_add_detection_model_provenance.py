"""add detection model provenance

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-14 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "detection_tasks",
        sa.Column("model_key", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "detection_tasks",
        sa.Column("model_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "detection_tasks",
        sa.Column("model_class_map_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "detection_tasks",
        sa.Column("confidence_threshold", sa.Float(), nullable=True),
    )
    op.add_column(
        "detection_tasks",
        sa.Column("iou_threshold", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("detection_tasks", "iou_threshold")
    op.drop_column("detection_tasks", "confidence_threshold")
    op.drop_column("detection_tasks", "model_class_map_json")
    op.drop_column("detection_tasks", "model_sha256")
    op.drop_column("detection_tasks", "model_key")

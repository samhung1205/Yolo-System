"""add_detection_video_fields

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-18 00:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("detection_tasks", sa.Column("source_video_path", sa.String(length=255), nullable=True))
    op.add_column("detection_tasks", sa.Column("result_video_path", sa.String(length=255), nullable=True))
    op.add_column("detection_tasks", sa.Column("preview_image_path", sa.String(length=255), nullable=True))
    op.add_column("detection_tasks", sa.Column("frame_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("detection_tasks", "frame_count")
    op.drop_column("detection_tasks", "preview_image_path")
    op.drop_column("detection_tasks", "result_video_path")
    op.drop_column("detection_tasks", "source_video_path")

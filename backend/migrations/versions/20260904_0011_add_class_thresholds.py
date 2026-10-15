"""add per-class threshold columns to detection_tasks / detection_batches

Per-class detection lets each class carry its own confidence and IoU
threshold (e.g. class 0 at conf 0.20 / IoU 0.40 while class 4 runs at
conf 0.50 / IoU 0.35). The existing scalar ``confidence_threshold`` /
``iou_threshold`` columns stay in place and keep acting as the default for
any class not listed, so existing rows and single-threshold requests are
unaffected.

Stored shape (JSON, keyed by class id as a string):
    {"0": {"conf": 0.2, "iou": 0.4}, "4": {"conf": 0.5, "iou": 0.35}}

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-04 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "detection_tasks",
        sa.Column("class_thresholds_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "detection_batches",
        sa.Column("class_thresholds_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("detection_batches", "class_thresholds_json")
    op.drop_column("detection_tasks", "class_thresholds_json")

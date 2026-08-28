"""
Detection batch ORM model.

Groups a set of ``detection_tasks`` created from a single "multiple images /
folder upload" request so the whole batch can be tracked (progress, status)
and aggregated (per-class totals across all images) as one unit.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class DetectionBatch(Base):
    __tablename__ = "detection_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    iou_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_files: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    tasks = relationship(
        "DetectionTask",
        back_populates="batch",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DetectionTask.id",
    )

    def __repr__(self) -> str:
        return f"<DetectionBatch id={self.id} user_id={self.user_id} status={self.status}>"

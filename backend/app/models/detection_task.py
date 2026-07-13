"""
Detection task ORM model.
Stores uploaded media and its inference result summary.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class DetectionTask(Base):
    __tablename__ = "detection_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="image")
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_video_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_video_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preview_image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_class_map_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    iou_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing", index=True)
    inference_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frame_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    objects = relationship(
        "DetectionObject",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<DetectionTask id={self.id} user_id={self.user_id} status={self.status}>"

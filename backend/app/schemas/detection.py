"""
Pydantic schemas for detection API.
"""
from datetime import datetime

from pydantic import BaseModel, Field


class YoloModelRead(BaseModel):
    key: str
    display_name: str
    checkpoint: str
    architecture: str
    dataset_variant: str
    task: str
    input_size: int
    checkpoint_class_names: dict[int, str]
    canonical_class_names: dict[int, str]
    class_count: int
    sha256: str | None
    available: bool
    is_default: bool
    unavailable_reason: str | None


class DetectionObjectRead(BaseModel):
    id: int
    object_index: int
    class_id: int
    class_name: str
    confidence: float
    bbox: list[float] = Field(description="[x1, y1, x2, y2]")


class DetectionTaskSummaryRead(BaseModel):
    id: int
    user_id: int
    source_type: str
    source_filename: str
    source_image_path: str | None
    source_image_url: str | None
    result_image_path: str | None
    result_image_url: str | None
    source_video_path: str | None
    source_video_url: str | None
    result_video_path: str | None
    result_video_url: str | None
    preview_image_path: str | None
    preview_image_url: str | None
    model_name: str
    model_key: str | None
    model_sha256: str | None
    model_class_map: dict[str, dict[str, str]] | None
    confidence_threshold: float | None
    iou_threshold: float | None
    status: str
    inference_ms: float | None
    image_width: int | None
    image_height: int | None
    frame_count: int | None
    object_count: int
    created_at: datetime
    updated_at: datetime


class DetectionTaskRead(DetectionTaskSummaryRead):
    error_message: str | None
    objects: list[DetectionObjectRead]

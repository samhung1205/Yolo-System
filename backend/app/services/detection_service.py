"""
Detection business logic for media inference.
"""
import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.static_tokens import build_signed_static_url
from app.db.session import SessionLocal
from app.integrations.model_registry import (
    YoloModelRegistryError,
    YoloModelSpec,
    get_yolo_model,
)
from app.integrations.yolo_engine import YoloEngine
from app.models.detection_task import DetectionTask
from app.models.user import User
from app.repositories import detection_repository
from app.schemas.detection import DetectionObjectRead, DetectionTaskRead, DetectionTaskSummaryRead

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"}
ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "video/x-flv",
}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".flv"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE = 200 * 1024 * 1024  # 200 MB


def create_image_detection(
    db: Session,
    *,
    current_user: User,
    file: UploadFile,
    conf: float = 0.25,
    iou: float = 0.45,
    model_key: str | None = None,
) -> DetectionTaskRead:
    _validate_upload(file)
    model_spec = _resolve_model(model_key)

    task = detection_repository.create_task(
        db,
        user_id=current_user.id,
        source_type="image",
        source_filename=file.filename or "uploaded_image",
        model_name=model_spec.checkpoint_path.name,
        model_key=model_spec.key,
        model_sha256=model_spec.current_sha256(),
        model_class_map_json=model_spec.provenance_snapshot(),
        confidence_threshold=conf,
        iou_threshold=iou,
        status="processing",
    )

    source_fs_path: Path | None = None
    result_fs_path: Path | None = None

    try:
        source_fs_path, source_rel_path = _store_original_image(task.id, file)
        detection_repository.update_task(db, task, source_image_path=source_rel_path)

        engine = YoloEngine(model_key=model_spec.key)
        detection_result = engine.detect_image(source_fs_path, conf=conf, iou=iou)

        result_fs_path, result_rel_path = _store_result_image(task.id, detection_result.annotated_image)

        detection_repository.update_task(
            db,
            task,
            source_image_path=source_rel_path,
            result_image_path=result_rel_path,
            model_name=detection_result.model_name,
            model_key=detection_result.model_key,
            model_sha256=detection_result.model_sha256,
            model_class_map_json=detection_result.model_class_map,
            status="completed",
            inference_ms=detection_result.inference_ms,
            image_width=detection_result.image_width,
            image_height=detection_result.image_height,
            error_message=None,
        )

        object_rows = [
            {
                "object_index": obj["object_index"],
                "class_id": obj["class_id"],
                "class_name": obj["class_name"],
                "confidence": obj["confidence"],
                "bbox_x1": obj["bbox"][0],
                "bbox_y1": obj["bbox"][1],
                "bbox_x2": obj["bbox"][2],
                "bbox_y2": obj["bbox"][3],
            }
            for obj in detection_result.objects
        ]
        detection_repository.replace_task_objects(db, task, object_rows)
        task = detection_repository.get_task(db, task.id)
        assert task is not None
        return _serialize_task(task)
    except HTTPException as exc:
        _cleanup_files(source_fs_path, result_fs_path)
        detection_repository.update_task(db, task, status="failed", error_message=exc.detail)
        raise
    except Exception as exc:
        _cleanup_files(source_fs_path, result_fs_path)
        detection_repository.update_task(db, task, status="failed", error_message=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection failed: {exc}",
        ) from exc


def create_video_detection_task(
    db: Session,
    *,
    current_user: User,
    file: UploadFile,
    conf: float = 0.25,
    iou: float = 0.45,
    model_key: str | None = None,
) -> DetectionTaskRead:
    _validate_video_upload(file)
    model_spec = _resolve_model(model_key)

    task = detection_repository.create_task(
        db,
        user_id=current_user.id,
        source_type="video",
        source_filename=file.filename or "uploaded_video",
        model_name=model_spec.checkpoint_path.name,
        model_key=model_spec.key,
        model_sha256=model_spec.current_sha256(),
        model_class_map_json=model_spec.provenance_snapshot(),
        confidence_threshold=conf,
        iou_threshold=iou,
        status="processing",
    )

    try:
        source_fs_path, source_rel_path = _store_original_video(task.id, file)
        detection_repository.update_task(db, task, source_video_path=source_rel_path, error_message=None)
        task = detection_repository.get_task(db, task.id)
        assert task is not None
        return _serialize_task(task)
    except HTTPException as exc:
        source_fs_path = _static_root() / task.source_video_path if task.source_video_path else None
        _cleanup_files(source_fs_path)
        detection_repository.update_task(db, task, status="failed", error_message=exc.detail)
        raise
    except Exception as exc:
        source_fs_path = _static_root() / task.source_video_path if task.source_video_path else None
        _cleanup_files(source_fs_path)
        detection_repository.update_task(db, task, status="failed", error_message=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection failed: {exc}",
        ) from exc


def process_video_detection_task(*, task_id: int, conf: float = 0.25, iou: float = 0.45) -> None:
    db = SessionLocal()
    task = detection_repository.get_task(db, task_id)
    if task is None:
        db.close()
        return

    source_fs_path = _static_root() / task.source_video_path if task.source_video_path else None
    result_video_fs_path: Path | None = None
    preview_fs_path: Path | None = None

    try:
        if source_fs_path is None or not source_fs_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source video not found for detection task",
            )

        result_video_fs_path, result_video_rel_path = _allocate_result_video_path(task.id)
        detection_repository.update_task(db, task, result_video_path=result_video_rel_path, status="processing")

        engine = YoloEngine(model_key=task.model_key)
        detection_result = engine.detect_video(
            source_fs_path,
            output_video_path=result_video_fs_path,
            conf=conf,
            iou=iou,
        )

        preview_fs_path, preview_rel_path = _store_preview_image(task.id, detection_result.preview_image)

        detection_repository.update_task(
            db,
            task,
            result_video_path=result_video_rel_path,
            preview_image_path=preview_rel_path,
            model_name=detection_result.model_name,
            model_key=detection_result.model_key,
            model_sha256=detection_result.model_sha256,
            model_class_map_json=detection_result.model_class_map,
            status="completed",
            inference_ms=detection_result.inference_ms,
            image_width=detection_result.image_width,
            image_height=detection_result.image_height,
            frame_count=detection_result.frame_count,
            error_message=None,
        )

        object_rows = [
            {
                "object_index": obj["object_index"],
                "class_id": obj["class_id"],
                "class_name": obj["class_name"],
                "confidence": obj["confidence"],
                "bbox_x1": obj["bbox"][0],
                "bbox_y1": obj["bbox"][1],
                "bbox_x2": obj["bbox"][2],
                "bbox_y2": obj["bbox"][3],
            }
            for obj in detection_result.objects
        ]
        detection_repository.replace_task_objects(db, task, object_rows)
    except HTTPException as exc:
        _cleanup_files(result_video_fs_path, preview_fs_path)
        detection_repository.update_task(db, task, status="failed", error_message=exc.detail)
    except Exception as exc:
        _cleanup_files(result_video_fs_path, preview_fs_path)
        detection_repository.update_task(db, task, status="failed", error_message=str(exc))
    finally:
        db.close()


def list_detections(
    db: Session,
    *,
    current_user: User,
    status: str | None = None,
    source_type: str | None = None,
    limit: int = 50,
    page: int = 1,
) -> tuple[int, list[DetectionTaskSummaryRead]]:
    """Return (total_count, items) with optional filters and pagination."""
    user_id = None if current_user.is_admin else current_user.id
    offset = (max(1, page) - 1) * limit
    total = detection_repository.count_tasks(
        db,
        user_id=user_id,
        status=status or None,
        source_type=source_type or None,
    )
    tasks = detection_repository.list_tasks(
        db,
        user_id=user_id,
        status=status or None,
        source_type=source_type or None,
        limit=limit,
        offset=offset,
    )
    return total, [_serialize_task_summary(task) for task in tasks]


def get_detection(db: Session, *, current_user: User, detection_id: int) -> DetectionTaskRead:
    task = _get_owned_task(db, current_user=current_user, detection_id=detection_id)
    return _serialize_task(task)


def delete_detection(db: Session, *, current_user: User, detection_id: int) -> None:
    task = _get_owned_task(db, current_user=current_user, detection_id=detection_id)
    source_fs_path = _static_root() / task.source_image_path if task.source_image_path else None
    result_fs_path = _static_root() / task.result_image_path if task.result_image_path else None
    source_video_fs_path = _static_root() / task.source_video_path if task.source_video_path else None
    result_video_fs_path = _static_root() / task.result_video_path if task.result_video_path else None
    preview_fs_path = _static_root() / task.preview_image_path if task.preview_image_path else None
    _cleanup_files(source_fs_path, result_fs_path, source_video_fs_path, result_video_fs_path, preview_fs_path)
    detection_repository.delete_task(db, task)


def _get_owned_task(db: Session, *, current_user: User, detection_id: int) -> DetectionTask:
    task = detection_repository.get_task(db, detection_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection task not found")
    if not current_user.is_admin and task.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this detection")
    return task


def _validate_upload(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image uploads are supported for Phase 3 MVP",
        )


def _resolve_model(model_key: str | None) -> YoloModelSpec:
    try:
        return get_yolo_model(model_key)
    except YoloModelRegistryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _validate_video_upload(file: UploadFile) -> None:
    extension = Path(file.filename or "").suffix.lower()
    if file.content_type not in ALLOWED_VIDEO_TYPES and extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only MP4, MOV, AVI, MKV, and FLV video uploads are supported",
        )


def _store_original_image(task_id: int, file: UploadFile) -> tuple[Path, str]:
    extension = Path(file.filename or "").suffix or ".jpg"
    full_path = Path(settings.DETECTION_SOURCE_DIR) / f"task_{task_id}_{uuid4().hex[:8]}{extension}"
    relative_path = _to_static_relative_path(full_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)

    total_size = 0
    with full_path.open("wb") as buffer:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_IMAGE_SIZE:
                buffer.close()
                if full_path.exists():
                    full_path.unlink()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Image size must not exceed 10 MB",
                )
            buffer.write(chunk)
    file.file.close()
    return full_path, relative_path


def _store_original_video(task_id: int, file: UploadFile) -> tuple[Path, str]:
    extension = Path(file.filename or "").suffix.lower() or ".mp4"
    full_path = Path(settings.DETECTION_VIDEO_SOURCE_DIR) / f"task_{task_id}_{uuid4().hex[:8]}{extension}"
    relative_path = _to_static_relative_path(full_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)

    total_size = 0
    with full_path.open("wb") as buffer:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_VIDEO_SIZE:
                buffer.close()
                if full_path.exists():
                    full_path.unlink()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Video size must not exceed 200 MB",
                )
            buffer.write(chunk)
    file.file.close()
    return full_path, relative_path


def _store_result_image(task_id: int, image) -> tuple[Path, str]:
    full_path = Path(settings.DETECTION_RESULT_DIR) / f"task_{task_id}_{uuid4().hex[:8]}.jpg"
    relative_path = _to_static_relative_path(full_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(full_path, format="JPEG")
    return full_path, relative_path


def _store_preview_image(task_id: int, image) -> tuple[Path, str]:
    full_path = Path(settings.DETECTION_PREVIEW_DIR) / f"task_{task_id}_{uuid4().hex[:8]}.jpg"
    relative_path = _to_static_relative_path(full_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(full_path, format="JPEG")
    return full_path, relative_path


def _allocate_result_video_path(task_id: int) -> tuple[Path, str]:
    full_path = Path(settings.DETECTION_VIDEO_RESULT_DIR) / f"task_{task_id}_{uuid4().hex[:8]}.mp4"
    relative_path = _to_static_relative_path(full_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    return full_path, relative_path


def _static_root() -> Path:
    return Path("static")


def _cleanup_files(*paths: Path | None) -> None:
    for path in paths:
        if path and path.exists():
            path.unlink(missing_ok=True)


def _serialize_task(task: DetectionTask) -> DetectionTaskRead:
    return DetectionTaskRead(
        **_serialize_task_summary(task).model_dump(),
        error_message=task.error_message,
        objects=[
            DetectionObjectRead(
                id=obj.id,
                object_index=obj.object_index,
                class_id=obj.class_id,
                class_name=obj.class_name,
                confidence=obj.confidence,
                bbox=[obj.bbox_x1, obj.bbox_y1, obj.bbox_x2, obj.bbox_y2],
            )
            for obj in task.objects
        ],
    )


def _serialize_task_summary(task: DetectionTask) -> DetectionTaskSummaryRead:
    return DetectionTaskSummaryRead(
        id=task.id,
        user_id=task.user_id,
        source_type=task.source_type,
        source_filename=task.source_filename,
        source_image_path=task.source_image_path,
        source_image_url=_to_static_url(task.source_image_path),
        result_image_path=task.result_image_path,
        result_image_url=_to_static_url(task.result_image_path),
        source_video_path=task.source_video_path,
        source_video_url=_to_static_url(task.source_video_path),
        result_video_path=task.result_video_path,
        result_video_url=_to_static_url(task.result_video_path),
        preview_image_path=task.preview_image_path,
        preview_image_url=_to_static_url(task.preview_image_path),
        model_name=task.model_name,
        model_key=task.model_key,
        model_sha256=task.model_sha256,
        model_class_map=task.model_class_map_json,
        confidence_threshold=task.confidence_threshold,
        iou_threshold=task.iou_threshold,
        status=task.status,
        inference_ms=task.inference_ms,
        image_width=task.image_width,
        image_height=task.image_height,
        frame_count=task.frame_count,
        object_count=len(task.objects),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _to_static_url(relative_path: str | None) -> str | None:
    if not relative_path:
        return None
    normalized = relative_path.replace(os.sep, "/")
    return build_signed_static_url(normalized)


def _to_static_relative_path(full_path: Path) -> str:
    static_root = _static_root().resolve()
    return str(full_path.resolve().relative_to(static_root))

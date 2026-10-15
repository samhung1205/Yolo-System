"""
Detection business logic for media inference.
"""
import io
import json
import os
import zipfile
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.static_tokens import build_signed_static_url
from app.db.session import SessionLocal
from app.integrations.model_registry import (
    YoloModelRegistryError,
    YoloModelSpec,
    get_yolo_model,
)
from app.integrations.yolo_engine import ClassThreshold, YoloEngine
from app.models.detection_batch import DetectionBatch
from app.models.detection_task import DetectionTask
from app.models.user import User
from app.repositories import detection_repository
from app.schemas.detection import (
    BatchDetailRead,
    BatchRead,
    ClassThreshold as ClassThresholdSchema,
    DetectionObjectRead,
    DetectionTaskRead,
    DetectionTaskSummaryRead,
)

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


def parse_class_thresholds(
    raw: str | None,
    model_spec: YoloModelSpec,
) -> dict[int, ClassThreshold] | None:
    """Validate a per-class threshold JSON payload against a model's classes.

    Expected shape, keyed by class id:
    ``{"0": {"conf": 0.2, "iou": 0.4}, "4": {"conf": 0.5, "iou": 0.35}}``

    Returns ``None`` for a missing/blank/empty payload so callers fall back to
    the scalar thresholds. Class ids are checked against the *selected* model
    so a stale UI (or a model switch) can't silently apply thresholds to the
    wrong classes.
    """
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None

    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"class_thresholds must be valid JSON: {exc}",
        ) from exc

    if not isinstance(decoded, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='class_thresholds must be a JSON object keyed by class id, e.g. {"0": {"conf": 0.2, "iou": 0.4}}',
        )
    if not decoded:
        return None

    valid_class_ids = set(model_spec.canonical_class_names)
    parsed: dict[int, ClassThreshold] = {}
    for raw_class_id, raw_threshold in decoded.items():
        try:
            class_id = int(raw_class_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"class_thresholds keys must be class ids: got {raw_class_id!r}",
            ) from exc

        if class_id not in valid_class_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"class id {class_id} is not part of model '{model_spec.key}' "
                    f"(valid ids: {sorted(valid_class_ids)})"
                ),
            )

        try:
            validated = ClassThresholdSchema.model_validate(raw_threshold)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"invalid threshold for class {class_id}: {exc.errors()}",
            ) from exc

        parsed[class_id] = ClassThreshold(conf=validated.conf, iou=validated.iou)

    return parsed


def _class_thresholds_to_json(
    class_thresholds: dict[int, ClassThreshold] | None,
) -> dict | None:
    """Serialize per-class thresholds for storage / API responses."""
    if not class_thresholds:
        return None
    return {
        str(class_id): {"conf": threshold.conf, "iou": threshold.iou}
        for class_id, threshold in sorted(class_thresholds.items())
    }


def _class_thresholds_from_json(payload: dict | None) -> dict[int, ClassThreshold] | None:
    """Rebuild per-class thresholds from a stored JSON column."""
    if not payload:
        return None
    return {
        int(class_id): ClassThreshold(conf=float(values["conf"]), iou=float(values["iou"]))
        for class_id, values in payload.items()
    }


def create_image_detection(
    db: Session,
    *,
    current_user: User,
    file: UploadFile,
    conf: float = 0.25,
    iou: float = 0.45,
    model_key: str | None = None,
    class_thresholds: dict[int, ClassThreshold] | None = None,
) -> DetectionTaskRead:
    _validate_upload(file)
    model_spec = resolve_model(model_key)

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
        class_thresholds_json=_class_thresholds_to_json(class_thresholds),
        status="processing",
    )

    source_fs_path: Path | None = None
    result_fs_path: Path | None = None

    try:
        source_fs_path, source_rel_path = _store_original_image(task.id, file)
        detection_repository.update_task(db, task, source_image_path=source_rel_path)

        engine = YoloEngine(model_key=model_spec.key)
        detection_result = engine.detect_image(
            source_fs_path,
            conf=conf,
            iou=iou,
            class_thresholds=class_thresholds,
        )

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
    model_spec = resolve_model(model_key)

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


def create_image_batch(
    db: Session,
    *,
    current_user: User,
    files: list[UploadFile],
    conf: float = 0.25,
    iou: float = 0.45,
    model_key: str | None = None,
    name: str | None = None,
    class_thresholds: dict[int, ClassThreshold] | None = None,
) -> BatchDetailRead:
    """Store every valid image in ``files`` as a pending task under one batch.

    Non-image files are skipped (recorded in ``skipped_files``) rather than
    failing the whole request, since folder uploads often contain stray
    files (e.g. ``.DS_Store``). Per-file storage errors (e.g. oversized image)
    only fail that one task; the rest of the batch still proceeds.
    Inference itself is NOT run here — the caller schedules
    :func:`process_image_batch_task` as a background task.
    """
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one file is required")
    if len(files) > settings.DETECTION_BATCH_MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch upload is limited to {settings.DETECTION_BATCH_MAX_FILES} files per request",
        )

    model_spec = resolve_model(model_key)

    valid_files: list[UploadFile] = []
    skipped_files: list[str] = []
    for upload in files:
        if upload.content_type in ALLOWED_IMAGE_TYPES:
            valid_files.append(upload)
        else:
            skipped_files.append(upload.filename or "unknown")

    if not valid_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid image files found in the upload",
        )

    class_thresholds_json = _class_thresholds_to_json(class_thresholds)
    batch = detection_repository.create_batch(
        db,
        user_id=current_user.id,
        name=name,
        model_name=model_spec.checkpoint_path.name,
        model_key=model_spec.key,
        model_sha256=model_spec.current_sha256(),
        confidence_threshold=conf,
        iou_threshold=iou,
        class_thresholds_json=class_thresholds_json,
        total_files=len(valid_files),
        skipped_files=skipped_files,
        status="processing",
    )

    upload_failed_count = 0
    for upload in valid_files:
        task = detection_repository.create_task(
            db,
            user_id=current_user.id,
            source_type="image",
            source_filename=upload.filename or "uploaded_image",
            model_name=model_spec.checkpoint_path.name,
            model_key=model_spec.key,
            model_sha256=model_spec.current_sha256(),
            model_class_map_json=model_spec.provenance_snapshot(),
            confidence_threshold=conf,
            iou_threshold=iou,
            class_thresholds_json=class_thresholds_json,
            status="pending",
            batch_id=batch.id,
        )
        try:
            source_fs_path, source_rel_path = _store_original_image(task.id, upload)
            detection_repository.update_task(db, task, source_image_path=source_rel_path)
        except HTTPException as exc:
            upload_failed_count += 1
            detection_repository.update_task(db, task, status="failed", error_message=exc.detail)
        except Exception as exc:  # pragma: no cover - defensive
            upload_failed_count += 1
            detection_repository.update_task(db, task, status="failed", error_message=str(exc))

    if upload_failed_count >= len(valid_files):
        detection_repository.update_batch(
            db,
            batch,
            status="failed",
            failed_count=upload_failed_count,
            error_message="All files failed to upload",
        )
    elif upload_failed_count:
        detection_repository.update_batch(db, batch, failed_count=upload_failed_count)

    batch = detection_repository.get_batch(db, batch.id)
    assert batch is not None
    return _serialize_batch_detail(batch)


def process_image_batch_task(*, batch_id: int, conf: float = 0.25, iou: float = 0.45) -> None:
    """Background task: run YOLO inference sequentially for every pending
    task in the batch, updating batch progress after each image so
    ``GET /api/detections/batches/{id}`` polling reflects real-time status.
    """
    db = SessionLocal()
    try:
        batch = detection_repository.get_batch(db, batch_id)
        if batch is None or batch.status == "failed":
            return

        # Read per-class thresholds from the batch row rather than the task
        # arguments so a resumed batch keeps the settings it was created with.
        class_thresholds = _class_thresholds_from_json(batch.class_thresholds_json)

        pending_tasks = detection_repository.get_pending_batch_tasks(db, batch_id)
        if not pending_tasks:
            _finalize_batch_status(db, batch)
            return

        try:
            engine = YoloEngine(model_key=batch.model_key)
        except Exception as exc:
            detection_repository.update_batch(
                db,
                batch,
                status="failed",
                error_message=f"Failed to load model for batch: {exc}",
            )
            for task in pending_tasks:
                detection_repository.update_task(db, task, status="failed", error_message="Batch model load failed")
            return

        processed_count = batch.processed_count or 0
        failed_count = batch.failed_count or 0

        for task in pending_tasks:
            result_fs_path: Path | None = None
            task_ok = True
            try:
                source_fs_path = _static_root() / task.source_image_path if task.source_image_path else None
                if source_fs_path is None or not source_fs_path.exists():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Source image not found for batch task",
                    )

                detection_result = engine.detect_image(
                    source_fs_path,
                    conf=conf,
                    iou=iou,
                    class_thresholds=class_thresholds,
                )
                result_fs_path, result_rel_path = _store_result_image(task.id, detection_result.annotated_image)

                detection_repository.update_task(
                    db,
                    task,
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
            except HTTPException as exc:
                task_ok = False
                _cleanup_files(result_fs_path)
                detection_repository.update_task(db, task, status="failed", error_message=exc.detail)
            except Exception as exc:  # pragma: no cover - defensive
                task_ok = False
                _cleanup_files(result_fs_path)
                detection_repository.update_task(db, task, status="failed", error_message=str(exc))

            processed_count += 1
            if not task_ok:
                failed_count += 1
            batch = detection_repository.update_batch(
                db,
                batch,
                processed_count=processed_count,
                failed_count=failed_count,
            )

        _finalize_batch_status(db, batch)
    finally:
        db.close()


def _finalize_batch_status(db: Session, batch: DetectionBatch) -> None:
    if batch.failed_count and batch.failed_count >= batch.total_files:
        detection_repository.update_batch(db, batch, status="failed")
    elif batch.failed_count:
        detection_repository.update_batch(db, batch, status="completed_with_errors")
    else:
        detection_repository.update_batch(db, batch, status="completed")


def list_batches(
    db: Session,
    *,
    current_user: User,
    status: str | None = None,
    limit: int = 20,
    page: int = 1,
) -> tuple[int, list[BatchRead]]:
    user_id = None if current_user.is_admin else current_user.id
    offset = (max(1, page) - 1) * limit
    total = detection_repository.count_batches(db, user_id=user_id, status=status or None)
    batches = detection_repository.list_batches(
        db,
        user_id=user_id,
        status=status or None,
        limit=limit,
        offset=offset,
    )
    return total, [_serialize_batch(batch) for batch in batches]


def get_batch(db: Session, *, current_user: User, batch_id: int) -> BatchDetailRead:
    batch = _get_owned_batch(db, current_user=current_user, batch_id=batch_id)
    return _serialize_batch_detail(batch)


def build_batch_results_zip(db: Session, *, current_user: User, batch_id: int) -> tuple[bytes, str]:
    """Zip every completed result image in a batch for a single download.

    Returns (zip_bytes, suggested_filename). Raises HTTPException(404) if the
    batch has no result images yet (e.g. still processing or every task
    failed), so the route can surface a clear error instead of an empty file.
    """
    batch = _get_owned_batch(db, current_user=current_user, batch_id=batch_id)

    entries: list[tuple[str, Path]] = []
    used_names: set[str] = set()
    for task in batch.tasks:
        if not task.result_image_path:
            continue
        fs_path = _static_root() / task.result_image_path
        if not fs_path.is_file():
            continue
        arcname = _unique_zip_arcname(task, used_names)
        used_names.add(arcname)
        entries.append((arcname, fs_path))

    if not entries:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This batch has no completed result images to download yet",
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for arcname, fs_path in entries:
            archive.write(fs_path, arcname=arcname)

    filename = f"batch_{batch.id}_results.zip"
    return buffer.getvalue(), filename


def _unique_zip_arcname(task: DetectionTask, used_names: set[str]) -> str:
    stem = Path(task.source_filename or f"task_{task.id}").stem or f"task_{task.id}"
    safe_stem = "".join(char if char.isalnum() or char in "-_." else "_" for char in stem) or f"task_{task.id}"
    candidate = f"{safe_stem}.jpg"
    if candidate not in used_names:
        return candidate
    return f"{safe_stem}_task{task.id}.jpg"


def delete_batch(db: Session, *, current_user: User, batch_id: int) -> None:
    batch = _get_owned_batch(db, current_user=current_user, batch_id=batch_id)
    for task in batch.tasks:
        source_fs_path = _static_root() / task.source_image_path if task.source_image_path else None
        result_fs_path = _static_root() / task.result_image_path if task.result_image_path else None
        _cleanup_files(source_fs_path, result_fs_path)
    detection_repository.delete_batch(db, batch)


def _get_owned_batch(db: Session, *, current_user: User, batch_id: int) -> DetectionBatch:
    batch = detection_repository.get_batch(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if not current_user.is_admin and batch.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this batch")
    return batch


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


def resolve_model(model_key: str | None) -> YoloModelSpec:
    """Look up a registered model, as an HTTP 400 if the key is unknown.

    Public because routes resolve the model before the service call in order
    to validate per-class thresholds against that model's class ids.
    """
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
        class_thresholds=task.class_thresholds_json,
        status=task.status,
        inference_ms=task.inference_ms,
        image_width=task.image_width,
        image_height=task.image_height,
        frame_count=task.frame_count,
        object_count=len(task.objects),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _serialize_batch(batch: DetectionBatch) -> BatchRead:
    return BatchRead(
        id=batch.id,
        user_id=batch.user_id,
        name=batch.name,
        model_name=batch.model_name,
        model_key=batch.model_key,
        model_sha256=batch.model_sha256,
        confidence_threshold=batch.confidence_threshold,
        iou_threshold=batch.iou_threshold,
        class_thresholds=batch.class_thresholds_json,
        status=batch.status,
        total_files=batch.total_files,
        processed_count=batch.processed_count,
        failed_count=batch.failed_count,
        skipped_files=batch.skipped_files or [],
        error_message=batch.error_message,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def _serialize_batch_detail(batch: DetectionBatch) -> BatchDetailRead:
    return BatchDetailRead(
        **_serialize_batch(batch).model_dump(),
        tasks=[_serialize_task_summary(task) for task in batch.tasks],
    )


def _to_static_url(relative_path: str | None) -> str | None:
    if not relative_path:
        return None
    normalized = relative_path.replace(os.sep, "/")
    return build_signed_static_url(normalized)


def _to_static_relative_path(full_path: Path) -> str:
    static_root = _static_root().resolve()
    return str(full_path.resolve().relative_to(static_root))

"""
Detection API routes.
Phase 3 MVP supports image/video inference.
Phase 3 補完 adds filter + pagination to GET /api/detections.
"""
import math
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.detection import BatchDetailRead, BatchRead, DetectionTaskRead, DetectionTaskSummaryRead
from app.services import detection_service

router = APIRouter()


# NOTE: the /batch(es) routes are registered before "/{detection_id}" so the
# literal "batches" path segment is matched first (FastAPI's int converter on
# detection_id would reject it anyway, but this keeps route order unambiguous).
@router.post("/batch", response_model=BatchDetailRead, status_code=status.HTTP_202_ACCEPTED)
def detect_image_batch(
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    files: Annotated[list[UploadFile], File(description="Multiple images for batch YOLO detection")],
    conf: float = Query(default=0.25, ge=0.0, le=1.0),
    iou: float = Query(default=0.45, ge=0.0, le=1.0),
    model_key: str | None = Query(default=None, min_length=1, max_length=100),
    name: str | None = Query(default=None, max_length=255),
):
    batch = detection_service.create_image_batch(
        db,
        current_user=current_user,
        files=files,
        conf=conf,
        iou=iou,
        model_key=model_key,
        name=name,
    )
    background_tasks.add_task(
        detection_service.process_image_batch_task,
        batch_id=batch.id,
        conf=conf,
        iou=iou,
    )
    return batch


@router.get("/batches", response_model=list[BatchRead])
def list_detection_batches(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    filter_status: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    page: int = Query(default=1, ge=1),
):
    total, items = detection_service.list_batches(
        db,
        current_user=current_user,
        status=filter_status,
        limit=limit,
        page=page,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Total-Pages"] = str(max(1, math.ceil(total / limit)))
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count, X-Total-Pages"
    return items


@router.get("/batches/{batch_id}", response_model=BatchDetailRead)
def get_detection_batch(
    batch_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return detection_service.get_batch(db, current_user=current_user, batch_id=batch_id)


@router.delete("/batches/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_detection_batch(
    batch_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    detection_service.delete_batch(db, current_user=current_user, batch_id=batch_id)


@router.post("/image", response_model=DetectionTaskRead, status_code=status.HTTP_201_CREATED)
def detect_image(
    file: Annotated[UploadFile, File(description="Single image for YOLO detection")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    conf: float = Query(default=0.25, ge=0.0, le=1.0),
    iou: float = Query(default=0.45, ge=0.0, le=1.0),
    model_key: str | None = Query(default=None, min_length=1, max_length=100),
):
    return detection_service.create_image_detection(
        db,
        current_user=current_user,
        file=file,
        conf=conf,
        iou=iou,
        model_key=model_key,
    )


@router.post("/video", response_model=DetectionTaskRead, status_code=status.HTTP_202_ACCEPTED)
def detect_video(
    file: Annotated[UploadFile, File(description="Single video for YOLO detection")],
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    conf: float = Query(default=0.25, ge=0.0, le=1.0),
    iou: float = Query(default=0.45, ge=0.0, le=1.0),
    model_key: str | None = Query(default=None, min_length=1, max_length=100),
):
    task = detection_service.create_video_detection_task(
        db,
        current_user=current_user,
        file=file,
        conf=conf,
        iou=iou,
        model_key=model_key,
    )
    background_tasks.add_task(
        detection_service.process_video_detection_task,
        task_id=task.id,
        conf=conf,
        iou=iou,
    )
    return task


@router.get("", response_model=list[DetectionTaskSummaryRead])
def list_detection_tasks(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    filter_status: Optional[str] = Query(default=None, alias="status", description="Filter by task status (completed/failed/processing/pending)"),
    source_type: Optional[str] = Query(default=None, description="Filter by source type (image/video)"),
    limit: int = Query(default=50, ge=1, le=200),
    page: int = Query(default=1, ge=1),
):
    total, items = detection_service.list_detections(
        db,
        current_user=current_user,
        status=filter_status,
        source_type=source_type,
        limit=limit,
        page=page,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Total-Pages"] = str(max(1, math.ceil(total / limit)))
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count, X-Total-Pages"
    return items


@router.get("/{detection_id}", response_model=DetectionTaskRead)
def get_detection_task(
    detection_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return detection_service.get_detection(db, current_user=current_user, detection_id=detection_id)


@router.delete("/{detection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_detection_task(
    detection_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    detection_service.delete_detection(db, current_user=current_user, detection_id=detection_id)

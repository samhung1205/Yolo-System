"""
Repository helpers for detection tasks, objects, and batches.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.detection_batch import DetectionBatch
from app.models.detection_object import DetectionObject
from app.models.detection_task import DetectionTask


def create_task(
    db: Session,
    *,
    user_id: int,
    source_type: str,
    source_filename: str,
    model_name: str,
    model_key: str | None = None,
    model_sha256: str | None = None,
    model_class_map_json: dict | None = None,
    confidence_threshold: float | None = None,
    iou_threshold: float | None = None,
    status: str = "processing",
    batch_id: int | None = None,
) -> DetectionTask:
    task = DetectionTask(
        user_id=user_id,
        source_type=source_type,
        source_filename=source_filename,
        model_name=model_name,
        model_key=model_key,
        model_sha256=model_sha256,
        model_class_map_json=model_class_map_json,
        confidence_threshold=confidence_threshold,
        iou_threshold=iou_threshold,
        status=status,
        batch_id=batch_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task: DetectionTask, **fields) -> DetectionTask:
    for key, value in fields.items():
        setattr(task, key, value)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def replace_task_objects(db: Session, task: DetectionTask, objects: list[dict]) -> None:
    db.query(DetectionObject).filter(DetectionObject.task_id == task.id).delete()
    for object_data in objects:
        db.add(DetectionObject(task_id=task.id, **object_data))
    db.commit()


def get_task(db: Session, task_id: int) -> DetectionTask | None:
    return (
        db.query(DetectionTask)
        .options(selectinload(DetectionTask.objects))
        .filter(DetectionTask.id == task_id)
        .first()
    )


def count_tasks(
    db: Session,
    *,
    user_id: int | None = None,
    status: str | None = None,
    source_type: str | None = None,
) -> int:
    query = db.query(DetectionTask.id)
    if user_id is not None:
        query = query.filter(DetectionTask.user_id == user_id)
    if status:
        query = query.filter(DetectionTask.status == status)
    if source_type:
        query = query.filter(DetectionTask.source_type == source_type)
    return query.count()


def list_tasks(
    db: Session,
    *,
    user_id: int | None = None,
    status: str | None = None,
    source_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[DetectionTask]:
    query = db.query(DetectionTask).options(selectinload(DetectionTask.objects))
    if user_id is not None:
        query = query.filter(DetectionTask.user_id == user_id)
    if status:
        query = query.filter(DetectionTask.status == status)
    if source_type:
        query = query.filter(DetectionTask.source_type == source_type)
    return (
        query.order_by(DetectionTask.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


def delete_task(db: Session, task: DetectionTask) -> None:
    db.delete(task)
    db.commit()


def create_batch(
    db: Session,
    *,
    user_id: int,
    name: str | None,
    model_name: str,
    model_key: str | None,
    model_sha256: str | None,
    confidence_threshold: float | None,
    iou_threshold: float | None,
    total_files: int,
    skipped_files: list[str] | None = None,
    status: str = "processing",
) -> DetectionBatch:
    batch = DetectionBatch(
        user_id=user_id,
        name=name,
        model_name=model_name,
        model_key=model_key,
        model_sha256=model_sha256,
        confidence_threshold=confidence_threshold,
        iou_threshold=iou_threshold,
        total_files=total_files,
        skipped_files=skipped_files or [],
        status=status,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def update_batch(db: Session, batch: DetectionBatch, **fields) -> DetectionBatch:
    for key, value in fields.items():
        setattr(batch, key, value)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def get_batch(db: Session, batch_id: int) -> DetectionBatch | None:
    return (
        db.query(DetectionBatch)
        .options(selectinload(DetectionBatch.tasks).selectinload(DetectionTask.objects))
        .filter(DetectionBatch.id == batch_id)
        .first()
    )


def count_batches(db: Session, *, user_id: int | None = None, status: str | None = None) -> int:
    query = db.query(DetectionBatch.id)
    if user_id is not None:
        query = query.filter(DetectionBatch.user_id == user_id)
    if status:
        query = query.filter(DetectionBatch.status == status)
    return query.count()


def list_batches(
    db: Session,
    *,
    user_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[DetectionBatch]:
    query = db.query(DetectionBatch)
    if user_id is not None:
        query = query.filter(DetectionBatch.user_id == user_id)
    if status:
        query = query.filter(DetectionBatch.status == status)
    return (
        query.order_by(DetectionBatch.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


def delete_batch(db: Session, batch: DetectionBatch) -> None:
    db.delete(batch)
    db.commit()


def get_pending_batch_tasks(db: Session, batch_id: int) -> list[DetectionTask]:
    return (
        db.query(DetectionTask)
        .filter(DetectionTask.batch_id == batch_id, DetectionTask.status == "pending")
        .order_by(DetectionTask.id)
        .all()
    )


def count_objects_by_class_for_batch(db: Session, batch_id: int) -> list[tuple[str, int]]:
    """Aggregate ``(class_name, count)`` across every task in the batch.

    Pure SQL GROUP BY so totals stay accurate even for the largest batches
    (no in-memory task/object list needs to be built for this query).
    """
    rows = (
        db.query(DetectionObject.class_name, func.count(DetectionObject.id))
        .join(DetectionTask, DetectionTask.id == DetectionObject.task_id)
        .filter(DetectionTask.batch_id == batch_id)
        .group_by(DetectionObject.class_name)
        .order_by(func.count(DetectionObject.id).desc())
        .all()
    )
    return [(class_name, int(count)) for class_name, count in rows]

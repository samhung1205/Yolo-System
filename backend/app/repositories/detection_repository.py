"""
Repository helpers for detection tasks and objects.
"""
from sqlalchemy.orm import Session, selectinload

from app.models.detection_object import DetectionObject
from app.models.detection_task import DetectionTask


def create_task(
    db: Session,
    *,
    user_id: int,
    source_type: str,
    source_filename: str,
    model_name: str,
    status: str = "processing",
) -> DetectionTask:
    task = DetectionTask(
        user_id=user_id,
        source_type=source_type,
        source_filename=source_filename,
        model_name=model_name,
        status=status,
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

"""
Batch detail carries deterministic per-class totals (DB GROUP BY), scoped to
the batch, so the batch page never has to ask the Agent to count.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.session import Base
from app.models import DetectionBatch, DetectionTask, User
from app.models.detection_object import DetectionObject
from app.services import detection_service


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    owner = User(id=1, username="alice", password_hash=hash_password("Abc12345"), is_active=True)
    other = User(id=2, username="bob", password_hash=hash_password("Abc12345"), is_active=True)
    session.add_all([owner, other])
    session.add_all(
        [
            DetectionBatch(id=1, user_id=1, model_name="m.pt", status="completed", total_files=3, processed_count=3),
            DetectionBatch(id=2, user_id=1, model_name="m.pt", status="completed", total_files=1, processed_count=1),
        ]
    )
    for task_id, batch_id in ((1, 1), (2, 1), (3, 1), (4, 2)):
        session.add(
            DetectionTask(
                id=task_id, user_id=1, batch_id=batch_id, source_type="image",
                source_filename=f"img_{task_id}.jpg", model_name="m.pt", status="completed",
            )
        )
    objects = [(1, "person"), (1, "person"), (1, "bus"), (2, "person"), (4, "ship")]
    for index, (task_id, class_name) in enumerate(objects):
        session.add(
            DetectionObject(
                task_id=task_id, object_index=index, class_id=0, class_name=class_name,
                confidence=0.9, bbox_x1=0, bbox_y1=0, bbox_x2=1, bbox_y2=1,
            )
        )
    session.commit()
    yield session
    session.close()


def test_batch_detail_includes_class_totals_for_that_batch_only(db):
    owner = db.get(User, 1)
    detail = detection_service.get_batch(db, current_user=owner, batch_id=1)

    assert [(row.class_name, row.count) for row in detail.class_counts] == [("person", 3), ("bus", 1)]
    # Task 3 completed with no objects: the zero-detection count stays derivable.
    assert [task.object_count for task in detail.tasks] == [3, 1, 0]


def test_batch_detail_class_totals_respect_ownership(db):
    other = db.get(User, 2)
    with pytest.raises(HTTPException) as exc:
        detection_service.get_batch(db, current_user=other, batch_id=1)
    assert exc.value.status_code == 403

"""Offline recovery preserves completed work and makes orphan status explicit."""
import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.models import DetectionBatch, DetectionTask, User

spec = importlib.util.spec_from_file_location('offline_recovery', Path(__file__).resolve().parents[1] / 'scripts/recover_interrupted.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


@pytest.fixture
def db():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        user=User(username='recovery',password_hash='unused',is_admin=False)
        session.add(user)
        session.flush()
        batch=DetectionBatch(user_id=user.id,model_name='test',status='processing',total_files=3)
        session.add(batch)
        session.flush()
        for status in ('completed','pending','failed'):
            session.add(DetectionTask(user_id=user.id,batch_id=batch.id,model_name='test',source_filename='test.png',status=status))
        session.add(DetectionTask(user_id=user.id,model_name='test',source_filename='test.mp4',source_type='video',status='processing'))
        session.commit()
        yield session
    engine.dispose()


def test_inventory_is_read_only(db):
    assert recovery.recover(db)=={'tasks':2,'batches':1,'applied':False}
    assert db.query(DetectionTask).filter_by(status='pending').count()==1
    assert db.query(DetectionBatch).one().status=='processing'


def test_apply_preserves_completed_results_and_recounts_batch(db):
    assert recovery.recover(db,True)['applied']
    assert db.query(DetectionTask).filter_by(status='completed').count()==1
    assert db.query(DetectionTask).filter_by(status='failed').count()==3
    batch=db.query(DetectionBatch).one()
    assert (batch.status,batch.processed_count,batch.failed_count)==('completed_with_errors',3,2)
    assert recovery.recover(db,True)['tasks']==0


def test_all_interrupted_batch_becomes_failed(db):
    for task in db.query(DetectionTask).filter(DetectionTask.batch_id.is_not(None)):
        task.status='pending'
    db.commit()
    recovery.recover(db,True)
    batch=db.query(DetectionBatch).one()
    assert (batch.status,batch.processed_count,batch.failed_count)==('failed',3,3)

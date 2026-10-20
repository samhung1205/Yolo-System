"""Offline maintenance: mark interrupted work failed, preserving completed results.

Default is a read-only inventory. --apply requires --backend-stopped and must
be run while the sole backend is stopped, through deploy/lab_recover.py.
No inference, file deletion, schema change or automatic resubmission.
"""
import argparse
import json
from sqlalchemy import func
from app.db.session import SessionLocal
from app.models import DetectionBatch, DetectionTask

MESSAGE = 'Interrupted by backend restart; please submit the original files again.'
ACTIVE = ('pending', 'processing')


def recover(db, apply=False):
    tasks = db.query(DetectionTask).filter(DetectionTask.status.in_(ACTIVE)).all()
    batches = db.query(DetectionBatch).filter(DetectionBatch.status.in_(ACTIVE)).all()
    report = {'tasks': len(tasks), 'batches': len(batches), 'applied': apply}
    if not apply:
        return report
    for task in tasks:
        task.status, task.error_message = 'failed', MESSAGE
    db.flush()
    for batch in batches:
        counts = dict(db.query(DetectionTask.status, func.count(DetectionTask.id))
                      .filter(DetectionTask.batch_id == batch.id).group_by(DetectionTask.status).all())
        batch.processed_count = sum(counts.values())
        batch.failed_count = counts.get('failed', 0)
        batch.status = ('failed' if batch.failed_count >= batch.total_files else
                        'completed_with_errors' if batch.failed_count else 'completed')
        batch.error_message = MESSAGE if batch.failed_count else None
    db.commit()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backend-stopped', action='store_true')
    args = parser.parse_args()
    if args.apply and not args.backend_stopped:
        parser.error('--apply requires --backend-stopped; use deploy/lab_recover.py')
    with SessionLocal() as db:
        print(json.dumps(recover(db, args.apply)))


if __name__ == '__main__':
    main()

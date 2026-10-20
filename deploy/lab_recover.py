"""Controlled recovery of orphan detection jobs, using the deployed image.

Inventory is read-only. --apply gracefully stops only the backend, marks
remaining pending/processing jobs failed, then starts it even on errors.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
from lab_compose_apply import Batch, need


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    batch = Batch()
    lock = os.open(batch.config / 'compose-apply.lock', os.O_RDONLY | os.O_NOFOLLOW)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    paused = False
    try:
        state = batch.inspect('sam-yolo-backend')
        need(state['project'] == 'sam-yolo' and state['service'] == 'backend', 'Backend ownership mismatch')
        if args.apply and state['running']:
            paused = True
            batch.docker('stop', '--time', '120', state['id'])
        need(not args.apply or not batch.inspect('sam-yolo-backend')['running'], 'Backend is still running')
        command = ['run', '--rm', '--network', 'host', '--user', state['user'],
            '--cpus', '1', '--memory', '512m', '-e', 'APP_ENV=production',
            '--mount', f'type=bind,source={batch.repo}/backend/.env,target=/opt/yolo/backend/.env,readonly',
            '--mount', f'type=bind,source={batch.repo}/backend/scripts/recover_interrupted.py,target=/opt/yolo/backend/recover_interrupted.py,readonly',
            state['image'], 'python', 'recover_interrupted.py']
        if args.apply:
            command += ['--apply', '--backend-stopped']
        result = json.loads(batch.docker(*command))
        print('PASS: interrupted job ' + json.dumps(result))
    finally:
        if paused:
            batch.docker('start', state['id'])
            batch.wait_backend()
        batch.session.close()
        os.close(lock)


if __name__ == '__main__':
    main()

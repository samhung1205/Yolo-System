"""Install an immutable stdlib backup worker; run once with sudo /usr/bin/python3.

Only this project's timer and files are changed. No daemon/host restarts,
sudoers changes, Docker group membership, firewall changes or pip installs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys

PREFIX = Path('/usr/local/lib/sam-yolo-maintenance')
CONFIG = Path('/etc/sam-yolo-maintenance.json')
ROOT = Path('/var/lib/sam-yolo-backups')
SERVICE = '''[Unit]
Description=YOLO private backup and isolated restore verification
After=network-online.target snap.docker.dockerd.service docker.service

[Service]
Type=oneshot
User=root
UMask=0077
ExecStart=/usr/bin/python3 -I /usr/local/lib/sam-yolo-maintenance/worker.py
ExecStopPost=/usr/bin/python3 -I /usr/local/lib/sam-yolo-maintenance/worker.py --recover
TimeoutStartSec=45min
TimeoutStopSec=180
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
CPUQuota=200%
MemoryMax=2G
StandardOutput=journal
StandardError=journal
'''


def need(value, message):
    if not value:
        raise RuntimeError(message)


def timer_text(at):
    need(re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', at), 'Use HH:MM in Asia/Taipei')
    return f'''[Unit]
Description=Daily YOLO backup at {at} Asia/Taipei

[Timer]
OnCalendar=*-*-* {at}:00 Asia/Taipei
Persistent=true
AccuracySec=1min
Unit=sam-yolo-backup.service

[Install]
WantedBy=timers.target
'''


def root_directory(path, group=0, mode=0o755):
    if path.exists() or path.is_symlink():
        info = path.lstat()
        need(path.is_dir() and not path.is_symlink() and info.st_uid == 0 and not info.st_mode & 0o022,
             'Existing directory is not protected: ' + str(path))
    else:
        path.mkdir(mode=mode)
    os.chown(path, 0, group)
    path.chmod(mode)


def write_owned(path, body, mode):
    if path.exists() or path.is_symlink():
        info = path.lstat()
        need(path.is_file() and not path.is_symlink() and info.st_uid == 0 and not info.st_mode & 0o022,
             'Refusing untrusted existing file')
    temporary = path.with_name(path.name + '.new-' + str(os.getpid()))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as output:
        output.write(body)
    os.chown(temporary, 0, 0)
    os.replace(temporary, path)


def command(*args):
    result = subprocess.run(list(args), capture_output=True, timeout=90)
    need(result.returncode == 0, 'Installation command failed: ' + Path(args[0]).name)
    return result.stdout.decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--account', default='sam')
    parser.add_argument('--at', default='23:30')
    parser.add_argument('--enable', action='store_true', help='Enable only after the initial backup succeeds')
    args = parser.parse_args()
    need(sys.platform == 'linux' and os.getuid() == 0, 'Use sudo /usr/bin/python3 on Ubuntu')
    account = pwd.getpwnam(args.account)
    need(account.pw_uid != 0, 'Select the project user')
    repo = args.repo.absolute()
    need(repo == repo.resolve() and repo.is_dir() and repo.stat().st_uid == account.pw_uid, 'Unexpected repository owner/path')
    worker = repo / 'deploy/lab_maintenance.py'
    need(worker.is_file() and not worker.is_symlink() and worker.stat().st_uid == account.pw_uid, 'Worker source missing')
    source = worker.read_bytes()
    compile(source, str(worker), 'exec')
    # A trusted system executable, never the user's conda Python or wrapper.
    docker = shutil.which('docker', path='/usr/bin:/snap/bin:/usr/local/bin')
    need(docker in ('/usr/bin/docker', '/snap/bin/docker'), 'Unsupported Docker executable path')
    configuration = {'repo': str(repo), 'home': account.pw_dir, 'uid': account.pw_uid,
                     'gid': account.pw_gid, 'docker': docker, 'keep': 7, 'at': args.at,
                     'worker_sha256': hashlib.sha256(source).hexdigest()}
    ollama=pwd.getpwnam('ollama')
    need(ollama.pw_uid!=0,'Ollama must have a dedicated non-root user')
    models=Path(ollama.pw_dir)/'.ollama/models'
    need(models.is_dir() and models.resolve()==models,'Native Ollama model store missing or symlinked')
    configuration.update(ollama_uid=ollama.pw_uid,ollama_gid=ollama.pw_gid,ollama_models=str(models))
    timer = timer_text(args.at).encode()
    root_directory(PREFIX)
    root_directory(ROOT, account.pw_gid, 0o750)
    if CONFIG.exists():
        info = CONFIG.lstat()
        need(CONFIG.is_file() and not CONFIG.is_symlink() and info.st_uid == 0 and not info.st_mode & 0o022,
             'Untrusted existing config')
        old = json.loads(CONFIG.read_text())
        need(all(old.get(k) == configuration[k] for k in ('repo','home','uid','gid','docker')), 'Existing installation belongs to a different project')
    write_owned(PREFIX / 'worker.py', source, 0o644)
    write_owned(CONFIG, json.dumps(configuration, indent=2).encode(), 0o600)
    write_owned(Path('/etc/systemd/system/sam-yolo-backup.service'), SERVICE.encode(), 0o644)
    write_owned(Path('/etc/systemd/system/sam-yolo-backup.timer'), timer, 0o644)
    command('/usr/bin/systemd-analyze', 'verify', '/etc/systemd/system/sam-yolo-backup.service', '/etc/systemd/system/sam-yolo-backup.timer')
    command('/usr/bin/systemctl', 'daemon-reload')
    if args.enable:
        # Success is evaluated from the installed worker's latest snapshot.
        manifests = sorted(ROOT.glob('*/manifest.json'), reverse=True)
        latest=json.loads(manifests[0].read_text()) if manifests else {}
        need(latest.get('success') is True and latest.get('restore_verified') is True
             and latest.get('worker_sha256')==configuration['worker_sha256'], 'Initial verified backup required before enabling timer')
        command('/usr/bin/systemctl', 'enable', '--now', 'sam-yolo-backup.timer')
    print('PASS: root-owned backup installation; ' + ('timer enabled' if args.enable else 'timer not enabled yet'))
    print('Schedule: ' + args.at + ' Asia/Taipei; keep 7 verified snapshots; original baseline untouched')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('FAIL: ' + (str(exc) if type(exc) is RuntimeError else type(exc).__name__))
        raise SystemExit(1)

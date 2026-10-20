"""Apply a checksummed Phase 6 source bundle and run the single lab batch.

Run as sam with the yolo-backend environment, after sudo -v.
Checks every preimage first, preserves replaced sources privately, and never
includes .env, model bytes, user media or credentials in the source bundle.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys


def need(value,message):
    if not value:raise RuntimeError(message)


def digest(data):
    return hashlib.sha256(data.replace(b'\r\n',b'\n')).hexdigest()


def allowed(name):
    path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or any(p.startswith('.env') for p in path.parts):return False
    if name in ('README.md','AGENTS.md','DEPLOY.md','docs/roadmap.md','backend/pytest.ini','.github/workflows/verify.yml'):return True
    if name.startswith('docs/lab-') and path.suffix=='.md':return True
    if name.startswith('deploy/') and len(path.parts)==2:
        return path.suffix in ('.py','.yaml','.lock','.conf','.dockerignore') or path.name in ('backend.Dockerfile','public.Dockerfile','Caddyfile.public')
    if name.startswith('deploy/tests/') and len(path.parts)==3 and path.suffix=='.py':return True
    if name.startswith('backend/tests/') and len(path.parts)==3 and path.suffix=='.py':return True
    if name=='backend/scripts/recover_interrupted.py':return True
    if name in ('web-frontend/package.json','web-frontend/package-lock.json','web-frontend/vite.config.js','web-frontend/index.html'):return True
    if name.startswith('web-frontend/src/') and path.suffix in ('.js','.jsx','.css','.svg'):return True
    return False


def plan(repo,package):
    manifest=json.loads((package/'manifest.json').read_text())
    need(manifest.get('release')=='phase6-final-20261021','Wrong release')
    result=[]
    for name,entry in manifest['files'].items():
        need(allowed(name),'Unexpected bundle path')
        source=package/'payload'/name
        need(source.is_file() and not source.is_symlink(),'Missing source')
        body=source.read_bytes()
        need(hashlib.sha256(body).hexdigest()==entry['sha256'],'Bundle checksum mismatch')
        target=repo/name
        for path in (target,*target.parents):
            if path==repo:break
            need(not path.is_symlink(),'Symlink in destination')
        previous=target.read_bytes() if target.exists() else None
        current=digest(previous) if previous is not None else None
        need(current in entry['before'] or current==digest(body),'伺服器來源已變更，未覆寫：'+name)
        if previous!=body:result.append((name,target,previous,body))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path.home()/'apps/Yolo_system')
    args=parser.parse_args()
    need(sys.platform=='linux' and os.getuid()!=0,'請以 yolo-backend 環境執行，勿 sudo python')
    os.umask(0o077)
    repo=args.repo.resolve()
    lock=os.open(Path.home()/'.config/yolo-system/compose-apply.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    need(os.fstat(lock).st_uid==os.getuid(),'Deployment lock belongs to another user')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    changes=plan(repo,Path(__file__).resolve().parent)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+f'-{os.getpid()}'
    backup=Path.home()/'.config/yolo-system/releases'/('finalize-source-'+stamp)
    backup.mkdir(mode=0o700)
    print('來源備份：'+str(backup),flush=True)
    for name,target,previous,body in changes:
        if previous is not None:
            saved=backup/name
            saved.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            saved.write_bytes(previous)
            saved.chmod(0o600)
    # Every destination was validated before any application source changes.
    for name,target,previous,body in changes:
        target.parent.mkdir(parents=True,exist_ok=True)
        need((target.read_bytes() if target.exists() else None)==previous,'Source changed during application')
        temporary=target.with_name(target.name+'.phase6-'+stamp)
        with temporary.open('xb') as output:output.write(body)
        temporary.chmod(0o644)
        os.replace(temporary,target)
    print(f'PASS: {len(changes)} source files updated; previous files: {backup}',flush=True)
    os.close(lock)
    return subprocess.run([sys.executable,str(repo/'deploy/lab_finalize.py')],cwd=repo).returncode


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print('FAIL: '+(str(exc) if type(exc) is RuntimeError else type(exc).__name__))
        raise SystemExit(1)

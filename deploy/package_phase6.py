"""Package Phase 6 sources with known preimages, never models or private data."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
from apply_phase6 import allowed,digest

ROOT=Path(__file__).resolve().parents[1]


def package():
    names=[]
    for folder in ('deploy','backend/tests','backend/scripts','web-frontend','docs','.github'):
        names += [p.relative_to(ROOT).as_posix() for p in (ROOT/folder).rglob('*') if p.is_file() and allowed(p.relative_to(ROOT).as_posix())]
    names += ['README.md','AGENTS.md','DEPLOY.md','backend/pytest.ini']
    names=sorted(set(names))
    old={}
    prior=ROOT/'deploy/out/yolo-public-update-20261020.tar.gz'
    if prior.exists():
        with tarfile.open(prior) as archive:
            for member in archive:
                if member.isfile() and '/payload/' in member.name:
                    old[member.name.split('/payload/',1)[1]]=digest(archive.extractfile(member).read())
    manifest={'release':'phase6-final-20261021','files':{}}
    payload={}
    for name in names:
        path=ROOT/name
        if path.is_symlink():raise ValueError('Symlink in source')
        data=path.read_bytes()
        previous=subprocess.run(['git','show','HEAD:'+name],cwd=ROOT,capture_output=True)
        before={None,digest(data)}
        if previous.returncode==0:before.add(digest(previous.stdout))
        if name in old:before.add(old[name])
        manifest['files'][name]={'sha256':hashlib.sha256(data).hexdigest(),'before':sorted(before,key=lambda value:value or '')}
        payload['payload/'+name]=data
    # Historical backup contains the pre-update deployment helpers, no private
    # contents are copied into this source bundle; only matching source hashes.
    original=Path('/Users/SAM/Desktop/Yolo-system-backups/20261020T075232Z-2550504/files.tar.gz')
    if original.exists():
        with tarfile.open(original) as archive:
            for member in archive:
                if member.isfile() and member.name in manifest['files']:
                    value=digest(archive.extractfile(member).read())
                    hashes=manifest['files'][member.name]['before']
                    if value not in hashes:hashes.append(value)
    payload['manifest.json']=json.dumps(manifest,indent=2,sort_keys=True).encode()
    payload['apply.py']=(ROOT/'deploy/apply_phase6.py').read_bytes()
    target=ROOT/'deploy/out/yolo-phase6-final-20261021.tar.gz'
    target.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(target,'w:gz',compresslevel=6) as archive:
        for name,data in sorted(payload.items()):
            info=tarfile.TarInfo('yolo-phase6-final-20261021/'+name)
            info.size=len(data);info.mode=0o644;info.mtime=0
            archive.addfile(info,io.BytesIO(data))
    print(str(target))
    print('SHA-256: '+hashlib.sha256(target.read_bytes()).hexdigest())
    print('Source files: '+str(len(names)))


if __name__=='__main__':package()

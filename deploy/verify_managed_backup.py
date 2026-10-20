"""Read-only verification of a downloaded managed snapshot and its version caches.

Usage: python3 deploy/verify_managed_backup.py BACKUP_ROOT SNAPSHOT_NAME
No extraction, SQL output, secret output, Docker or server connection.
"""
import argparse
import gzip
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
from verify_downloaded_backup import need, regular, stream_hash, InvalidBackup


def verify(root, name):
    need(re.fullmatch(r'\d{8}T\d{6}Z-[0-9a-f]{8}', name), '快照名稱不合法')
    folder=root/name
    need(root.is_dir() and not root.is_symlink() and folder.is_dir() and not folder.is_symlink(), '備份目錄不合法')
    report=json.loads(regular(folder/'manifest.json').read_text())
    need(report.get('kind')=='sam-yolo-managed-v1' and report.get('success') is True
         and report.get('restore_verified') is True,'快照尚未通過隔離還原')
    need(set(report['artifacts'])=={'database.sql.gz','files.tar.gz','caddy-data.tar.gz'},'備份產物不完整')
    for artifact,expected in report['artifacts'].items():
        with regular(folder/artifact).open('rb') as stream:
            need(stream_hash(stream)==expected,'壓縮產物 SHA-256 不符')
    with gzip.open(folder/'database.sql.gz','rb') as stream:
        need(stream_hash(stream)==report['database_sql_sha256'],'完整 SQL SHA-256 不符')
    seen=set()
    with tarfile.open(folder/'files.tar.gz') as archive:
        for member in archive:
            path=PurePosixPath(member.name)
            need(member.isfile() and not path.is_absolute() and '..' not in path.parts
                 and member.name in report['files'] and member.name not in seen,'檔案壓縮內容不符')
            expected=report['files'][member.name]
            with archive.extractfile(member) as stream:
                need(member.size==expected['size'] and stream_hash(stream)==expected['sha256'],'備份檔案 SHA-256 不符')
            seen.add(member.name)
    need(seen==set(report['files']),'備份檔案遺失')
    caches=[(value,'images') for value in report['images'].values()]+[(report['native_models'],'models')]
    need(report['images'] and report['native_models'],'image／模型快取清單遺失')
    for entry,kind in caches:
        need(re.fullmatch(kind+r'/[0-9a-f]{64}\.tar\.gz',entry['path']),'快取路徑不合法')
        need(not (root/kind).is_symlink(),'快取目錄不能是 symlink')
        with regular(root/entry['path']).open('rb') as stream:
            need(stream_hash(stream)==entry['sha256'],'image／模型快取 SHA-256 不符或未下載')
    return {'files':len(seen),'version_caches':len(caches),'snapshot':name}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('snapshot')
    args=parser.parse_args()
    try:
        print('PASS: '+json.dumps(verify(args.root.expanduser(),args.snapshot),ensure_ascii=False))
    except Exception as exc:
        print('FAIL: '+(str(exc) if isinstance(exc,InvalidBackup) else type(exc).__name__))
        raise SystemExit(1)

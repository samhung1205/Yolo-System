"""Verify a downloaded backup against its successful isolated-restore report.

Standard library only. Reads/hashes SQL and archive members without extracting
private settings, printing contents, contacting a server or running MySQL.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile


class InvalidBackup(Exception):
    pass


def need(condition, message):
    if not condition:
        raise InvalidBackup(message)


def stream_hash(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def regular(path):
    need(path.is_file() and not path.is_symlink(), "缺少必要的一般檔案，或來源為 symlink")
    return path


def verify(source, success):
    need(source.is_dir() and not source.is_symlink() and success.is_dir() and not success.is_symlink(),
         "請指定下載後的原始備份與成功報告兩個目錄")
    original = json.loads(regular(source / "manifest.json").read_text())
    report = json.loads(regular(success / "manifest.json").read_text())
    need(report.get("success") is True and report.get("restore_verified") is True, "第二個目錄不是已通過的隔離還原報告")
    need(Path(report.get("source_backup", "")).name == source.name, "成功報告指向其他原始備份")
    for key in ("artifacts", "files", "database_sql_sha256", "database_defaults"):
        need(original.get(key) is not None and original[key] == report.get(key), "原始 manifest 與成功報告的產物基準不同")
    need(isinstance(original["files"], dict) and original["files"], "備份檔案清單缺少")
    for name in ("database.sql.gz", "files.tar.gz"):
        with regular(source / name).open("rb") as stream:
            need(stream_hash(stream) == original["artifacts"].get(name), "下載的壓縮產物 SHA-256 不符")
    with gzip.open(source / "database.sql.gz", "rb") as stream:
        need(stream_hash(stream) == original["database_sql_sha256"], "SQL 解壓後 SHA-256 不符")
    seen = set()
    total = 0
    with tarfile.open(source / "files.tar.gz", "r:gz") as archive:
        for member in archive:
            relative = PurePosixPath(member.name)
            need(member.isfile() and not relative.is_absolute() and ".." not in relative.parts
                 and member.name in original["files"] and member.name not in seen, "檔案壓縮內容含非預期或不安全項目")
            expected = original["files"][member.name]
            need(member.size == expected["size"], "下載的備份檔案大小不符")
            with archive.extractfile(member) as stream:
                need(stream_hash(stream) == expected["sha256"], "下載的備份檔案 SHA-256 不符")
            seen.add(member.name)
            total += member.size
    need(seen == set(original["files"]), "下載的備份檔案不完整")
    return {"files": len(seen), "bytes": total, "source": source.name, "restore_report": success.name}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("success", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.source.expanduser(), args.success.expanduser())
    except (InvalidBackup, OSError, ValueError, KeyError, tarfile.TarError) as exc:
        message = str(exc) if isinstance(exc, InvalidBackup) else type(exc).__name__
        print("FAIL: " + message)
        return 1
    print("PASS: Mac 副本壓縮產物／完整 SQL／所有備份檔案 SHA-256 與成功還原報告一致")
    print(json.dumps(result, ensure_ascii=False))
    print("僅驗證下載副本完整性；本輪未重新執行 MySQL 還原。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

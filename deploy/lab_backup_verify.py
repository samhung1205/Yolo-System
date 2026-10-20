"""Create a private lab backup and verify an isolated MySQL/file restore.

Run as sam after sudo -v while the site is idle. Production MySQL is never
stopped or restored over. Only the backend pauses while DB/media are captured.
"""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from itertools import zip_longest

from lab_compose_apply import Batch, Failed, need

MYSQL_IMAGE = "sha256:4aae07a2c195abb9b3e92449443b39b51212f555a35ff8f93da0e82683f45de8"
DUMP = ('export MYSQL_PWD="$MYSQL_PASSWORD"; exec mysqldump '
        '--host=127.0.0.1 --protocol=TCP --user="$MYSQL_USER" '
        '--single-transaction --quick --no-tablespaces --set-gtid-purged=OFF '
        '--hex-blob --default-character-set=utf8mb4 --order-by-primary '
        '--skip-comments --skip-dump-date "$MYSQL_DATABASE"')
MYSQL = ('export MYSQL_PWD="$MYSQL_PASSWORD"; exec mysql '
         '--host=127.0.0.1 --protocol=TCP --user="$MYSQL_USER" '
         '--batch --skip-column-names --default-character-set=utf8mb4 '
         '"$MYSQL_DATABASE" "$@"')


def keep_sudo_alive(stop):
    """Refresh only the already-authorized sudo timestamp while this batch runs."""
    while not stop.wait(45):
        try:
            result = subprocess.run(["sudo", "-n", "-v"], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            if result.returncode:
                return
        except (OSError, subprocess.TimeoutExpired):
            return


def private_write(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


REDUNDANT_UTF8MB4 = re.compile(
    rb"^( +`[A-Za-z0-9_]+` (?:char\([0-9]+\)|varchar\([0-9]+\)|tinytext|text|mediumtext|longtext))"
    rb" CHARACTER SET utf8mb4(?= COLLATE utf8mb4_[A-Za-z0-9_]+(?:[ ,\r\n]|$))")


def normalized_sql_hash(path):
    """Account only for MySQL #110825; preserve every other SQL byte.

    COLLATE utf8mb4_* already determines CHARACTER SET utf8mb4. MySQL may
    redundantly print the latter after a restore. Limit this rule to the
    beginning of supported character-column definitions inside CREATE TABLE;
    never rewrite INSERT values, defaults, table options or collation names.
    https://bugs.mysql.com/bug.php?id=110825
    https://dev.mysql.com/doc/refman/8.4/en/charset-column.html
    """
    checksum = hashlib.sha256()
    clauses = 0
    in_table = False
    with gzip.open(path, "rb") as handle:
        for line in handle:
            if re.fullmatch(rb"CREATE TABLE `[A-Za-z0-9_]+` \(\r?\n", line):
                in_table = True
            if in_table:
                line, count = REDUNDANT_UTF8MB4.subn(rb"\1", line, count=1)
                clauses += count
                if line.startswith(b")"):
                    in_table = False
            checksum.update(line)
    return {"sha256": checksum.hexdigest(), "redundant_utf8mb4_clauses": clauses}


def sql_difference(source, restored):
    """Describe differences without disclosing SQL literals or user data."""
    summary = {"differing_lines": 0, "source_lines": 0, "restored_lines": 0}
    table = None
    section = "session"
    with gzip.open(source, "rb") as left, gzip.open(restored, "rb") as right:
        for number, (before, after) in enumerate(zip_longest(left, right), 1):
            summary["source_lines"] += before is not None
            summary["restored_lines"] += after is not None
            if before:
                match = re.match(rb"(?:CREATE TABLE|INSERT INTO|LOCK TABLES|DROP TABLE IF EXISTS) `([A-Za-z0-9_]+)`", before)
                if match:
                    table = match[1].decode("ascii")
                    section = "data" if before.startswith((b"INSERT", b"LOCK")) else "schema"
            if before == after:
                continue
            summary["differing_lines"] += 1
            if "first_difference" not in summary:
                detail = {"line": number, "table": table, "section": section,
                          "source_bytes": len(before or b""), "restored_bytes": len(after or b"")}
                if section == "schema":
                    definitions = []
                    for line in (before, after):
                        column = re.match(rb"\s+`([A-Za-z0-9_]+)` ([A-Za-z0-9_]+)", line or b"")
                        key = re.match(rb"\s+(UNIQUE KEY|KEY|CONSTRAINT) `([A-Za-z0-9_]+)`", line or b"")
                        definitions.append({"column": column[1].decode(), "type": column[2].decode()} if column
                                           else {"kind": key[1].decode(), "name": key[2].decode()} if key else None)
                    detail["definition_tokens"] = definitions
                # Only fixed table-option tokens and integers are safe to echo.
                if all(value and value.startswith(b") ENGINE=") for value in (before, after)):
                    detail["table_options"] = {}
                    for key, pattern in (("engine", rb"ENGINE=([A-Za-z0-9_]+)"),
                                         ("auto_increment", rb"AUTO_INCREMENT=([0-9]+)"),
                                         ("charset", rb"CHARSET=([A-Za-z0-9_]+)"),
                                         ("collation", rb"COLLATE=([A-Za-z0-9_]+)")):
                        pair = [re.search(pattern, line) for line in (before, after)]
                        detail["table_options"][key] = [m[1].decode("ascii") if m else None for m in pair]
                summary["first_difference"] = detail
    return summary


def capture_files(archive, sources):
    """Archive regular files only; record hashes without exposing contents."""
    manifest = {}
    descriptor = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output, tarfile.open(fileobj=output, mode="w:gz", compresslevel=1, dereference=True) as tar:
        for name, source in sorted(sources.items()):
            need(not source.is_symlink() and source.is_file(), "備份來源必須是一般檔案，不接受 symlink")
            before = source.stat()
            info = tar.gettarinfo(str(source), arcname=name)
            checksum = hashlib.sha256()

            class Reader:
                def __init__(self, handle): self.handle = handle
                def read(self, size=-1):
                    chunk = self.handle.read(size)
                    checksum.update(chunk)
                    return chunk

            with source.open("rb") as handle:
                tar.addfile(info, Reader(handle))
            after = source.stat()
            need((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), "備份期間來源檔案被修改")
            manifest[name] = {"sha256": checksum.hexdigest(), "size": info.size}
    return manifest


def verify_files(archive, destination, manifest):
    """Restore into a new private directory; no links or traversal accepted."""
    seen = set()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            relative = PurePosixPath(member.name)
            need(member.isfile() and not relative.is_absolute() and ".." not in relative.parts
                 and member.name in manifest and member.name not in seen, "備份內有不合法或重複路徑")
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            source = tar.extractfile(member)
            with os.fdopen(descriptor, "wb") as output, source:
                shutil.copyfileobj(source, output)
            expected = manifest[member.name]
            need(target.stat().st_size == expected["size"] and file_hash(target) == expected["sha256"], "還原檔案雜湊不符")
            seen.add(member.name)
    need(seen == set(manifest), "還原檔案不完整")


class Backup(Batch):
    def __init__(self, existing=None):
        super().__init__()
        self.step = "backup.preflight"
        self.root = Path.home() / ".local/share/yolo-system/backups"
        self.output = self.root / self.stamp
        self.work = self.output / ".work"
        self.existing = existing
        self.archive_root = self.output
        self.paused = False
        self.temp_id = None
        self.volume = None
        self.backend_id = None
        self.database = None
        self.report = {"success": False, "checks": [], "same_host_only": True}

    def mysql(self, container, sql):
        return self.docker("exec", container, "sh", "-c", MYSQL, "mysql-client", "-e", sql)

    def preflight(self):
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        metadata = self.root.stat()
        need(metadata.st_uid == os.getuid() and not metadata.st_mode & 0o077, "備份目錄必須是自己的私人目錄（0700）")
        self.output.mkdir(mode=0o700)
        self.work.mkdir(mode=0o700)
        backend = self.inspect("sam-yolo-backend")
        need(backend["running"] and backend["project"] == "sam-yolo" and backend["service"] == "backend", "請先完成 Compose 納管")
        self.backend_id = backend["id"]
        self.database = self.inspect("sam-yolo-mysql")
        need(self.database["running"] and self.database["image"] == MYSQL_IMAGE
             and any(m.get("Name") == "sam-yolo-mysql-data" and m["Destination"] == "/var/lib/mysql"
                     for m in self.database["mounts"]), "正式 MySQL image／volume 不符")
        self.health(8000)
        self.health()
        identity = self.docker("exec", "sam-yolo-mysql", "sh", "-c", 'printf "%s|%s" "$MYSQL_DATABASE" "$MYSQL_USER"')
        need(identity == "yolo|yolo_app", "MySQL schema／專用帳號與已驗證設定不符")
        if self.existing is not None:
            self.load_existing()
            self.passed("既有備份／產物 SHA-256／正式服務正常；本輪不停止 backend")
            return
        values = self.mysql("sam-yolo-mysql", "SELECT COUNT(*) FROM detection_tasks WHERE status IN ('pending','processing');"
            "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE' AND ENGINE<>'InnoDB';"
            "SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE();"
            "SELECT COUNT(*) FROM information_schema.EVENTS WHERE EVENT_SCHEMA=DATABASE();"
            "SELECT COALESCE(SUM(DATA_LENGTH+INDEX_LENGTH),0) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE();").splitlines()
        need(len(values) == 5 and values[:4] == ["0"] * 4, "仍有進行中偵測，或資料庫有本流程未支援的儲存引擎／routines／events")
        defaults = self.mysql("sam-yolo-mysql", "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=DATABASE();").strip().split("\t")
        need(len(defaults) == 2 and all(re.fullmatch(r"[a-zA-Z0-9_]+", value) for value in defaults), "無法辨識 schema 字元集／collation")
        self.report["database_defaults"] = dict(zip(("charset", "collation"), defaults))
        self.sources = self.collect_sources()
        total = sum(p.stat().st_size for p in self.sources.values())
        need(shutil.disk_usage(self.root).free > 3 * total + 3 * int(values[4]) + 256 * 1024**2,
             "可用空間不足以備份及隔離還原")
        self.report.update(mysql_container_id=self.database["id"], mysql_image=MYSQL_IMAGE,
                           source_bytes=total, source_files=len(self.sources))
        self.passed("來源／InnoDB／無進行中偵測／私人設定／磁碟空間")

    def load_existing(self):
        source = Path(self.existing).expanduser()
        need(not source.is_symlink(), "既有備份不能是 symlink")
        source = source.resolve()
        need(source.parent == self.root.resolve() and source != self.output
             and source.is_dir(), "請指定私人 backups 內既有的時間戳目錄")
        metadata = source.stat()
        need(metadata.st_uid == os.getuid() and not metadata.st_mode & 0o077, "既有備份目錄必須是自己的私人目錄")
        manifest = source / "manifest.json"
        need(manifest.is_file() and not manifest.is_symlink() and manifest.stat().st_size < 64 * 1024**2,
             "既有備份 manifest 缺少或不合法")
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        need(previous.get("mysql_image") == MYSQL_IMAGE and isinstance(previous.get("files"), dict), "既有備份不是本流程的 MySQL／檔案快照")
        for name in ("database.sql.gz", "files.tar.gz"):
            path = source / name
            expected = previous.get("artifacts", {}).get(name)
            need(path.is_file() and not path.is_symlink() and file_hash(path) == expected, "既有備份產物雜湊不符，拒絕還原")
        need(re.fullmatch(r"[0-9a-f]{64}", previous.get("database_sql_sha256", "")), "既有 SQL 雜湊缺少")
        defaults = previous.get("database_defaults", {})
        need(all(re.fullmatch(r"[A-Za-z0-9_]+", defaults.get(key, "")) for key in ("charset", "collation")), "既有 schema 字元集／collation 缺少")
        required = 2 * sum(item["size"] for item in previous["files"].values()) + 256 * 1024**2
        with gzip.open(source / "database.sql.gz", "rb") as handle:
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                required += 4 * len(chunk)
        need(digest.hexdigest() == previous["database_sql_sha256"], "既有 SQL 解壓後雜湊不符")
        need(shutil.disk_usage(self.root).free > required, "空間不足以隔離重驗")
        self.archive_root = source
        self.report.update({key: previous[key] for key in ("files", "artifacts", "database_sql_sha256", "database_defaults")})
        self.report["source_backup"] = str(source)

    def collect_sources(self):
        sources = {}
        for folder in ("backend/static", "backend/pt", "web-frontend/dist", "deploy"):
            root = self.repo / folder
            need(root.is_dir() and not root.is_symlink(), "缺少備份必要目錄")
            for path in root.rglob("*"):
                need(not path.is_symlink(), "備份來源包含 symlink，請先查明")
                if path.is_file() and "__pycache__" not in path.parts:
                    sources[path.relative_to(self.repo).as_posix()] = path
        for name, path in (("backend.env", self.repo / "backend/.env"),
                           ("mysql.env", self.config / "mysql.env"),
                           ("nginx.lab.conf", self.config / "nginx.lab.conf"),
                           ("compose.env", self.config / "compose.env")):
            need(path.is_file() and not path.is_symlink(), "缺少私人設定備份來源")
            sources["private/" + name] = path
        return sources

    def transfer(self, container, *, archive=None, restore=False):
        """Stream SQL through private files, never command-line passwords."""
        command = ["sudo", "-n", "docker", "exec"]
        if restore:
            need(container == self.temp_id and container is not None, "拒絕向正式資料庫執行還原")
            command += ["-i", container, "sh", "-c", MYSQL, "mysql-client"]
        else:
            command += [container, "sh", "-c", DUMP]
        checksum = hashlib.sha256()
        with tempfile.TemporaryFile(dir=self.work) as errors:
            process = subprocess.Popen(command, env=self.env, stdin=subprocess.PIPE if restore else subprocess.DEVNULL,
                stdout=subprocess.DEVNULL if restore else subprocess.PIPE, stderr=errors)
            timer = threading.Timer(600, process.kill)
            timer.daemon = True
            timer.start()
            try:
                if restore:
                    with gzip.open(archive, "rb") as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            process.stdin.write(chunk)
                    process.stdin.close()
                else:
                    output = gzip.open(archive, "xb", compresslevel=1) if archive else None
                    try:
                        if archive:
                            archive.chmod(0o600)
                        for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
                            checksum.update(chunk)
                            if output:
                                output.write(chunk)
                    finally:
                        if output:
                            output.close()
                        process.stdout.close()
                code = process.wait(timeout=30)
                if code:
                    errors.seek(0)
                    details = errors.read(64 * 1024).decode("utf-8", errors="replace")
                    private_write(self.output / "sql-error.log", details)
                    codes = re.findall(r"(?:ERROR|error:)\s*(\d+)", details, flags=re.I)
                    self.report["sql_error_codes"] = codes
                    raise Failed(f"SQL {'還原' if restore else '匯出'}失敗（exit {code}，MySQL codes={codes}）；細節存私人 sql-error.log")
            finally:
                timer.cancel()
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
        return checksum.hexdigest()

    def capture(self):
        self.step = "backup.capture"
        need(self.inspect("sam-yolo-backend")["id"] == self.backend_id, "backend 身分已改變")
        self.paused = True  # Also recover when stop fails after stopping.
        try:
            self.docker("stop", "--time", "120", self.backend_id)
            need(self.mysql("sam-yolo-mysql", "SELECT COUNT(*) FROM detection_tasks WHERE status IN ('pending','processing');").strip() == "0",
                 "停止前有新偵測工作進入；保留現況，請待工作完成再備份")
            self.sources = self.collect_sources()
            self.report.update(source_bytes=sum(p.stat().st_size for p in self.sources.values()),
                               source_files=len(self.sources))
            self.report["database_sql_sha256"] = self.transfer("sam-yolo-mysql", archive=self.output / "database.sql.gz")
            self.report["files"] = capture_files(self.output / "files.tar.gz", self.sources)
            self.report["artifacts"] = {name: file_hash(self.output / name) for name in ("database.sql.gz", "files.tar.gz")}
        finally:
            self.docker("start", self.backend_id)
            self.paused = False
        self.passed("一致性 SQL／媒體／模型／前端／設定備份；backend 已啟動")

    def restore(self):
        self.step = "backup.restore"
        envfile = self.work / "restore.env"
        private_write(envfile, "MYSQL_DATABASE=yolo\nMYSQL_USER=yolo_app\nMYSQL_PASSWORD=" + secrets.token_hex(24)
                      + "\nMYSQL_ROOT_PASSWORD=" + secrets.token_hex(24) + "\n")
        self.volume = "sam-yolo-restore-" + self.stamp.lower()
        need(self.volume != "sam-yolo-mysql-data", "拒絕使用正式 volume")
        self.docker("volume", "create", "--label", "sam.yolo.restore=" + self.stamp, self.volume)
        labels = json.loads(self.docker("volume", "inspect", "--format", "{{json .Labels}}", self.volume)) or {}
        need(labels.get("sam.yolo.restore") == self.stamp, "暫存 volume 歸屬不符，拒絕掛入還原")
        name = "sam-yolo-restore-" + self.stamp.lower()
        created = self.docker("create", "--name", name, "--label", "sam.yolo.restore=" + self.stamp,
            "--network", "none", "--cpus", "2", "--memory", "2g", "--log-driver", "json-file",
            "--log-opt", "max-size=5m", "--log-opt", "max-file=1", "--env-file", str(envfile),
            "--mount", "type=volume,source=" + self.volume + ",target=/var/lib/mysql",
            MYSQL_IMAGE, "--character-set-server=" + self.report["database_defaults"]["charset"],
            "--collation-server=" + self.report["database_defaults"]["collation"]).strip()
        need(len(created) == 64 and all(c in "0123456789abcdef" for c in created), "暫存容器 ID 不符")
        self.temp_id = created
        self.docker("start", self.temp_id)
        until = time.monotonic() + 120
        while True:
            try:
                if self.mysql(self.temp_id, "SELECT 1;").strip() == "1":
                    self.report.pop("docker_error", None)
                    break
            except Failed:
                pass
            need(time.monotonic() < until, "暫存 MySQL 120 秒內未就緒")
            time.sleep(2)
        self.transfer(self.temp_id, archive=self.archive_root / "database.sql.gz", restore=True)
        restored_sql = self.output / "restored.sql.gz"
        restored_hash = self.transfer(self.temp_id, archive=restored_sql)
        self.report["restored_sql_sha256"] = restored_hash
        raw_matches = restored_hash == self.report["database_sql_sha256"]
        sql_matches = raw_matches
        self.report["sql_verification"] = {"method": "exact_sql_bytes", "raw_equal": raw_matches}
        if not raw_matches:
            source_normalized = normalized_sql_hash(self.archive_root / "database.sql.gz")
            restored_normalized = normalized_sql_hash(restored_sql)
            sql_matches = source_normalized["sha256"] == restored_normalized["sha256"]
            self.report["sql_verification"].update(method="mysql_110825_redundant_utf8mb4_only",
                source_normalized=source_normalized, restored_normalized=restored_normalized,
                equivalent=sql_matches)
            self.report["sql_difference"] = sql_difference(self.archive_root / "database.sql.gz", restored_sql)
            if sql_matches:
                self.passed("SQL 僅有等價 utf8mb4 字元集表示差異；其餘完整 SQL 位元組一致"
                    f"（冗餘標記：來源 {source_normalized['redundant_utf8mb4_clauses']}／還原 {restored_normalized['redundant_utf8mb4_clauses']}）")
            else:
                print("SQL difference: " + json.dumps(self.report["sql_difference"], ensure_ascii=False), flush=True)
        destination = self.work / "restored-files"
        destination.mkdir(mode=0o700)
        verify_files(self.archive_root / "files.tar.gz", destination, self.report["files"])
        self.report["files_restore_verified"] = True
        self.passed("所有備份檔案已解至獨立目錄；大小／SHA-256 一致")
        need(sql_matches, "隔離還原後 SQL 仍有非等價差異；摘要與私人 restored.sql.gz 已保存")
        if raw_matches:
            restored_sql.unlink()
        self.report["restore_verified"] = True
        self.passed("無網路暫存 MySQL 還原／完整 SQL 等價比對與所有檔案 SHA-256 通過")

    def cleanup_restore(self):
        if self.temp_id:
            need(self.temp_id != self.database["id"], "拒絕刪除正式資料庫容器")
            self.docker("stop", "--time", "30", self.temp_id)
            self.docker("rm", self.temp_id)
            self.temp_id = None
        if self.volume:
            need(self.volume.startswith("sam-yolo-restore-") and self.volume != "sam-yolo-mysql-data", "拒絕刪除正式 volume")
            labels = json.loads(self.docker("volume", "inspect", "--format", "{{json .Labels}}", self.volume)) or {}
            need(labels.get("sam.yolo.restore") == self.stamp, "暫存 volume 歸屬不符")
            self.docker("volume", "rm", self.volume)
            self.volume = None

    def run(self):
        verified = False
        try:
            self.preflight()
            if self.existing is None:
                self.capture()
            self.restore()
            verified = True
        except (Exception, KeyboardInterrupt) as exc:
            self.report["failed_step"] = self.step
            self.report["error"] = str(exc) if isinstance(exc, Failed) else type(exc).__name__
            print(f"FAIL [{self.step}]: " + self.report["error"], flush=True)
        finally:
            cleanup_errors = []
            try:
                if self.paused:
                    self.docker("start", self.backend_id)
                    self.paused = False
                if self.backend_id:
                    self.wait_backend()
                    self.health()
                    if self.database:
                        current = self.inspect("sam-yolo-mysql")
                        need(current["id"] == self.database["id"] and current["mounts"] == self.database["mounts"], "正式 MySQL 身分／掛載變更")
            except Exception:
                cleanup_errors.append("production health")
            try:
                self.cleanup_restore()
            except Exception:
                cleanup_errors.append("temporary restore resources")
            self.report["cleanup_errors"] = cleanup_errors
            self.report["success"] = verified and not cleanup_errors
            if self.work.exists() and not cleanup_errors:
                shutil.rmtree(self.work)
            self.session.close()
            if self.backend_id and self.database and not cleanup_errors:
                self.passed("正式 backend／nginx／MySQL 正常；暫存還原資源已清除")
            if self.report["success"]:
                try:
                    result = subprocess.run(["ss", "-ltnH", "( sport = :80 or sport = :443 )"], capture_output=True, text=True, timeout=10)
                    self.report["https_listeners"] = result.stdout.splitlines() if result.returncode == 0 else None
                except (OSError, subprocess.TimeoutExpired):
                    self.report["https_listeners"] = None
                listeners = self.report["https_listeners"]
                print("HTTPS readiness: " + ("80/443 currently unused" if listeners == []
                                             else "80/443 needs inspection"), flush=True)
                if listeners:
                    print("\n".join(listeners), flush=True)
                print("Backup / isolated restore / SQL-files verification: PASS", flush=True)
            elif cleanup_errors:
                print("需處理：" + ", ".join(cleanup_errors), flush=True)
            if self.output.exists():
                private_write(self.output / "manifest.json", json.dumps(self.report, ensure_ascii=False, indent=2))
            if self.existing is not None:
                print("原始備份：" + str(self.existing), flush=True)
                print("本次驗證報告：" + str(self.output), flush=True)
            else:
                print("私人備份與報告：" + str(self.output), flush=True)
        return 0 if self.report["success"] else 1


if __name__ == "__main__":
    if sys.platform != "linux" or os.getuid() == 0:
        raise SystemExit("請在 Ubuntu 先 sudo -v，再以自己的帳號執行 Python。")
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-existing", type=Path, help="重驗既有備份，不停止 backend、不建立新來源快照")
    arguments = parser.parse_args()
    lock = Path.home() / ".config/yolo-system/compose-apply.lock"
    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("已有部署或備份批次正在執行。")
        authorization = subprocess.run(["sudo", "-n", "-v"], stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        if authorization.returncode:
            raise SystemExit("請先執行 sudo -v，再重跑本批次。")
        stop_refresh = threading.Event()
        refresh = threading.Thread(target=keep_sudo_alive, args=(stop_refresh,), daemon=True)
        refresh.start()
        try:
            raise SystemExit(Backup(arguments.verify_existing).run())
        finally:
            stop_refresh.set()
            refresh.join(timeout=11)
    finally:
        os.close(descriptor)

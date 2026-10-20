"""Local file-integrity and production-protection tests; no Docker or network."""
from contextlib import redirect_stdout
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "lab_backup_verify.py"
with patch.object(sys, "path", [str(SOURCE.parent)] + sys.path):
    spec = importlib.util.spec_from_file_location("lab_backup_verify", SOURCE)
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)


class FileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "source"
        self.source.write_bytes(b"private contents\x00\xff")
        self.archive = self.root / "files.tar.gz"
        self.destination = self.root / "restore"
        self.destination.mkdir(mode=0o700)

    def test_archive_restore_hashes_and_private_modes(self):
        manifest = app.capture_files(self.archive, {"private/backend.env": self.source})
        app.verify_files(self.archive, self.destination, manifest)
        restored = self.destination / "private/backend.env"
        self.assertEqual(restored.read_bytes(), self.source.read_bytes())
        self.assertEqual(self.archive.stat().st_mode & 0o777, 0o600)
        self.assertEqual(restored.stat().st_mode & 0o777, 0o600)

    def test_hardlinked_sources_are_archived_as_independent_regular_files(self):
        second = self.root / "hardlink"
        os.link(self.source, second)
        manifest = app.capture_files(self.archive, {"one": self.source, "two": second})
        app.verify_files(self.archive, self.destination, manifest)
        self.assertEqual((self.destination / "two").read_bytes(), self.source.read_bytes())

    def test_symlink_source_is_rejected(self):
        link = self.root / "link"
        link.symlink_to(self.source)
        with self.assertRaises(app.Failed):
            app.capture_files(self.archive, {"link": link})

    def test_manifest_hash_mismatch_is_rejected(self):
        manifest = app.capture_files(self.archive, {"one": self.source})
        manifest["one"]["sha256"] = "incorrect"
        with self.assertRaises(app.Failed):
            app.verify_files(self.archive, self.destination, manifest)

    def test_traversal_is_rejected_before_write(self):
        with tarfile.open(self.archive, "w:gz") as tar:
            info = tarfile.TarInfo("../../escape")
            info.size = 1
            tar.addfile(info, io.BytesIO(b"x"))
        with self.assertRaises(app.Failed):
            app.verify_files(self.archive, self.destination, {"../../escape": {"size":1,"sha256":"unused"}})
        self.assertFalse((self.root.parent / "escape").exists())

    def test_duplicate_archive_entry_is_rejected(self):
        with tarfile.open(self.archive, "w:gz") as tar:
            for _ in range(2):
                info = tarfile.TarInfo("one")
                info.size = self.source.stat().st_size
                tar.addfile(info, io.BytesIO(self.source.read_bytes()))
        manifest = {"one": {"size":self.source.stat().st_size,"sha256":app.file_hash(self.source)}}
        with self.assertRaises(app.Failed):
            app.verify_files(self.archive, self.destination, manifest)

    def test_private_write_refuses_overwrite(self):
        target = self.root / "config"
        app.private_write(target, "first")
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            app.private_write(target, "second")
        self.assertEqual(target.read_text(), "first")


class DifferenceTests(unittest.TestCase):
    def test_data_differences_are_reported_without_sql_or_literals(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / name for name in ("source.gz", "restored.gz")]
            for path, secret in zip(paths, ("private-password-hash-A", "private-password-hash-B")):
                with gzip.open(path, "wb") as handle:
                    handle.write(("CREATE TABLE `users` (\n);\nINSERT INTO `users` VALUES (1,'" + secret + "');\n").encode())
            summary = app.sql_difference(*paths)
            self.assertEqual(summary["first_difference"]["section"], "data")
            self.assertEqual(summary["first_difference"]["table"], "users")
            self.assertEqual(summary["differing_lines"], 1)
            self.assertNotIn("private-password", json.dumps(summary))
            self.assertNotIn("INSERT", json.dumps(summary))

    def test_safe_table_options_and_missing_lines_are_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / name for name in ("source.gz", "restored.gz")]
            for path, count in zip(paths, (5, 6)):
                with gzip.open(path, "wb") as handle:
                    handle.write(f"CREATE TABLE `items` (\n) ENGINE=InnoDB AUTO_INCREMENT={count} DEFAULT CHARSET=utf8mb4;\n".encode())
                    if count == 6:
                        handle.write(b"\n")
            summary = app.sql_difference(*paths)
            self.assertEqual(summary["first_difference"]["table_options"]["auto_increment"], ["5", "6"])
            self.assertEqual(summary["source_lines"], 2)
            self.assertEqual(summary["restored_lines"], 3)


class NormalizationTests(unittest.TestCase):
    def compare(self, before, after):
        with tempfile.TemporaryDirectory() as folder:
            results = []
            for name, sql in (("source", before), ("restored", after)):
                path = Path(folder) / (name + ".sql.gz")
                with gzip.open(path, "wb") as handle:
                    handle.write(sql)
                results.append(app.normalized_sql_hash(path))
            return results

    def test_mysql_110825_thirty_column_fixture_is_equivalent(self):
        prefix = b"CREATE TABLE `alembic_version` (\n"
        columns = b"".join(f"  `column_{n}` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,\n".encode() for n in range(30))
        suffix = b") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;\nINSERT INTO `alembic_version` VALUES ('0013');\n"
        before = prefix + columns + suffix
        after = prefix + columns.replace(b" COLLATE ", b" CHARACTER SET utf8mb4 COLLATE ") + suffix
        source, restored = self.compare(before, after)
        self.assertEqual(source["sha256"], restored["sha256"])
        self.assertEqual(source["redundant_utf8mb4_clauses"], 0)
        self.assertEqual(restored["redundant_utf8mb4_clauses"], 30)

    def test_data_values_and_default_literals_remain_exact(self):
        for before, after in (
            (b"INSERT INTO `users` VALUES ('private-A CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci');\n",
             b"INSERT INTO `users` VALUES ('private-B CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci');\n"),
            (b"CREATE TABLE `t` (\n  `v` text DEFAULT 'CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'\n);\n",
             b"CREATE TABLE `t` (\n  `v` text DEFAULT 'COLLATE utf8mb4_unicode_ci'\n);\n")):
            with self.subTest(before=before[:30]):
                source, restored = self.compare(before, after)
                self.assertNotEqual(source["sha256"], restored["sha256"])
                self.assertEqual(source["redundant_utf8mb4_clauses"], 0)

    def test_other_schema_changes_still_fail(self):
        before = b"CREATE TABLE `t` (\n  `v` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL\n) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4;\n"
        changes = (
            before.replace(b"utf8mb4_unicode_ci", b"utf8mb4_bin"),
            before.replace(b"varchar(32)", b"varchar(64)"),
            before.replace(b"DEFAULT NULL", b"NOT NULL"),
            before.replace(b"AUTO_INCREMENT=7", b"AUTO_INCREMENT=8"),
            before.replace(b" COLLATE utf8mb4_unicode_ci", b" CHARACTER SET utf8mb4"),
            before.replace(b" COLLATE utf8mb4_unicode_ci", b" CHARACTER SET latin1 COLLATE latin1_swedish_ci"))
        for after in changes:
            with self.subTest(after=after):
                source, restored = self.compare(before, after)
                self.assertNotEqual(source["sha256"], restored["sha256"])

    def test_only_create_table_column_prefix_is_normalized(self):
        for prefix in (b"", b"CREATE TABLE `t` (\n);\n"):
            before = prefix + b"  `v` varchar(32) COLLATE utf8mb4_unicode_ci\n"
            after = before.replace(b" COLLATE ", b" CHARACTER SET utf8mb4 COLLATE ")
            source, restored = self.compare(before, after)
            self.assertNotEqual(source["sha256"], restored["sha256"])
            self.assertEqual(restored["redundant_utf8mb4_clauses"], 0)


class ExistingBackupTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.backups = root / "backups"
        self.backups.mkdir(mode=0o700)
        self.previous = self.backups / "original"
        self.previous.mkdir(mode=0o700)
        source = root / "source"
        source.write_bytes(b"media")
        files = app.capture_files(self.previous / "files.tar.gz", {"backend/static/image.png":source})
        with gzip.open(self.previous / "database.sql.gz", "wb") as handle:
            handle.write(b"private SQL contents")
        manifest = {"files":files, "mysql_image":app.MYSQL_IMAGE,
            "database_sql_sha256":app.hashlib.sha256(b"private SQL contents").hexdigest(),
            "database_defaults":{"charset":"utf8mb4", "collation":"utf8mb4_0900_ai_ci"},
            "artifacts":{name:app.file_hash(self.previous / name) for name in ("database.sql.gz", "files.tar.gz")}}
        app.private_write(self.previous / "manifest.json", json.dumps(manifest))
        self.batch = app.Backup(existing=self.previous)
        self.addCleanup(self.batch.session.close)
        self.batch.root = self.backups
        self.batch.output = self.backups / "new-report"

    def test_existing_backup_is_loaded_without_rewriting_original(self):
        before = app.file_hash(self.previous / "manifest.json")
        self.batch.load_existing()
        self.assertEqual(self.batch.archive_root, self.previous.resolve())
        self.assertEqual(self.batch.report["source_backup"], str(self.previous.resolve()))
        self.assertEqual(app.file_hash(self.previous / "manifest.json"), before)

    def test_corrupt_existing_artifact_is_rejected(self):
        (self.previous / "database.sql.gz").write_bytes(b"corrupt")
        with self.assertRaises(app.Failed):
            self.batch.load_existing()

    def test_path_outside_private_backup_root_is_rejected(self):
        self.batch.existing = self.backups.parent
        with self.assertRaises(app.Failed):
            self.batch.load_existing()


class Simulation(app.Backup):
    def __init__(self, root, failure=None):
        super().__init__()
        self.output = root / "backup"
        self.work = self.output / ".work"
        self.archive_root = self.output
        self.failure = failure
        self.calls = []
        self.backend_id = "original-backend"
        self.database = {"id":"production-mysql", "mounts":[{"Name":"sam-yolo-mysql-data"}]}
        self.running = True
        self.source = root / "media.png"
        self.source.write_bytes(b"sample")
        self.sources = {"backend/static/media.png": self.source}

    def preflight(self):
        self.output.mkdir(mode=0o700)
        self.work.mkdir(mode=0o700)

    def collect_sources(self):
        return self.sources

    def mysql(self, container, sql):
        return "0"

    def inspect(self, name, optional=False):
        if name == "sam-yolo-backend":
            return {"id":self.backend_id,"running":self.running}
        if name == "sam-yolo-mysql":
            return self.database.copy()
        raise AssertionError("Unexpected inspect")

    def docker(self, *args, **kwargs):
        self.calls.append(args)
        if args[0] == "stop" and args[-1] == self.backend_id:
            self.running = False
        elif args[0] == "start" and args[-1] == self.backend_id:
            self.running = True
        if args[:2] == ("volume", "inspect"):
            return json.dumps({"sam.yolo.restore": "foreign" if self.failure == "ownership" else self.stamp})
        return ""

    def transfer(self, container, *, archive=None, restore=False):
        if self.failure == "dump" and container == "sam-yolo-mysql":
            raise app.Failed("simulated dump error")
        if archive and not restore:
            with gzip.open(archive,"wb") as handle:
                handle.write(b"test SQL")
        return "test-sql-hash"

    def restore(self):
        self.step = "backup.restore"
        self.temp_id = "temporary-mysql"
        self.volume = "sam-yolo-restore-test"
        if self.failure == "restore":
            raise app.Failed("simulated restore mismatch")
        self.report["restore_verified"] = True

    def wait_backend(self):
        if not self.running:
            raise app.Failed("backend not restored")

    def health(self, port=8080):
        self.wait_backend()


class ProtectionTests(unittest.TestCase):
    def test_retry_does_not_capture_or_stop_production(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulation(Path(folder))
            batch.existing = Path(folder) / "previous"
            with redirect_stdout(io.StringIO()), patch.object(batch, "capture", side_effect=AssertionError("must not capture")), \
                 patch.object(app.subprocess, "run", return_value=subprocess.CompletedProcess([],0,"","")):
                self.assertEqual(batch.run(), 0)
            self.assertFalse(any(c[0] == "stop" and c[-1] == batch.backend_id for c in batch.calls))

    def test_sudo_refresh_is_noninteractive_and_ends_with_batch(self):
        stop = Mock()
        stop.wait.side_effect = [False, True]
        with patch.object(app.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            app.keep_sudo_alive(stop)
        self.assertEqual(run.call_args.args[0], ["sudo", "-n", "-v"])
        self.assertEqual(run.call_count, 1)

    def test_actual_restore_uses_isolated_target_and_source_schema_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulation(Path(folder))
            batch.report["database_defaults"] = {"charset":"utf8mb4", "collation":"utf8mb4_0900_ai_ci"}
            docker = batch.docker
            def simulate(*args, **kwargs):
                result = docker(*args, **kwargs)
                return "a" * 64 if args[0] == "create" else result
            with redirect_stdout(io.StringIO()), patch.object(batch, "docker", side_effect=simulate):
                batch.preflight()
                batch.capture()
                with patch.object(batch, "mysql", return_value="1"):
                    app.Backup.restore(batch)
                self.assertTrue(batch.report["restore_verified"])
                self.assertEqual(batch.temp_id, "a" * 64)
                create = next(c for c in batch.calls if c[0] == "create")
                self.assertEqual(create[create.index("--network") + 1], "none")
                self.assertNotIn("--publish", create)
                self.assertIn("--collation-server=utf8mb4_0900_ai_ci", create)
                self.assertNotIn("type=volume,source=sam-yolo-mysql-data,target=/var/lib/mysql", create)
                batch.cleanup_restore()

    def test_actual_sql_mismatch_stays_failed_and_preserves_private_diagnostics(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulation(Path(folder))
            batch.report["database_defaults"] = {"charset":"utf8mb4", "collation":"utf8mb4_0900_ai_ci"}
            docker = batch.docker
            def simulate(*args, **kwargs):
                result = docker(*args, **kwargs)
                return "a" * 64 if args[0] == "create" else result
            output = io.StringIO()
            with redirect_stdout(output), patch.object(batch, "docker", side_effect=simulate):
                batch.preflight()
                batch.capture()
                transfer = batch.transfer
                def different(container, *, archive=None, restore=False):
                    if not restore and archive and archive.name == "restored.sql.gz":
                        with gzip.open(archive, "wb") as handle:
                            handle.write(b"private-user-data")
                        return "different-hash"
                    return transfer(container, archive=archive, restore=restore)
                with patch.object(batch, "mysql", return_value="1"), patch.object(batch, "transfer", side_effect=different):
                    with self.assertRaises(app.Failed):
                        app.Backup.restore(batch)
                self.assertTrue(batch.report["files_restore_verified"])
                self.assertFalse(batch.report.get("restore_verified", False))
                self.assertIn("sql_difference", batch.report)
                self.assertTrue((batch.output / "restored.sql.gz").exists())
                self.assertNotIn("private-user-data", output.getvalue())
                batch.cleanup_restore()

    def test_actual_restore_accepts_only_proven_equivalent_charset_output(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulation(Path(folder))
            batch.report["database_defaults"] = {"charset":"utf8mb4", "collation":"utf8mb4_unicode_ci"}
            source_sql = b"CREATE TABLE `t` (\n  `v` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL\n);\nINSERT INTO `t` VALUES ('private data');\n"
            restored_sql = source_sql.replace(b"varchar(32) COLLATE", b"varchar(32) CHARACTER SET utf8mb4 COLLATE")
            docker = batch.docker
            def simulate(*args, **kwargs):
                result = docker(*args, **kwargs)
                return "a" * 64 if args[0] == "create" else result
            with redirect_stdout(io.StringIO()), patch.object(batch, "docker", side_effect=simulate):
                batch.preflight()
                batch.capture()
                with gzip.open(batch.output / "database.sql.gz", "wb") as handle:
                    handle.write(source_sql)
                batch.report["database_sql_sha256"] = app.hashlib.sha256(source_sql).hexdigest()
                def transfer(container, *, archive=None, restore=False):
                    if not restore:
                        with gzip.open(archive, "wb") as handle:
                            handle.write(restored_sql)
                    return app.hashlib.sha256(restored_sql).hexdigest()
                with patch.object(batch, "mysql", return_value="1"), patch.object(batch, "transfer", side_effect=transfer):
                    app.Backup.restore(batch)
                self.assertTrue(batch.report["restore_verified"])
                self.assertFalse(batch.report["sql_verification"]["raw_equal"])
                self.assertTrue(batch.report["sql_verification"]["equivalent"])
                self.assertEqual(batch.report["sql_verification"]["restored_normalized"]["redundant_utf8mb4_clauses"], 1)
                self.assertTrue((batch.output / "restored.sql.gz").is_file())
                batch.cleanup_restore()

    def run_batch(self, failure=None):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        batch = Simulation(Path(folder.name), failure)
        with redirect_stdout(io.StringIO()), patch.object(app.subprocess, "run", return_value=subprocess.CompletedProcess([],0,"","")):
            status = batch.run()
        self.assertTrue(batch.running)
        self.assertFalse(any(c[0] in ("stop", "rm") and c[-1] in ("sam-yolo-mysql", "production-mysql") for c in batch.calls))
        self.assertFalse(any(c[:2] == ("volume","rm") and c[-1] == "sam-yolo-mysql-data" for c in batch.calls))
        report = json.loads((batch.output / "manifest.json").read_text())
        self.assertEqual(report["success"], status == 0)
        self.assertEqual((batch.output / "manifest.json").stat().st_mode & 0o777, 0o600)
        return batch, status

    def test_success_restores_backend_and_removes_only_temp_resources(self):
        batch, status = self.run_batch()
        self.assertEqual(status, 0)
        self.assertIn(("rm","temporary-mysql"), batch.calls)
        self.assertIn(("volume","rm","sam-yolo-restore-test"), batch.calls)
        self.assertFalse(batch.work.exists())
        report = json.loads((batch.output / "manifest.json").read_text())
        self.assertIn("正式 backend／nginx／MySQL 正常；暫存還原資源已清除", report["checks"])
        self.assertEqual(report["https_listeners"], [])

    def test_port_inventory_failure_does_not_invalidate_verified_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulation(Path(folder))
            with redirect_stdout(io.StringIO()), patch.object(app.subprocess, "run", side_effect=FileNotFoundError):
                self.assertEqual(batch.run(), 0)
            report = json.loads((batch.output / "manifest.json").read_text())
            self.assertIsNone(report["https_listeners"])
            self.assertTrue(report["restore_verified"])

    def test_new_pending_work_aborts_capture_and_restarts_backend(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulation(Path(folder))
            with redirect_stdout(io.StringIO()), patch.object(batch, "mysql", return_value="1"):
                self.assertEqual(batch.run(), 1)
            self.assertTrue(batch.running)
            self.assertFalse((batch.output / "database.sql.gz").exists())

    def test_dump_failure_still_restarts_backend(self):
        batch, status = self.run_batch("dump")
        self.assertEqual(status, 1)
        self.assertIn(("start","original-backend"), batch.calls)

    def test_restore_failure_cleans_only_temporary_resources(self):
        batch, status = self.run_batch("restore")
        self.assertEqual(status, 1)
        self.assertIn(("rm","temporary-mysql"), batch.calls)

    def test_wrong_volume_label_is_not_deleted(self):
        batch, status = self.run_batch("ownership")
        self.assertEqual(status, 1)
        self.assertNotIn(("volume","rm","sam-yolo-restore-test"), batch.calls)
        self.assertTrue(batch.work.exists())

    def test_production_import_rejected_before_process_start(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulation(Path(folder))
            batch.temp_id = "temporary-mysql"
            with patch.object(app.subprocess, "Popen") as process:
                with self.assertRaises(app.Failed):
                    app.Backup.transfer(batch, "sam-yolo-mysql", restore=True)
                process.assert_not_called()

    def test_production_container_cleanup_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulation(Path(folder))
            batch.temp_id = "production-mysql"
            with self.assertRaises(app.Failed):
                batch.cleanup_restore()
            self.assertEqual(batch.calls, [])

    def test_production_volume_cleanup_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulation(Path(folder))
            batch.volume = "sam-yolo-mysql-data"
            with self.assertRaises(app.Failed):
                batch.cleanup_restore()
            self.assertEqual(batch.calls, [])


if __name__ == "__main__":
    unittest.main()

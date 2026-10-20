"""Downloaded copies must match verified artifacts and every archived file."""
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/"verify_downloaded_backup.py"
spec=importlib.util.spec_from_file_location("verify_downloaded_backup",SOURCE)
app=importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
        self.source=self.root/"source"
        self.success=self.root/"verified"
        self.source.mkdir()
        self.success.mkdir()
        self.sql=b"CREATE TABLE fixture (id INT);\n"
        (self.source/"database.sql.gz").write_bytes(gzip.compress(self.sql))
        self.payload=b"fixture-content\n"
        self.member="private/backend.env"
        self.archive()
        self.original={"success":False,"restore_verified":False,"database_defaults":{"charset":"utf8mb4","collation":"utf8mb4_unicode_ci"},
            "database_sql_sha256":hashlib.sha256(self.sql).hexdigest(),
            "files":{self.member:{"size":len(self.payload),"sha256":hashlib.sha256(self.payload).hexdigest()}},
            "artifacts":{name:hashlib.sha256((self.source/name).read_bytes()).hexdigest() for name in ("database.sql.gz","files.tar.gz")}}
        self.report=deepcopy(self.original)
        self.report.update(success=True,restore_verified=True,source_backup="/server/backups/source")
        self.save()

    def archive(self):
        with tarfile.open(self.source/"files.tar.gz","w:gz") as archive:
            info=tarfile.TarInfo(self.member)
            info.size=len(self.payload)
            archive.addfile(info,io.BytesIO(self.payload))

    def save(self):
        (self.source/"manifest.json").write_text(json.dumps(self.original))
        (self.success/"manifest.json").write_text(json.dumps(self.report))

    def test_success_uses_separate_passed_restore_report_not_initial_failed_flag(self):
        result=app.verify(self.source,self.success)
        self.assertEqual(result["files"],1)
        self.assertEqual(result["bytes"],len(self.payload))
        self.assertEqual(set(p.name for p in self.source.iterdir()),{"manifest.json","files.tar.gz","database.sql.gz"})

    def test_unverified_or_unrelated_restore_report_is_rejected(self):
        self.report["restore_verified"]=False
        self.save()
        with self.assertRaises(app.InvalidBackup): app.verify(self.source,self.success)
        self.report.update(restore_verified=True,source_backup="/server/backups/another")
        self.save()
        with self.assertRaises(app.InvalidBackup): app.verify(self.source,self.success)

    def test_incomplete_or_corrupted_compressed_download_is_rejected(self):
        with (self.source/"files.tar.gz").open("ab") as stream: stream.write(b"changed")
        with self.assertRaises(app.InvalidBackup): app.verify(self.source,self.success)

    def test_inner_file_hash_is_checked_even_when_outer_archive_matches(self):
        self.payload=b"changed-content\n"
        self.archive()
        digest=hashlib.sha256((self.source/"files.tar.gz").read_bytes()).hexdigest()
        self.original["artifacts"]["files.tar.gz"]=digest
        self.report["artifacts"]["files.tar.gz"]=digest
        self.save()
        with self.assertRaises(app.InvalidBackup): app.verify(self.source,self.success)

    def test_sql_uncompressed_hash_is_checked(self):
        (self.source/"database.sql.gz").write_bytes(gzip.compress(b"different SQL"))
        digest=hashlib.sha256((self.source/"database.sql.gz").read_bytes()).hexdigest()
        self.original["artifacts"]["database.sql.gz"]=digest
        self.report["artifacts"]["database.sql.gz"]=digest
        self.save()
        with self.assertRaises(app.InvalidBackup): app.verify(self.source,self.success)

    def test_tar_traversal_is_never_accepted_or_extracted(self):
        self.member="../outside"
        self.archive()
        self.original["files"]={self.member:{"size":len(self.payload),"sha256":hashlib.sha256(self.payload).hexdigest()}}
        self.original["artifacts"]["files.tar.gz"]=hashlib.sha256((self.source/"files.tar.gz").read_bytes()).hexdigest()
        self.report=deepcopy(self.original)
        self.report.update(success=True,restore_verified=True,source_backup="/server/backups/source")
        self.save()
        with self.assertRaises(app.InvalidBackup): app.verify(self.source,self.success)
        self.assertFalse((self.root/"outside").exists())


if __name__=="__main__": unittest.main()

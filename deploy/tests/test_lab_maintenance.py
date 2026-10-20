"""Failure recovery, retention and privilege boundaries of daily backups."""
from contextlib import redirect_stdout
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import subprocess
import tarfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lab_maintenance as app
import install_lab_maintenance as installer
from ci_requirements import cpu_pins


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.config={'uid':1007,'gid':1007,'keep':7,'worker_sha256':'test','docker':'/snap/bin/docker'}
        self.worker=app.Maintenance(self.config,self.root)

    def snapshot(self,index,**extra):
        path=self.root/f'202610{index:02d}T120000Z-12345678'
        path.mkdir()
        report={'kind':'sam-yolo-managed-v1','success':True,'pinned':False,**extra}
        (path/'manifest.json').write_text(json.dumps(report))
        return path

    def test_only_verified_unpinned_snapshots_rotate(self):
        first=self.snapshot(1)
        self.snapshot(2,pinned=True)
        self.snapshot(3,success=False)
        for index in range(4,11):self.snapshot(index)
        (self.root/'unrelated').mkdir()
        self.assertEqual(app.retained_candidates(self.root,7),[first])

    def test_source_original_baseline_and_symlinks_never_rotate(self):
        original=self.root/'20261020T075232Z-2550504'
        original.mkdir()
        (self.root/'20261001T120000Z-12345678').symlink_to(original,target_is_directory=True)
        self.assertEqual(app.retained_candidates(self.root,0),[])

    def test_charset_normalization_does_not_change_data(self):
        left=self.root/'left.gz'; right=self.root/'right.gz'
        source=b'CREATE TABLE `t` (\n  `a` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,\n) ENGINE=InnoDB;\nINSERT INTO `t` VALUES ("data");\n'
        with gzip.open(left,'wb') as out:out.write(source)
        with gzip.open(right,'wb') as out:out.write(source.replace(b'varchar(32) COLLATE',b'varchar(32) CHARACTER SET utf8mb4 COLLATE'))
        self.assertEqual(app.normalized_sql(left),app.normalized_sql(right))
        with gzip.open(right,'wb') as out:out.write(source.replace(b'"data"',b'"changed"'))
        self.assertNotEqual(app.normalized_sql(left),app.normalized_sql(right))

    def test_dump_failure_always_starts_backend(self):
        states={'sam-yolo-backend':{'id':'backend'},'sam-yolo-mysql':{'id':'db'},'sam-yolo-gateway':{'id':'gateway'}}
        self.worker.output.mkdir()
        calls=[]
        with patch.object(self.worker,'docker',side_effect=lambda *a,**k:calls.append(a)), \
             patch.object(self.worker,'sql',return_value='0'), \
             patch.object(self.worker,'stream',side_effect=RuntimeError('dump failed')), \
             patch.object(self.worker,'health'):
            with self.assertRaises(RuntimeError): self.worker.capture(states)
        self.assertIn(('start','backend'),calls)
        self.assertFalse((self.root/'paused-backend.json').exists())

    def test_cleanup_refuses_foreign_container(self):
        self.worker.temporary='foreign'
        with patch.object(self.worker,'inspect',return_value={'labels':{}}),patch.object(self.worker,'docker') as docker:
            with self.assertRaises(RuntimeError):self.worker.cleanup()
            docker.assert_not_called()

    def test_cleanup_refuses_production_volume(self):
        self.worker.volume='sam-yolo-mysql-data'
        with patch.object(self.worker,'docker',return_value='{}') as docker:
            with self.assertRaises(RuntimeError):self.worker.cleanup()
            self.assertFalse(any('rm' in call.args for call in docker.call_args_list))

    def test_resume_does_not_remove_marker_when_start_fails(self):
        marker=self.root/'paused-backend.json'; marker.write_text('{}')
        self.worker.paused='backend'
        with patch.object(self.worker,'docker',side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):self.worker.resume()
        self.assertTrue(marker.exists())
        self.assertEqual(self.worker.paused,'backend')

    def test_failed_verification_never_rotates(self):
        with patch.object(self.worker,'preflight',side_effect=RuntimeError('busy')), \
             patch.object(self.worker,'cleanup'),patch.object(app.os,'chown'), \
             patch.object(app,'retained_candidates') as rotate, redirect_stdout(io.StringIO()):
            self.assertEqual(self.worker.run(),1)
        rotate.assert_not_called()
        self.assertFalse(json.loads((self.worker.output/'manifest.json').read_text())['success'])

    def test_forked_archive_is_fully_flushed_and_includes_uncommitted_source(self):
        repo=self.root/'repo'; repo.mkdir()
        subprocess.run(['git','init','-q',str(repo)],check=True)
        (repo/'README.md').write_text('uncommitted source')
        for folder in ('backend/static','backend/pt','web-frontend/dist'):
            (repo/folder).mkdir(parents=True)
        (repo/'backend/.env').write_text('private test fixture')
        home=self.root/'home'; private=home/'.config/yolo-system'; private.mkdir(parents=True)
        for name in ('compose.env','mysql.env','nginx.lab.conf'):(private/name).write_text('fixture')
        target=self.root/'files.tar.gz'
        # Exercise real fork/FD sharing and tar/gzip close, while remaining our UID.
        with target.open('xb') as archive,tempfile.TemporaryFile() as manifest, \
             patch.object(app.os,'setgroups'),patch.object(app.os,'setgid'),patch.object(app.os,'setuid'):
            app.capture_user_files({'repo':str(repo),'home':str(home),'uid':os.getuid(),'gid':os.getgid()},archive,manifest)
            manifest.seek(0)
            files=json.load(manifest)
        with tarfile.open(target) as archive:
            self.assertEqual(set(archive.getnames()),set(files))
            self.assertEqual(archive.extractfile('source/README.md').read(),b'uncommitted source')

    def model_cache(self,corrupt=False):
        models=self.root/'native'
        (models/'blobs').mkdir(parents=True)
        blob=b'local model fixture'
        digest=hashlib.sha256(blob).hexdigest()
        (models/'blobs'/('sha256-'+digest)).write_bytes(b'corrupt' if corrupt else blob)
        manifests=models/'manifests/registry/library/test';manifests.mkdir(parents=True)
        metadata=json.dumps({'layers':[{'digest':'sha256:'+digest}]}).encode()
        (manifests/'latest').write_bytes(metadata)
        self.worker.report['ollama_models']={'models':[{'name':'test:latest','digest':hashlib.sha256(metadata).hexdigest()}]}
        self.worker.config.update(ollama_models=str(models),ollama_uid=os.getuid(),ollama_gid=os.getgid())
        run=subprocess.run
        def as_current(*args,**kwargs):
            for key in ('user','group','extra_groups'):kwargs.pop(key,None)
            kwargs['env']={**kwargs.get('env',{}),'COPYFILE_DISABLE':'1'}
            return run(*args,**kwargs)
        with patch.object(app.subprocess,'run',side_effect=as_current),patch.object(app,'trusted'),patch.object(app.os,'chown'):
            self.worker.cache_models()

    def test_native_model_cache_checks_manifest_and_blob_content(self):
        self.model_cache()
        cached=self.worker.report['native_models']
        self.assertEqual(app.checksum(self.root/cached['path']),cached['sha256'])

    def test_corrupt_native_model_blob_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'blob fingerprint'):self.model_cache(corrupt=True)


class InstallerTests(unittest.TestCase):
    def test_explicit_timezone_and_authorized_time(self):
        text=installer.timer_text('23:30')
        self.assertIn('23:30:00 Asia/Taipei',text)
        self.assertIn('Persistent=true',text)
        for value in ('24:00','3:00','23:60','23:30\nExecStart=bad'):
            with self.assertRaises(RuntimeError):installer.timer_text(value)

    def test_root_worker_uses_isolated_system_python_and_recovery(self):
        self.assertIn('/usr/bin/python3 -I /usr/local/lib/',installer.SERVICE)
        self.assertIn('ExecStopPost=',installer.SERVICE)
        self.assertNotIn('/home/',installer.SERVICE)
        self.assertNotIn('conda',installer.SERVICE)

    def test_ci_changes_only_cuda_dependencies_and_retains_pins(self):
        text=Path(__file__).resolve().parents[1].joinpath('backend-linux.lock').read_text()
        pins=cpu_pins(text)
        self.assertIn('torch==2.11.0+cpu',pins)
        self.assertIn('torchvision==0.26.0+cpu',pins)
        self.assertFalse(any(p.startswith(('nvidia-','cuda-','triton==')) for p in pins))
        self.assertTrue(all('==' in p for p in pins))


if __name__=='__main__':unittest.main()

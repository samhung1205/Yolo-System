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
import time
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

    def model_cache(self,corrupt=False,aliases=False,blob_alias=False):
        models=self.root/'native'
        (models/'blobs').mkdir(parents=True)
        blob=b'local model fixture'
        digest=hashlib.sha256(blob).hexdigest()
        (models/'blobs'/('sha256-'+digest)).write_bytes(b'corrupt' if corrupt else blob)
        if blob_alias:
            source = models/'blobs'/('sha256-'+digest)
            source.rename(models/'payload')
            source.symlink_to('../payload')
        manifests=models/'manifests/registry/library/test';manifests.mkdir(parents=True)
        metadata=json.dumps({'layers':[{'digest':'sha256:'+digest}]}).encode()
        (manifests/'latest').write_bytes(metadata)
        if aliases:
            (manifests/'relative').symlink_to('latest')
            (manifests/'absolute').symlink_to((manifests/'latest').resolve())
        self.worker.report['ollama_models']={'models':[{'name':'test:latest','digest':hashlib.sha256(metadata).hexdigest()}]}
        self.worker.config.update(ollama_models=str(models),ollama_uid=os.getuid(),ollama_gid=os.getgid())
        with patch.object(app.os,'setgroups'),patch.object(app.os,'setgid'),patch.object(app.os,'setuid'), \
             patch.object(app,'trusted'),patch.object(app.os,'chown'):
            self.worker.cache_models()

    def test_native_model_cache_checks_manifest_and_blob_content(self):
        self.model_cache()
        cached=self.worker.report['native_models']
        self.assertEqual(app.checksum(self.root/cached['path']),cached['sha256'])

    def test_corrupt_native_model_blob_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'blob fingerprint'):self.model_cache(corrupt=True)

    def test_two_internal_manifest_aliases_become_portable_files(self):
        self.model_cache(aliases=True)
        path = self.root / self.worker.report['native_models']['path']
        with tarfile.open(path) as archive:
            members = archive.getmembers()
            self.assertTrue(all(item.isfile() or item.isdir() for item in members))
            latest = archive.extractfile('manifests/registry/library/test/latest').read()
            for alias in ('relative', 'absolute'):
                self.assertEqual(archive.extractfile('manifests/registry/library/test/' + alias).read(), latest)

    def test_internal_blob_link_is_exported_and_fingerprinted(self):
        self.model_cache(blob_alias=True)
        self.assertIn('native_models', self.worker.report)

    def test_corrupt_internal_blob_link_still_fails_fingerprint(self):
        with self.assertRaisesRegex(RuntimeError, 'blob fingerprint'):
            self.model_cache(blob_alias=True, corrupt=True)


class NativeModelSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'models'; self.root.mkdir()
        (self.root / 'data').mkdir(); (self.root / 'data/blob').write_bytes(b'model fixture')

    def archive(self):
        output = io.BytesIO()
        app.write_native_models(self.root, output)
        output.seek(0)
        return output

    def test_internal_directory_alias_and_hardlink_have_full_contents(self):
        (self.root / 'alias').symlink_to('data', target_is_directory=True)
        os.link(self.root / 'data/blob', self.root / 'hardlink')
        with tarfile.open(fileobj=self.archive()) as archive:
            self.assertTrue(all(item.isfile() or item.isdir() for item in archive))
            self.assertEqual(archive.extractfile('alias/blob').read(), b'model fixture')
            self.assertEqual(archive.extractfile('hardlink').read(), b'model fixture')

    def test_external_link_rejected_before_any_compression(self):
        outside = self.root.parent / 'private'; outside.write_bytes(b'not model data')
        for target in (str(outside.resolve()), '../private'):
            with self.subTest(target=target):
                link = self.root / 'link'; link.symlink_to(target)
                output = io.BytesIO()
                with self.assertRaisesRegex(app.ModelSourceError, 'leaves model store'):
                    app.write_native_models(self.root, output)
                self.assertEqual(output.getvalue(), b'')
                link.unlink()

    def test_replaced_store_root_is_rejected(self):
        alias = self.root.parent / 'root-link'; alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(app.ModelSourceError, 'root changed'):
            app.write_native_models(alias, io.BytesIO())

    def test_cyclic_directory_link_rejected_before_compression(self):
        (self.root / 'data/loop').symlink_to('..', target_is_directory=True)
        output = io.BytesIO()
        with self.assertRaisesRegex(app.ModelSourceError, 'Cyclic'):
            app.write_native_models(self.root, output)
        self.assertEqual(output.getvalue(), b'')

    def test_dangling_link_and_fifo_are_rejected(self):
        link = self.root / 'link'; link.symlink_to('absent')
        with self.assertRaisesRegex(app.ModelSourceError, 'Broken'):
            self.archive()
        link.unlink(); os.mkfifo(self.root / 'pipe')
        with self.assertRaisesRegex(app.ModelSourceError, 'Unsupported'):
            self.archive()

    def test_changed_file_is_rejected_before_reading_bytes(self):
        original_open = os.open
        def replace(path, flags):
            if Path(path).name == 'blob':
                Path(path).unlink(); Path(path).write_bytes(b'new bytes')
            return original_open(path, flags)
        with patch.object(app.os, 'open', side_effect=replace):
            with self.assertRaisesRegex(app.ModelSourceError, 'file changed'):
                self.archive()

    def test_export_drops_groups_gid_uid_before_reading_model_tree(self):
        steps = []
        config = {'ollama_models': str(self.root), 'ollama_uid': 1008, 'ollama_gid': 1008}
        def write(root, output):
            output.write(json.dumps(steps).encode()); output.flush()
        output = tempfile.TemporaryFile(); self.addCleanup(output.close)
        with patch.object(app.os, 'setgroups', side_effect=lambda groups: steps.append(['groups', groups])), \
             patch.object(app.os, 'setgid', side_effect=lambda gid: steps.append(['gid', gid])), \
             patch.object(app.os, 'setuid', side_effect=lambda uid: steps.append(['uid', uid])), \
             patch.object(app, 'write_native_models', side_effect=write):
            app.capture_native_models(config, output)
        output.seek(0)
        self.assertEqual(json.load(output), [['groups', []], ['gid', 1008], ['uid', 1008]])

    def test_export_timeout_stops_and_reaps_the_reader(self):
        output = tempfile.TemporaryFile(); self.addCleanup(output.close)
        config = {'ollama_models': str(self.root), 'ollama_uid': os.getuid(), 'ollama_gid': os.getgid()}
        with patch.object(app.os, 'setgroups'), patch.object(app.os, 'setgid'), patch.object(app.os, 'setuid'), \
             patch.object(app, 'write_native_models', side_effect=lambda *args: time.sleep(5)):
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                app.capture_native_models(config, output, timeout=0.01)


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

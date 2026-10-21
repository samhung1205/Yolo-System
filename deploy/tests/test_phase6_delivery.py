import hashlib
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import apply_phase6 as delivery
import lab_finalize as finalize


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        self.package=self.root/'package';self.package.mkdir()

    def manifest(self,name,body=b'new',before=None):
        source=self.package/'payload'/name;source.parent.mkdir(parents=True,exist_ok=True);source.write_bytes(body)
        (self.package/'manifest.json').write_text(json.dumps({'release':'phase6-final-20261021','files':{
            name:{'sha256':hashlib.sha256(body).hexdigest(),'before':[before]}}}))

    def test_plan_does_not_change_sources(self):
        target=self.repo/'README.md';target.write_bytes(b'old')
        self.manifest('README.md',before=delivery.digest(b'old'))
        self.assertEqual(len(delivery.plan(self.repo,self.package)),1)
        self.assertEqual(target.read_bytes(),b'old')

    def test_unknown_server_edit_is_preserved(self):
        target=self.repo/'README.md';target.write_bytes(b'custom')
        self.manifest('README.md')
        with self.assertRaises(RuntimeError):delivery.plan(self.repo,self.package)
        self.assertEqual(target.read_bytes(),b'custom')

    def test_traversal_private_media_and_env_never_allowed(self):
        for name in ('../outside.py','/tmp/a.py','backend/.env','deploy/.env','backend/pt/model.pt',
                     'backend/static/file.png','web-frontend/node_modules/test.js'):
            self.assertFalse(delivery.allowed(name),name)

    def test_tampered_payload_is_rejected(self):
        self.manifest('README.md')
        (self.package/'payload/README.md').write_bytes(b'altered')
        with self.assertRaises(RuntimeError):delivery.plan(self.repo,self.package)

    def test_symlink_destination_is_rejected(self):
        target=self.repo/'README.md';target.symlink_to(self.root/'external')
        self.manifest('README.md')
        with self.assertRaises(RuntimeError):delivery.plan(self.repo,self.package)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.work=self.root/'work';self.work.mkdir()
        self.before='YOLO_PUBLIC_GATEWAY_IMAGE=sha256:'+('a'*64)+'\nYOLO_GATEWAY_NNP=false\n'
        (self.root/'compose.env').write_text(self.before)
        self.calls=[]
        self.batch=SimpleNamespace(config=self.root,repo=self.root,stamp='20261021T000000Z-1',
            session=SimpleNamespace(get=lambda *a,**k:SimpleNamespace(status_code=200,json=lambda:{'database':'connected'})),
            inspect=lambda _: {'image':'sha256:'+'b'*64})
        def docker(*args):
            self.calls.append(args)
            if args[:2]==('image','inspect'):return 'sha256:'+'b'*64
            if args[0]=='run':return '{}'
            return ''
        self.batch.docker=docker

    def test_only_gateway_is_recreated_and_nnp_preserved(self):
        with patch.object(finalize,'checked'),patch.object(finalize,'check_gateway_config'):
            result=finalize.update_gateway(self.batch,{'image':'previous'},self.work)
        self.assertEqual(result['previous_image'],'previous')
        self.assertIn('YOLO_GATEWAY_NNP=false',(self.root/'compose.env').read_text())
        up=[c for c in self.calls if 'up' in c]
        self.assertEqual(len(up),1)
        self.assertEqual(up[0][-1],'gateway')
        self.assertIn('--no-deps',up[0])

    def test_failed_gateway_switch_restores_private_config(self):
        original=self.batch.docker
        count=0
        def failed(*args):
            nonlocal count
            if 'up' in args:
                count+=1
                if count==1:raise RuntimeError('switch failure')
            return original(*args)
        self.batch.docker=failed
        with patch.object(finalize,'checked'),patch.object(finalize,'check_gateway_config'):
            with self.assertRaises(RuntimeError):finalize.update_gateway(self.batch,{'image':'previous'},self.work)
        self.assertEqual((self.root/'compose.env').read_text(),self.before)
        self.assertEqual(count,2)


class ContainerRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.batch=SimpleNamespace(repo=self.root)
        self.state={'image':'sha256:'+'a'*64,'user':'1007:1007'}

    def test_no_host_tmp_or_private_media_is_mounted_and_gpu_limits_remain(self):
        with patch.object(finalize,'checked',return_value='190 passed\nContainer custom YOLO GPU smoke test: PASS\nContainer YOLO video smoke test: PASS') as run:
            finalize.container_tests(self.batch,self.state)
        command=run.call_args.args[0]
        mounts=[command[i+1] for i,value in enumerate(command) if value=='--mount']
        self.assertEqual(len(mounts),4)
        self.assertTrue(all(value.endswith(',readonly') for value in mounts))
        self.assertFalse(any('/backend/static' in value or '/.env' in value for value in mounts))
        self.assertIn('/opt/yolo/backend/static:rw,nosuid,nodev,noexec,size=16m,mode=1777',command)
        self.assertEqual(command[command.index('--network')+1],'none')
        self.assertEqual(command[command.index('--user')+1],'1007:1007')
        self.assertEqual(command[command.index('--memory')+1],'8g')
        self.assertEqual(command[command.index('--gpus')+1],'all')
        self.assertNotIn('--privileged',command)

    def test_actual_seed_command_creates_only_three_synthetic_images(self):
        from PIL import Image
        with patch.object(finalize,'checked',return_value='Container custom YOLO GPU smoke test: PASS\nContainer YOLO video smoke test: PASS') as run:
            finalize.container_tests(self.batch,self.state)
        tokens=shlex.split(run.call_args.args[0][-1])
        seed=tokens[tokens.index('-c')+1]
        self.assertIn('&&',tokens)
        subprocess.run([sys.executable,'-c',seed],cwd=self.root,check=True,capture_output=True)
        images=sorted(self.root.rglob('*.png'))
        self.assertEqual(len(images),3)
        for path in images:
            with Image.open(path) as image:self.assertEqual(image.size,(640,640))

    def test_missing_gpu_pass_marker_is_not_success(self):
        with patch.object(finalize,'checked',return_value='182 passed'):
            with self.assertRaises(finalize.Failed):finalize.container_tests(self.batch,self.state)

    def test_image_gpu_success_without_video_is_not_success(self):
        with patch.object(finalize,'checked',return_value='190 passed\nContainer custom YOLO GPU smoke test: PASS'):
            with self.assertRaisesRegex(finalize.Failed,'影片追蹤未通過'):
                finalize.container_tests(self.batch,self.state)

    def test_real_subprocess_error_is_private_and_preserves_exit_and_stderr(self):
        log=self.root/'failure.json'
        stdout=io.StringIO()
        with redirect_stdout(stdout),self.assertRaises(finalize.CommandFailure) as raised:
            finalize.checked([sys.executable,'-c',
                'import sys; print("private fixture"); print("diagnostic fixture",file=sys.stderr); sys.exit(125)'],
                show=True,log_path=log)
        self.assertEqual(raised.exception.returncode,125)
        self.assertNotIn('private fixture',stdout.getvalue()+str(raised.exception))
        self.assertNotIn('diagnostic fixture',stdout.getvalue()+str(raised.exception))
        report=json.loads(log.read_text())
        self.assertEqual(report['exit_code'],125)
        self.assertIn('diagnostic fixture',report['stderr'])
        self.assertEqual(log.stat().st_mode & 0o777,0o600)

    def test_docker_mount_error_is_not_mislabelled_as_sudo(self):
        result=subprocess.CompletedProcess([],125,'','Error response from daemon: bind source path does not exist: /tmp/private-fixture')
        with patch.object(finalize.subprocess,'run',return_value=result),self.assertRaises(finalize.CommandFailure) as raised:
            finalize.checked(['sudo','-n','docker','run'],log_path=self.root/'mount.json')
        message=str(raised.exception)
        self.assertIn('Docker',message)
        self.assertIn('bind mount',message)
        self.assertNotIn('/tmp/private-fixture',message)

    def test_sudo_authentication_error_remains_distinguishable(self):
        result=subprocess.CompletedProcess([],1,'','sudo: a password is required')
        with patch.object(finalize.subprocess,'run',return_value=result),self.assertRaises(finalize.CommandFailure) as raised:
            finalize.checked(['sudo','-n','docker','run'],log_path=self.root/'sudo.json')
        self.assertIn('sudo 驗證',str(raised.exception))

    def test_container_failure_stops_before_gateway_or_account_changes(self):
        previous=os.umask(0o077);self.addCleanup(os.umask,previous)
        config=self.root/'config';config.mkdir()
        (config/'releases').mkdir()
        batch=Mock(config=config,stamp='test',repo=self.root)
        batch.inspect.return_value={'running':True,'mounts':[{'Name':'sam-yolo-mysql-data'}]}
        resources=Mock();resources.thread.ident=None
        failure=finalize.CommandFailure('Docker',125,self.root/'command.json','fixture failure')
        with patch.object(finalize.sys,'platform','linux'),patch.object(finalize.os,'getuid',return_value=1007), \
             patch.object(finalize,'Batch',return_value=batch),patch.object(finalize,'checked'), \
             patch.object(finalize,'build_backend',return_value='sha256:'+'a'*64), \
             patch.object(finalize,'ResourceSample',return_value=resources), \
             patch.object(finalize,'keep_sudo_alive'),patch.object(finalize,'container_tests',side_effect=failure), \
             patch.object(finalize,'update_backend') as backend, \
             patch.object(finalize,'update_gateway') as gateway,patch.object(finalize,'Regression') as regression, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(finalize.main(),1)
        backend.assert_not_called();gateway.assert_not_called();regression.assert_not_called()
        report=json.loads(next((config/'reports').glob('finalize-*.json')).read_text())
        self.assertFalse(report['success'])
        self.assertEqual(report['stage'],'container-regression')
        self.assertEqual(report['command_failure']['exit_code'],125)


class BackupResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'config'; (self.config / 'reports').mkdir(parents=True)
        (self.config / 'releases').mkdir()
        self.path = self.config / 'reports/finalize-fixture.json'
        self.states = {name: {'id': name, 'image': 'sha256:' + char * 64, 'running': True,
                            'mounts': [{'Name': 'sam-yolo-mysql-data'}],
                            'project': 'sam-yolo', 'service': name.removeprefix('sam-yolo-')}
                       for name, char in zip(('sam-yolo-backend', 'sam-yolo-web', 'sam-yolo-gateway', 'sam-yolo-mysql'), 'abcd')}
        self.evidence = {'success': False, 'stage': 'initial-managed-backup',
                         'existing_data_and_sse': True, 'regression': {'success': True},
                         'container_tests': ['Container custom YOLO GPU smoke test: PASS',
                                             'Container YOLO video smoke test: PASS'],
                         'candidate_backend_image': self.states['sam-yolo-backend']['image'],
                         'backend_update': {}, 'gateway_update': {'image': self.states['sam-yolo-gateway']['image']}}
        self.save()
        self.batch = Mock(config=self.config, repo=self.root, stamp='fixture')
        self.batch.request.return_value.json.return_value = {'registration_enabled': False}
        self.batch.session.get.return_value.status_code = 200
        self.batch.session.get.return_value.json.return_value = {'database': 'connected'}

    def save(self):
        self.path.write_text(json.dumps(self.evidence)); self.path.chmod(0o600)

    def test_complete_checks_and_same_images_can_resume(self):
        result = finalize.backup_resume_evidence(self.batch, self.path, self.states)
        self.assertEqual(result['resumed_from'], str(self.path))
        self.assertTrue(result['regression']['success'])
        self.batch.health.assert_any_call(8000)
        self.batch.health.assert_any_call()

    def test_incomplete_or_older_checks_cannot_skip_verification(self):
        for change in ({'regression': {'success': False}}, {'existing_data_and_sse': False},
                       {'stage': 'https-regression'}, {'container_tests': ['Container custom YOLO GPU smoke test: PASS']}):
            with self.subTest(change=change):
                before = self.evidence.copy(); self.evidence.update(change); self.save()
                with self.assertRaises(finalize.Failed):
                    finalize.backup_resume_evidence(self.batch, self.path, self.states)
                self.evidence = before

    def test_changed_running_image_is_rejected(self):
        self.states['sam-yolo-backend']['image'] = 'sha256:' + 'e' * 64
        with self.assertRaisesRegex(finalize.Failed, 'image 已改變'):
            finalize.backup_resume_evidence(self.batch, self.path, self.states)

    def test_shared_report_or_symlink_is_rejected(self):
        self.path.chmod(0o644)
        with self.assertRaises(finalize.Failed):
            finalize.backup_resume_evidence(self.batch, self.path, self.states)
        self.path.chmod(0o600)
        link = self.path.with_name('link.json'); link.symlink_to(self.path)
        with self.assertRaises(finalize.Failed):
            finalize.backup_resume_evidence(self.batch, link, self.states)

    def test_https_or_registration_failure_prevents_resume(self):
        self.batch.session.get.return_value.status_code = 503
        with self.assertRaises(finalize.Failed):
            finalize.backup_resume_evidence(self.batch, self.path, self.states)
        self.batch.session.get.return_value.status_code = 200
        self.batch.request.return_value.json.return_value = {'registration_enabled': True}
        with self.assertRaises(finalize.Failed):
            finalize.backup_resume_evidence(self.batch, self.path, self.states)

    def test_resume_runs_backup_and_enable_without_build_or_regression(self):
        previous = os.umask(0o077); self.addCleanup(os.umask, previous)
        self.batch.inspect.side_effect = lambda name: self.states[name]
        self.states['sam-yolo-mysql']['restart'] = 'unless-stopped'
        resources = Mock(); resources.thread.ident = None
        backup = self.root / 'backups'; snapshot = backup / '20261021T000000Z-12345678'
        snapshot.mkdir(parents=True)
        (snapshot / 'manifest.json').write_text(json.dumps({'success': True, 'restore_verified': True}))
        actual_path = Path
        def paths(value):
            return backup if value == '/var/lib/sam-yolo-backups' else actual_path(value)
        with patch.object(finalize.sys, 'platform', 'linux'), patch.object(finalize, 'Batch', return_value=self.batch), \
             patch.object(finalize, 'Path', side_effect=paths), patch.object(finalize, 'ResourceSample', return_value=resources), \
             patch.object(finalize, 'keep_sudo_alive'), patch.object(finalize, 'checked', return_value='enabled') as commands, \
             patch.object(finalize, 'build_backend') as build, patch.object(finalize, 'update_gateway') as gateway, \
             patch.object(finalize, 'Regression') as regression, redirect_stdout(io.StringIO()):
            self.assertEqual(finalize.main(['--resume-backup', str(self.path)]), 0)
        build.assert_not_called(); gateway.assert_not_called(); regression.assert_not_called()
        self.assertTrue(any(call.args[0][-2:] == ['start', 'sam-yolo-backup.service'] for call in commands.call_args_list))
        self.assertTrue(any('--enable' in call.args[0] for call in commands.call_args_list))
        reports = [p for p in (self.config / 'reports').glob('finalize-*.json') if p != self.path]
        self.assertEqual(len(reports), 1)
        self.assertTrue(json.loads(reports[0].read_text())['success'])


class BackendUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.work=self.root/'work';self.work.mkdir()
        self.before='YOLO_PUBLIC_BACKEND_IMAGE=sha256:'+('a'*64)+'\nYOLO_GATEWAY_NNP=false\n'
        (self.root/'compose.env').write_text(self.before)
        self.old={'id':'old-id','image':'sha256:'+'a'*64,'mounts':[{'Name':'private-fixture'}],
                  'running':True,'project':'sam-yolo','service':'backend'}
        self.image='sha256:'+'b'*64
        self.calls=[]
        self.batch=SimpleNamespace(config=self.root,repo=self.root,stamp='fixture',
            wait_backend=Mock(),inspect=Mock(side_effect=[self.old,{**self.old,'image':self.image}]),
            request=Mock(return_value=SimpleNamespace(json=lambda:{'registration_enabled':False})))
        def docker(*args):
            self.calls.append(args)
            return '0' if args[0]=='exec' else ''
        self.batch.docker=docker

    def test_only_tested_backend_changes_and_other_settings_survive(self):
        result=finalize.update_backend(self.batch,self.old,self.image,self.work)
        self.assertTrue(result['changed'])
        ups=[call for call in self.calls if 'up' in call]
        self.assertEqual(len(ups),1)
        self.assertEqual(ups[0][-1],'backend')
        self.assertIn('--no-deps',ups[0]);self.assertIn('--no-build',ups[0])
        self.assertIn(self.image,(self.root/'compose.env').read_text())
        self.assertIn('YOLO_GATEWAY_NNP=false',(self.root/'compose.env').read_text())
        self.assertEqual((self.work/'backend.compose.before.env').read_text(),self.before)

    def test_busy_database_preserves_original_config_and_container(self):
        self.batch.docker=lambda *args:'1'
        with self.assertRaises(finalize.Failed):
            finalize.update_backend(self.batch,self.old,self.image,self.work)
        self.assertEqual((self.root/'compose.env').read_text(),self.before)
        self.batch.wait_backend.assert_not_called()

    def test_foreign_or_changed_container_is_never_replaced(self):
        self.batch.inspect=Mock(return_value={**self.old,'project':'foreign'})
        with self.assertRaises(finalize.Failed):
            finalize.update_backend(self.batch,self.old,self.image,self.work)
        self.assertEqual(self.calls,[])

    def test_stale_private_image_setting_cannot_be_used_for_rollback(self):
        stale='YOLO_PUBLIC_BACKEND_IMAGE=sha256:'+('c'*64)+'\n'
        (self.root/'compose.env').write_text(stale)
        with self.assertRaisesRegex(finalize.Failed,'differs from running image'):
            finalize.update_backend(self.batch,self.old,self.image,self.work)
        self.assertEqual((self.root/'compose.env').read_text(),stale)
        self.assertEqual(self.calls,[])

    def test_startup_failure_restores_previous_image_and_waits_for_recovery(self):
        self.batch.wait_backend.side_effect=[finalize.Failed('health failed'),None]
        with self.assertRaises(finalize.Failed):
            finalize.update_backend(self.batch,self.old,self.image,self.work)
        self.assertEqual((self.root/'compose.env').read_text(),self.before)
        self.assertEqual(len([call for call in self.calls if 'up' in call]),2)
        self.assertEqual(self.batch.wait_backend.call_count,2)

    def test_rollback_does_not_overwrite_concurrent_private_edit(self):
        def fail():
            (self.root/'compose.env').write_text('concurrent edit')
            raise finalize.Failed('health failed')
        self.batch.wait_backend.side_effect=fail
        with self.assertRaisesRegex(finalize.Failed,'refusing automatic rollback'):
            finalize.update_backend(self.batch,self.old,self.image,self.work)
        self.assertEqual((self.root/'compose.env').read_text(),'concurrent edit')
        self.assertEqual(len([call for call in self.calls if 'up' in call]),1)

    def test_same_image_does_not_recreate_backend(self):
        result=finalize.update_backend(self.batch,self.old,self.old['image'],self.work)
        self.assertFalse(result['changed'])
        self.assertEqual(self.calls,[])

    def test_build_does_not_restart_or_reconfigure_production(self):
        self.batch.docker=Mock(return_value=self.image)
        with patch.object(finalize,'checked') as build:
            self.assertEqual(finalize.build_backend(self.batch),self.image)
        command=build.call_args.args[0]
        self.assertEqual(command[:4],['sudo','-n','docker','build'])
        self.assertIn('--pull=false',command)
        self.assertEqual(self.batch.docker.call_args.args[:2],('image','inspect'))
        self.batch.wait_backend.assert_not_called()


if __name__=='__main__':unittest.main()

import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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


if __name__=='__main__':unittest.main()

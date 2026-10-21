"""Ollama 0.40.6 legacy/v2, manifest-list and blob integrity contracts."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lab_maintenance as app


class NativeManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.files = {}
        config, weights = self.blob(b'{}'), self.blob(b'weights')
        self.child = {'schemaVersion': 2, 'mediaType': 'application/vnd.docker.distribution.manifest.v2+json',
                      'config': {'mediaType': '', 'digest': 'sha256:' + config, 'size': 2},
                      'layers': [{'mediaType': '', 'digest': 'sha256:' + weights, 'size': 7}],
                      'runner': 'llamacpp', 'format': 'gguf'}
        self.body = json.dumps(self.child, separators=(',', ':')).encode()
        self.digest = hashlib.sha256(self.body).hexdigest()
        self.inventory = [('test:latest', self.digest)]
        self.named = 'manifests-v2/ollama.com/library/test/latest'

    def blob(self, data):
        digest = hashlib.sha256(data).hexdigest()
        self.files['blobs/sha256-' + digest] = data
        return digest

    def pack(self, output):
        with tarfile.open(fileobj=output, mode='w:gz') as archive:
            for name, data in sorted(self.files.items()):
                member = tarfile.TarInfo(name); member.size = len(data)
                archive.addfile(member, io.BytesIO(data))

    def validate(self):
        path = self.root / 'archive.tar.gz'
        with path.open('wb') as output:
            self.pack(output)
        return app.validate_native_models(path, self.inventory)

    def list_parent(self, *, inline=False, other_runner=False):
        self.blob(self.body)
        child = self.child if inline else {'mediaType': self.child['mediaType'],
            'digest': 'sha256:' + self.digest, 'runner': 'llamacpp', 'format': 'gguf'}
        children = [child]
        if other_runner:
            children.append({'mediaType': self.child['mediaType'], 'digest': 'sha256:' + 'f'*64,
                             'runner': 'mlx', 'format': 'safetensors'})
        parent = {'schemaVersion': 2, 'mediaType': 'application/vnd.ollama.manifest.list.v2+json',
                  'manifests': children}
        self.files[self.named] = json.dumps(parent, indent=2).encode()

    def test_v2_only_layout_is_verified(self):
        self.files[self.named] = self.body
        self.assertEqual(self.validate()['named_models'], 1)
        self.assertFalse(any('manifests' in Path(name).parts for name in self.files))

    def test_list_reports_selected_child_not_parent_hash(self):
        self.list_parent()
        self.assertNotEqual(hashlib.sha256(self.files[self.named]).hexdigest(), self.digest)
        self.assertEqual(self.validate()['verified_blobs'], 3)

    def test_inline_child_uses_upstream_canonical_field_order(self):
        # Change the stored inline order/whitespace; the API digest still uses
        # Manifest.MarshalJSON order, not parent bytes or sorted JSON keys.
        self.child = dict(reversed(list(self.child.items())))
        self.list_parent(inline=True)
        del self.files['blobs/sha256-' + self.digest]
        self.assertEqual(self.validate()['named_models'], 1)

    def test_uninstalled_other_platform_child_does_not_break_local_backup(self):
        self.list_parent(other_runner=True)
        self.validate()

    def test_missing_selected_child_or_its_weights_is_rejected(self):
        self.list_parent()
        for filename in ('blobs/sha256-' + self.digest,
                         'blobs/' + self.child['layers'][0]['digest'].replace(':', '-')):
            with self.subTest(filename=filename):
                saved = self.files.pop(filename)
                with self.assertRaisesRegex(RuntimeError, 'inventory mismatch'):
                    self.validate()
                self.files[filename] = saved

    def test_v2_supersedes_stale_legacy_manifest(self):
        self.files[self.named] = self.body
        self.files['manifests/registry.ollama.ai/library/test/latest'] = b'{}'
        self.validate()

    def test_unrelated_blob_or_another_model_cannot_satisfy_inventory(self):
        self.blob(self.body)
        self.files[self.named.replace('/test/', '/other/')] = self.body
        with self.assertRaisesRegex(RuntimeError, 'named model missing'):
            self.validate()

    def test_corrupt_blob_remains_rejected(self):
        self.files[self.named] = self.body
        self.files['blobs/' + self.child['layers'][0]['digest'].replace(':', '-')] = b'bad'
        with self.assertRaisesRegex(RuntimeError, 'blob fingerprint'):
            self.validate()

    def test_real_v2_manifest_link_export_then_inventory_verification(self):
        self.list_parent(other_runner=True)
        parent = self.files.pop(self.named)
        parent_digest = self.blob(parent)
        store = self.root / 'models'; store.mkdir()
        for name, data in self.files.items():
            path = store / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        named = store / self.named; named.parent.mkdir(parents=True)
        named.symlink_to(os.path.relpath(store / ('blobs/sha256-' + parent_digest), named.parent))
        archive = self.root / 'export.tar.gz'
        with archive.open('wb') as output:
            app.write_native_models(store, output)
        self.assertEqual(app.validate_native_models(archive, self.inventory)['named_models'], 1)
        self.assertTrue(named.is_symlink())  # Original model store is untouched.

    def test_api_change_before_export_is_rejected_without_reading_models(self):
        worker = app.Maintenance({'gid': os.getgid()}, self.root)
        worker.report['ollama_models'] = {'models': [{'name': name, 'digest': digest} for name, digest in self.inventory]}
        with patch.object(worker, 'ollama_inventory', return_value={'models': []}), \
             patch.object(app, 'capture_native_models') as capture:
            with self.assertRaisesRegex(RuntimeError, 'API inventory changed'):
                worker.cache_models()
        capture.assert_not_called()

    def test_api_change_after_export_is_not_claimed_as_success(self):
        self.files[self.named] = self.body
        worker = app.Maintenance({'gid': os.getgid()}, self.root)
        before = {'models': [{'name': name, 'digest': digest} for name, digest in self.inventory]}
        worker.report['ollama_models'] = before
        with patch.object(worker, 'ollama_inventory', side_effect=[before, {'models': []}]), \
             patch.object(app, 'capture_native_models', side_effect=lambda config, output: self.pack(output)), \
             patch.object(app, 'trusted'), patch.object(app.os, 'chown'):
            with self.assertRaisesRegex(RuntimeError, 'API inventory changed'):
                worker.cache_models()


if __name__ == '__main__':
    unittest.main()

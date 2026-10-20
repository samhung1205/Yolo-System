"""Behavioural checks for document drift and staged-content validation."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('check_docs', Path(__file__).resolve().parents[1]/'check_docs.py')
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


class CoverageTests(unittest.TestCase):
    def test_api_change_requires_contract_even_if_user_manual_updated(self):
        errors = check.coverage_errors({'backend/app/api/routes/chat.py', 'README.md'})
        self.assertTrue(any('API 契約' in item for item in errors))

    def test_api_and_schema_owners_cover_runtime_change(self):
        self.assertEqual(check.coverage_errors({'backend/app/api/routes/chat.py', 'docs/api-spec.md'}), [])
        errors = check.coverage_errors({'backend/migrations/versions/0014.py', 'README.md'})
        self.assertTrue(any('資料庫' in item for item in errors))

    def test_explicit_nonbehavioural_note_is_reviewable_exit(self):
        self.assertEqual(check.coverage_errors({'backend/app/services/x.py', 'docs/change-notes.md'}), [])

    def test_tests_and_unrelated_files_do_not_force_document_churn(self):
        self.assertEqual(check.coverage_errors({'backend/tests/test_x.py', 'assets/icon.png'}), [])

    def test_web_deploy_and_dependency_changes_have_different_owners(self):
        for name, label in [('web-frontend/src/pages/ChatPage.jsx', 'Web 操作'),
                            ('deploy/compose.public.yaml', '部署／維運'),
                            ('web-frontend/package-lock.json', '依賴／建置')]:
            self.assertTrue(any(label in x for x in check.coverage_errors({name})))


class LinksTests(unittest.TestCase):
    def validate(self, documents):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for name, content in documents.items():
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            return check.link_errors(root, sorted(documents), lambda name: (root/name).read_text(), lambda name: (root/name).exists())

    def test_missing_file_heading_and_unindexed_document_are_reported(self):
        errors = self.validate({'docs/README.md':'[missing](absent.md)\n[anchor](a.md#不存在)',
                                'docs/archive/README.md':'', 'docs/a.md':'# 存在', 'docs/orphan.md':'# 遺漏'})
        self.assertTrue(any('找不到連結目標' in x for x in errors))
        self.assertTrue(any('找不到標題錨點' in x for x in errors))
        self.assertTrue(any('尚未列入索引' in x for x in errors))

    def test_chinese_anchor_spaces_and_fenced_examples(self):
        self.assertEqual(self.validate({'docs/README.md':'[a](<a%20b.md#中文標題>)\n```md\n[example](missing.md)\n```',
                                        'docs/archive/README.md':'', 'docs/a b.md':'# 中文標題'}), [])

    def test_frozen_original_is_indexed_but_not_reinterpreted(self):
        self.assertEqual(self.validate({'docs/README.md':'', 'docs/archive/README.md':'[old](old.md)',
                                        'docs/archive/old.md':'[historical](removed-module.py)'}), [])

    def test_link_outside_repository_rejected(self):
        errors = self.validate({'docs/README.md':'[outside](../../private.md)', 'docs/archive/README.md':''})
        self.assertTrue(any('超出專案' in x for x in errors))


class GitSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run_git('init', '-q')
        self.write('docs/README.md', '[API](api-spec.md)')
        self.write('docs/archive/README.md', '')
        self.write('docs/api-spec.md', '# API')
        self.write('backend/app/api/routes/demo.py', '# before')
        self.run_git('add', '.')
        self.run_git('-c', 'user.name=Docs Test', '-c', 'user.email=docs@example.invalid', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture')

    def run_git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)

    def write(self, name, body):
        target = self.root/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)

    def run_check(self, *args):
        output = io.StringIO()
        with patch.object(check, 'ROOT', self.root), patch.object(sys, 'argv', ['check_docs', *args]), redirect_stdout(output):
            return check.main(), output.getvalue()

    def test_unstaged_document_does_not_cover_staged_api_then_staging_it_passes(self):
        self.write('backend/app/api/routes/demo.py', '# changed endpoint')
        self.run_git('add', 'backend/app/api/routes/demo.py')
        self.write('docs/api-spec.md', '# API\nUpdated contract')
        code, output = self.run_check('--staged')
        self.assertEqual(code, 1)
        self.assertIn('API 契約', output)
        self.run_git('add', 'docs/api-spec.md')
        self.assertEqual(self.run_check('--staged')[0], 0)

    def test_staged_links_are_not_repaired_by_unstaged_worktree(self):
        self.write('docs/README.md', '[broken](missing.md)')
        self.run_git('add', 'docs/README.md')
        self.write('docs/README.md', '[API](api-spec.md)')
        self.assertEqual(self.run_check('--staged')[0], 1)
        self.assertEqual(self.run_check()[0], 0)

    def test_base_comparison_includes_new_untracked_source(self):
        self.write('backend/app/api/routes/new.py', '# new API')
        self.assertIn('backend/app/api/routes/new.py', check.changed_paths(self.root, base='HEAD'))
        self.assertEqual(self.run_check('--base', 'HEAD')[0], 1)


if __name__ == '__main__':
    unittest.main()

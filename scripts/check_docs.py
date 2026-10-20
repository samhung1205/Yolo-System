"""Check maintained Markdown links, document indexing and staged doc coverage.

No dependencies, network, file writes or automatic text generation.
"""
import argparse
from fnmatch import fnmatch
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ('README.md', 'AGENTS.md', 'CLAUDE.md', 'DEPLOY.md',
         'web-frontend/README.md', 'web-frontend/DESIGN.md', 'desktop-app/README.md')
# Each affected area must update at least one listed owner. Semantic accuracy
# still needs human review; an explicit non-behavioural note is a reviewable exit.
RULES = (
    ('API 契約', ('backend/app/api/routes/*.py', 'backend/app/schemas/*.py'), ('docs/api-spec.md',)),
    ('資料庫', ('backend/app/models/*.py', 'backend/migrations/versions/*.py'), ('docs/database-design.md',)),
    ('後端行為', ('backend/app/**/*.py',), ('README.md', 'docs/api-spec.md', 'docs/database-design.md', 'docs/architecture.md', 'docs/lab-operations.md')),
    ('Web 操作', ('web-frontend/src/pages/*', 'web-frontend/src/components/*', 'web-frontend/src/services/*', 'web-frontend/src/router/*', 'web-frontend/src/hooks/*', 'web-frontend/src/state/*', 'web-frontend/src/styles.css'), ('README.md', 'web-frontend/README.md')),
    ('依賴／建置', ('web-frontend/package*.json', 'web-frontend/vite.config.*', 'backend/requirements.txt', 'deploy/backend-linux.lock', '.github/workflows/*'), ('docs/development.md', 'web-frontend/README.md', 'docs/lab-phase6-finalization.md')),
    ('部署／維運', ('deploy/*.py', 'deploy/*.yaml', 'deploy/*.conf', 'deploy/*Dockerfile', 'deploy/Caddyfile*'), ('DEPLOY.md', 'docs/lab-operations.md', 'docs/lab-phase6-finalization.md')),
    ('Desktop', ('desktop-app/*.py', 'Login.py', 'Register.py', 'MainUI.py', 'Admin*.py', 'AICSMain.py', 'AgentWindow.py', 'PersonFormMain.py', 'detect_mainui.py'), ('desktop-app/README.md',)),
    ('協作規範', ('AGENTS.md', 'CLAUDE.md'), ('docs/documentation-policy.md',)),
)
LINK = re.compile(r'!?\[[^\]\n]*\]\((<[^>\n]+>|[^\s)]+)(?:\s+"[^"]*")?\)')


def git(root, *args):
    result = subprocess.run(['git', *args], cwd=root, capture_output=True, check=True)
    return result.stdout


def changed_paths(root, staged=False, base=None):
    if staged:
        data = git(root, 'diff', '--cached', '--name-only', '-z', '--diff-filter=ACDMRT')
    else:
        data = git(root, 'diff', '--name-only', '-z', '--diff-filter=ACDMRT', base or 'HEAD')
        data += git(root, 'ls-files', '--others', '--exclude-standard', '-z')
    return set(data.decode().strip('\0').split('\0')) - {''}


def coverage_errors(changed):
    if 'docs/change-notes.md' in changed:
        return []
    errors = []
    for label, patterns, owners in RULES:
        triggers = sorted(p for p in changed if any(fnmatch(p, pat) for pat in patterns))
        if triggers and not set(owners).intersection(changed):
            errors.append(f'{label} 變更未同步文件：{triggers[0]} → 更新 ' + ' 或 '.join(owners))
    return errors


def prose(text):
    # Ignore code examples; URLs and example file paths inside them aren't links.
    lines, fence = [], None
    for line in text.splitlines():
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            if fence is None:
                fence = marker.group(1)[0]
            elif marker.group(1)[0] == fence:
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return '\n'.join(lines)


def anchors(text):
    found, counts = set(), {}
    for line in prose(text).splitlines():
        if not re.match(r'^#{1,6}\s+', line):
            continue
        title = re.sub(r'^#{1,6}\s+|\s+#+$', '', line).lower()
        title = re.sub(r'<[^>]*>', '', title)
        title = re.sub(r'[^\w\- ]', '', title).replace(' ', '-')
        count = counts.get(title, 0)
        counts[title] = count + 1
        found.add(title + (f'-{count}' if count else ''))
    return found


def link_errors(root, documents, read, exists):
    root = root.resolve()
    errors = []
    for name in documents:
        # Frozen originals intentionally record old paths; current entry points
        # and archive index are checked, not rewritten historical evidence.
        if name.startswith('docs/archive/') and name != 'docs/archive/README.md':
            continue
        for match in LINK.finditer(prose(read(name))):
            url = unquote(match.group(1).strip('<>'))
            parts = urlsplit(url)
            if parts.scheme or parts.netloc or url.startswith('/'):
                continue
            target = (root / name).parent / parts.path if parts.path else root / name
            target = target.resolve()
            if not target.is_relative_to(root):
                errors.append(f'{name}：連結超出專案：{url}')
                continue
            relative = target.relative_to(root).as_posix()
            if not exists(relative):
                errors.append(f'{name}：找不到連結目標：{url}')
            elif parts.fragment and relative.endswith('.md') and parts.fragment not in anchors(read(relative)):
                errors.append(f'{name}：找不到標題錨點：{url}')
    # All docs should be discoverable directly in one of the two indexes.
    index_links = set()
    for index in ('docs/README.md', 'docs/archive/README.md'):
        if not exists(index):
            errors.append(f'缺少文件入口：{index}')
            continue
        for match in LINK.finditer(prose(read(index))):
            parts = urlsplit(unquote(match.group(1).strip('<>')))
            if not parts.scheme and parts.path and not parts.path.startswith('/'):
                target = ((root/index).parent/parts.path).resolve()
                if target.is_relative_to(root):
                    index_links.add(target.relative_to(root).as_posix())
    for name in documents:
        if name.startswith('docs/') and name not in ('docs/README.md', 'docs/archive/README.md') and name not in index_links:
            errors.append(f'文件尚未列入索引：{name}')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument('--staged', action='store_true', help='Validate staged links and changed-area documentation together')
    choice.add_argument('--base', help='Compare working tree and untracked files against a Git ref')
    args = parser.parse_args()
    root = ROOT.resolve()
    if args.staged:
        files = set(git(root, 'ls-files', '-z').decode().strip('\0').split('\0')) - {''}
        # git ls-files also lists a path staged for removal only if still present
        # in the index; using the index keeps unstaged docs from hiding omissions.
        read = lambda name: git(root, 'show', ':' + name).decode()
        exists = lambda name: name in files or any(p.startswith(name + '/') for p in files)
    else:
        files = {p.relative_to(root).as_posix() for p in (root/'docs').rglob('*.md')}
        files.update(name for name in ENTRY if (root/name).exists())
        read = lambda name: (root/name).read_text()
        exists = lambda name: (root/name).exists()
    documents = sorted(name for name in files if name.endswith('.md') and (name.startswith('docs/') or name in ENTRY))
    errors = link_errors(root, documents, read, exists)
    if args.staged or args.base:
        errors += coverage_errors(changed_paths(root, staged=args.staged, base=args.base))
    for error in errors:
        print('FAIL: ' + error)
    if errors:
        print('請更新對應內容；純內部修改可在 docs/change-notes.md 說明不需更新的原因。')
        return 1
    print(f'PASS: 文件索引／現行連結與錨點（{len(documents)} 份文件）' + ('／變更同步' if args.staged or args.base else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

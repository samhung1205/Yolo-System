"""Root-owned, standard-library-only lab backup worker. Installed by the installer.

Never imports application code or executes a writable project script as root.
User-owned files are read in a child after permanently dropping privileges.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import stat
import subprocess
import tarfile
import tempfile
import time
from urllib.request import build_opener, ProxyHandler

CONFIG = Path('/etc/sam-yolo-maintenance.json')
ROOT = Path('/var/lib/sam-yolo-backups')
STAMP = re.compile(r'\d{8}T\d{6}Z-[0-9a-f]{8}')
NAMES = ('sam-yolo-backend', 'sam-yolo-web', 'sam-yolo-gateway', 'sam-yolo-mysql')
SQL_CLIENT = ('export MYSQL_PWD="$MYSQL_PASSWORD"; exec mysql --protocol=TCP '
              '--host=127.0.0.1 --user="$MYSQL_USER" --batch --skip-column-names '
              '--default-character-set=utf8mb4 "$MYSQL_DATABASE" "$@"')
DUMP = ('export MYSQL_PWD="$MYSQL_PASSWORD"; exec mysqldump --protocol=TCP '
        '--host=127.0.0.1 --user="$MYSQL_USER" --single-transaction --quick '
        '--no-tablespaces --set-gtid-purged=OFF --hex-blob --order-by-primary '
        '--default-character-set=utf8mb4 --skip-comments --skip-dump-date "$MYSQL_DATABASE"')


def need(value, message):
    if not value:
        raise RuntimeError(message)


def checksum(path, compressed=False):
    digest = hashlib.sha256()
    with (gzip.open(path, 'rb') if compressed else path.open('rb')) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_sql(path):
    # MySQL #110825: only the redundant charset before a matching COLLATE.
    rule = re.compile(rb'^( +`[A-Za-z0-9_]+` (?:char\([0-9]+\)|varchar\([0-9]+\)|tinytext|text|mediumtext|longtext)) CHARACTER SET utf8mb4(?= COLLATE utf8mb4_[A-Za-z0-9_]+(?:[ ,\r\n]|$))')
    digest = hashlib.sha256()
    inside = False
    with gzip.open(path, 'rb') as stream:
        for line in stream:
            if re.fullmatch(rb'CREATE TABLE `[A-Za-z0-9_]+` \(\r?\n', line):
                inside = True
            if inside:
                line = rule.sub(rb'\1', line, count=1)
                if line.startswith(b')'):
                    inside = False
            digest.update(line)
    return digest.hexdigest()


def safe_write(path, data, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)


def trusted(path, directory=False):
    info = path.lstat()
    need(not path.is_symlink() and info.st_uid == 0 and not info.st_mode & 0o022
         and (path.is_dir() if directory else path.is_file()), 'Untrusted maintenance path')


def retained_candidates(root, keep):
    """Only our successful, unpinned snapshots; original backup root is separate."""
    valid = []
    for path in root.iterdir():
        if not STAMP.fullmatch(path.name) or path.is_symlink() or not path.is_dir():
            continue
        manifest = path / 'manifest.json'
        if manifest.is_symlink() or not manifest.is_file():
            continue
        report = json.loads(manifest.read_text())
        if report.get('kind') == 'sam-yolo-managed-v1' and report.get('success') is True and not report.get('pinned'):
            valid.append(path)
    return sorted(valid, key=lambda p: p.name, reverse=True)[keep:]


def capture_user_files(config, archive, manifest):
    """Read all writable user sources with the user's permissions, never root's."""
    pid = os.fork()
    if pid == 0:
        try:
            os.setgroups([])
            os.setgid(config['gid'])
            os.setuid(config['uid'])
            repo, home = Path(config['repo']), Path(config['home'])
            tracked = subprocess.run(['/usr/bin/git', '-C', str(repo), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                                     capture_output=True, check=True, timeout=30).stdout
            sources = {}
            for value in tracked.split(b'\0'):
                if value:
                    name = os.fsdecode(value)
                    need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe source path')
                    path = repo / name
                    if path.is_file():
                        sources['source/' + name] = path
            for folder in ('backend/static', 'backend/pt', 'web-frontend/dist'):
                base = repo / folder
                need(base.is_dir() and not base.is_symlink(), 'Missing data directory')
                for path in base.rglob('*'):
                    need(not path.is_symlink(), 'Symlink in data directory')
                    if path.is_file():
                        sources['source/' + path.relative_to(repo).as_posix()] = path
            for name, path in {
                'backend.env': repo / 'backend/.env',
                'compose.env': home / '.config/yolo-system/compose.env',
                'mysql.env': home / '.config/yolo-system/mysql.env',
                'nginx.lab.conf': home / '.config/yolo-system/nginx.lab.conf',
            }.items():
                sources['private/' + name] = path
            files = {}
            with tarfile.open(fileobj=archive, mode='w:gz', compresslevel=1) as output:
                for name, path in sorted(sources.items()):
                    need(not path.is_symlink(), 'Symlink in backup source')
                    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                    with os.fdopen(fd, 'rb') as stream:
                        before = os.fstat(stream.fileno())
                        import stat
                        need(stat.S_ISREG(before.st_mode), 'Non-regular source')
                        digest = hashlib.sha256()
                        class Reader:
                            def read(self, size=-1):
                                chunk = stream.read(size)
                                digest.update(chunk)
                                return chunk
                        info = tarfile.TarInfo(name)
                        info.size, info.mode = before.st_size, 0o600
                        output.addfile(info, Reader())
                        after = os.fstat(stream.fileno())
                        need((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'Source changed')
                    files[name] = {'size': info.size, 'sha256': digest.hexdigest()}
            archive.flush()
            manifest.write(json.dumps(files).encode())
            manifest.flush()
            os._exit(0)
        except BaseException:
            os._exit(1)  # No user data, config values, or exception text in journal.
    _, status = os.waitpid(pid, 0)
    need(os.waitstatus_to_exitcode(status) == 0, 'User source capture failed')


class ModelSourceError(RuntimeError):
    """Fixed diagnostic messages only; never include source contents or paths."""


def write_native_models(root, output):
    """Materialize internal aliases; emit only ordinary files and directories."""
    if Path(root).is_symlink() or not Path(root).is_dir():
        raise ModelSourceError('Native model store root changed')
    root = Path(root).resolve(strict=True)
    entries = []

    def visit(path, name, ancestors):
        try:
            target = path.resolve(strict=True)
        except (OSError, RuntimeError):
            raise ModelSourceError('Broken or cyclic native model link') from None
        if not target.is_relative_to(root):
            raise ModelSourceError('Native model link leaves model store')
        info = target.stat()
        identity = (info.st_dev, info.st_ino)
        if stat.S_ISDIR(info.st_mode):
            if identity in ancestors:
                raise ModelSourceError('Cyclic native model directory link')
            entries.append((target, name, info))
            for child in sorted(target.iterdir()):
                visit(child, name / child.name, ancestors | {identity})
        elif stat.S_ISREG(info.st_mode):
            entries.append((target, name, info))
        else:
            raise ModelSourceError('Unsupported native model source type')

    # Validate the entire small metadata tree before reading/compressing GBs.
    visit(root, Path('.'), set())
    with tarfile.open(fileobj=output, mode='w:gz', compresslevel=1, dereference=True) as archive:
        for target, name, planned in entries:
            if stat.S_ISDIR(planned.st_mode):
                info = archive.gettarinfo(str(target), arcname=name.as_posix())
                if not info.isdir():
                    raise ModelSourceError('Native model directory changed')
                archive.addfile(info)
            else:
                fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, 'rb') as source:
                    before = os.fstat(source.fileno())
                    if not stat.S_ISREG(before.st_mode) or any(
                        getattr(before, key) != getattr(planned, key)
                        for key in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns')
                    ):
                        raise ModelSourceError('Native model file changed')
                    info = archive.gettarinfo(fileobj=source, arcname=name.as_posix())
                    archive.addfile(info, source)
                    after = os.fstat(source.fileno())
                    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise ModelSourceError('Native model file changed')
    output.flush()


def capture_native_models(config, output, *, timeout=1200):
    """Read model contents only after permanently dropping to the Ollama UID."""
    with tempfile.TemporaryFile() as diagnostic:
        pid = os.fork()
        if pid == 0:
            try:
                os.setgroups([])
                os.setgid(config['ollama_gid'])
                os.setuid(config['ollama_uid'])
                write_native_models(config['ollama_models'], output)
                os._exit(0)
            except BaseException as exc:
                message = str(exc) if isinstance(exc, ModelSourceError) else type(exc).__name__
                diagnostic.write(message.encode()); diagnostic.flush()
                os._exit(1)
        deadline = time.monotonic() + timeout
        reaped = False
        try:
            while True:
                finished, status = os.waitpid(pid, os.WNOHANG)
                if finished:
                    reaped = True
                    break
                need(time.monotonic() < deadline, 'Native model capture timed out')
                time.sleep(0.05)
        finally:
            if not reaped:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                os.waitpid(pid, 0)
        if os.waitstatus_to_exitcode(status) != 0:
            diagnostic.seek(0)
            raise RuntimeError('Native model capture failed: ' + diagnostic.read().decode())


def model_inventory_key(name):
    """Normalize public registry aliases as Ollama v0.40.6 does."""
    need(isinstance(name, str) and name and not any(c.isspace() for c in name), 'Invalid Ollama model name')
    parts = name.split('/')
    tail = parts.pop()
    model, separator, tag = tail.partition(':')
    tag = tag if separator else 'latest'
    if not parts:
        host, namespace = 'registry.ollama.ai', 'library'
    elif len(parts) == 1:
        if '.' in parts[0] or ':' in parts[0] or parts[0] == 'localhost':
            host, namespace = parts[0], 'library'
        else:
            host, namespace = 'registry.ollama.ai', parts[0]
    else:
        need(len(parts) == 2, 'Unsupported Ollama model name')
        host, namespace = parts
    host = host.replace('%3A', ':').replace('%3a', ':').lower()
    if host == 'ollama.com':
        host = 'registry.ollama.ai'
    need(all(v and v not in ('.', '..') for v in (host, namespace, model, tag)), 'Invalid Ollama model name')
    return tuple(v.casefold() for v in (host, namespace, model, tag))


def manifest_digest(value):
    match = re.fullmatch(r'(?:sha256[:-])?([0-9a-fA-F]{64})', value or '')
    need(match, 'Invalid Ollama manifest digest')
    return match[1].lower()


def canonical_inline_manifest(document):
    """Mirror Manifest.MarshalJSON / Layer field order for inline list children."""
    def layer(value):
        value = value or {}
        result = {key: value.get(key, default) for key, default in
                  (('mediaType', ''), ('digest', ''), ('size', 0))}
        for key in ('from', 'name'):
            if value.get(key):
                result[key] = value[key]
        return result
    if document.get('mediaType') == 'application/vnd.ollama.manifest.list.v2+json':
        body = {'schemaVersion': document.get('schemaVersion', 0), 'mediaType': document['mediaType'],
                'manifests': [json.loads(canonical_inline_manifest(child)) for child in document.get('manifests', [])]}
    elif document.get('digest') and not (document.get('config') or {}).get('digest') and not document.get('layers'):
        body = {'mediaType': document.get('mediaType', ''), 'digest': 'sha256:' + manifest_digest(document['digest'])}
    else:
        body = {'schemaVersion': document.get('schemaVersion', 0), 'mediaType': document.get('mediaType', ''),
                'config': layer(document.get('config')), 'layers': None if document.get('layers') is None
                else [layer(value) for value in document['layers']]}
    if document.get('mediaType') != 'application/vnd.ollama.manifest.list.v2+json':
        for key in ('runner', 'format'):
            if document.get(key):
                body[key] = document[key]
    text = json.dumps(body, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    # encoding/json escapes HTML-sensitive characters and these separators.
    for value, replacement in (('&', r'\u0026'), ('<', r'\u003c'), ('>', r'\u003e'),
                               ('\u2028', r'\u2028'), ('\u2029', r'\u2029')):
        text = text.replace(value, replacement)
    return text.encode()


def validate_native_models(path, inventory):
    """Verify named legacy/v2 manifests, selected children and all blob bytes."""
    blobs, documents, named, seen = {}, {}, {}, set()
    with tarfile.open(path) as archive:
        for member in archive:
            relative = Path(member.name)
            need(not member.issym() and not member.islnk() and not relative.is_absolute()
                 and '..' not in relative.parts and (member.isfile() or member.isdir()), 'Unsafe native model archive')
            key = relative.as_posix()
            need(key not in seen, 'Duplicate native model archive entry')
            seen.add(key)
            if not member.isfile():
                continue
            small = member.size <= 4 * 1024 * 1024
            with archive.extractfile(member) as source:
                raw = source.read() if small else None
                actual = hashlib.sha256(raw).hexdigest() if small else hash_stream(source)
            document = None
            if raw is not None:
                try:
                    candidate = json.loads(raw)
                    if isinstance(candidate, dict):
                        document = candidate
                except (ValueError, UnicodeError):
                    pass
            if relative.parts[0] == 'blobs':
                need(len(relative.parts) == 2 and relative.name == 'sha256-' + actual, 'Ollama blob fingerprint mismatch')
                blobs[actual] = member.size
                documents[actual] = document
            if relative.parts[0] in ('manifests', 'manifests-v2') and len(relative.parts) == 5:
                _, host, namespace, model, tag = relative.parts
                name = model_inventory_key(host + '/' + namespace + '/' + model + ':' + tag)
                priority = int(relative.parts[0] == 'manifests-v2')
                if name not in named or priority > named[name][0]:
                    named[name] = (priority, actual, document)

    def runnable(document, digest, trail=frozenset()):
        if not isinstance(document, dict):
            return set()
        need(digest not in trail and len(trail) < 32, 'Cyclic or excessively deep Ollama manifest list')
        if document.get('mediaType') == 'application/vnd.ollama.manifest.list.v2+json':
            children = document.get('manifests')
            need(isinstance(children, list), 'Invalid Ollama manifest list')
            verified = set()
            for child in children:
                need(isinstance(child, dict), 'Invalid Ollama child manifest')
                if child.get('digest'):
                    child_digest = manifest_digest(child['digest'])
                    # Other-platform children may legitimately not be installed.
                    child_document = documents.get(child_digest)
                else:
                    child_digest = hashlib.sha256(canonical_inline_manifest(child)).hexdigest()
                    child_document = child
                verified.update(runnable(child_document, child_digest, trail | {digest}))
            return verified | {digest} if verified else set()
        layers = document.get('layers')
        if not isinstance(layers, list):
            return set()
        config = document.get('config') or {}
        need(isinstance(config, dict), 'Invalid Ollama config descriptor')
        references = layers + ([config] if config.get('digest') else [])
        if not references:
            return set()
        for entry in references:
            need(isinstance(entry, dict), 'Invalid Ollama layer descriptor')
            reference = manifest_digest(entry.get('digest'))
            if reference not in blobs:
                return set()
            if 'size' in entry:
                need(entry['size'] == blobs[reference], 'Ollama layer size mismatch')
        return {digest}

    for name, expected in inventory:
        key = model_inventory_key(name)
        need(key in named, 'Ollama named model missing from legacy/v2 archive')
        _, digest, document = named[key]
        need(manifest_digest(expected) in runnable(document, digest),
             'Ollama manifest inventory mismatch (legacy/v2/list checked)')
    return {'named_models': len(named), 'verified_blobs': len(blobs)}


class Maintenance:
    def __init__(self, config, root=ROOT):
        self.config, self.root = config, root
        self.env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin', 'HOME': '/root', 'LANG': 'C.UTF-8'}
        self.stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + secrets.token_hex(4)
        self.output = root / self.stamp
        self.paused = None
        self.temporary = None
        self.volume = None
        self.report = {'kind': 'sam-yolo-managed-v1', 'success': False, 'pinned': False, 'checks': []}

    def ollama_inventory(self):
        with build_opener(ProxyHandler({})).open('http://127.0.0.1:11434/api/tags', timeout=15) as response:
            return json.load(response)

    def docker(self, *args, timeout=180, private_env=None):
        result = subprocess.run([self.config['docker'], *args], env={**self.env, **(private_env or {})}, capture_output=True, timeout=timeout)
        need(result.returncode == 0, 'Docker operation failed: ' + args[0])
        return result.stdout.decode()

    def inspect(self, name):
        # Select fields before output, never persist Config.Env or health logs.
        template = '{"id":{{json .Id}},"image":{{json .Image}},"running":{{.State.Running}},"restart":{{json .HostConfig.RestartPolicy.Name}},"labels":{{json .Config.Labels}},"mounts":{{json .Mounts}}}'
        return json.loads(self.docker('inspect', '--type', 'container', '--format', template, name))

    def sql(self, sql, container='sam-yolo-mysql'):
        return self.docker('exec', container, 'sh', '-c', SQL_CLIENT, 'mysql', '-e', sql).strip()

    def health(self):
        opener = build_opener(ProxyHandler({}))
        for port in (8000, 8080):
            with opener.open(f'http://127.0.0.1:{port}/api/health', timeout=15) as response:
                need(json.load(response).get('database') == 'connected', 'Database health failed')

    def public_health(self):
        import socket
        import ssl
        context=ssl.create_default_context()
        with socket.create_connection(('140.113.135.113',443),timeout=15) as connection:
            with context.wrap_socket(connection,server_hostname='140.113.135.113') as secured:
                expires=ssl.cert_time_to_seconds(secured.getpeercert()['notAfter'])
        remaining=expires-time.time()
        need(remaining>24*3600,'HTTPS certificate expires within 24 hours; check Caddy renewal')
        self.report['certificate_hours_remaining']=round(remaining/3600,2)

    def preflight(self):
        trusted(self.root, directory=True)
        need(shutil.disk_usage(self.root).free > 10 * 1024**3, 'Less than 10 GiB free; backup refused')
        states = {name: self.inspect(name) for name in NAMES}
        for name, state in states.items():
            need(state['running'], 'Service is stopped: ' + name)
            if name != 'sam-yolo-mysql':
                need((state.get('labels') or {}).get('com.docker.compose.project') == 'sam-yolo', 'Foreign container')
                need((state.get('labels') or {}).get('com.docker.compose.service') == name.removeprefix('sam-yolo-'), 'Foreign service')
        db = states['sam-yolo-mysql']
        need(any(m.get('Name') == 'sam-yolo-mysql-data' and m['Destination'] == '/var/lib/mysql' for m in db['mounts']), 'Unexpected DB volume')
        self.health()
        try:
            self.public_health()
        except Exception:
            self.report['operational_warning']='Check HTTPS certificate renewal'
        try:
            self.report['ollama_models'] = self.ollama_inventory()
        except Exception:
            self.report['operational_warning']='Check Ollama availability'
        need(self.docker('exec', db['id'], 'sh', '-c', 'printf "%s|%s" "$MYSQL_DATABASE" "$MYSQL_USER"') == 'yolo|yolo_app', 'Unexpected DB identity')
        need(self.sql("SELECT COUNT(*) FROM detection_tasks WHERE status IN ('pending','processing');") == '0', 'Active or interrupted detection; backup deferred')
        need(self.sql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE' AND ENGINE<>'InnoDB';") == '0', 'Non-InnoDB tables')
        need(self.sql('SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE();') == '0', 'Unsupported routines')
        need(self.sql('SELECT COUNT(*) FROM information_schema.EVENTS WHERE EVENT_SCHEMA=DATABASE();') == '0', 'Unsupported events')
        defaults = self.sql('SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=DATABASE();').split('\t')
        need(len(defaults) == 2 and all(re.fullmatch('[a-zA-Z0-9_]+', v) for v in defaults), 'Unknown DB defaults')
        self.report.update(containers=states, database_defaults=dict(zip(('charset', 'collation'), defaults)))
        return states

    def stream(self, args, path, *, restore=False, timeout=1200, compress=True):
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen([self.config['docker'], *args], env=self.env,
                stdin=subprocess.PIPE if restore else subprocess.DEVNULL,
                stdout=subprocess.DEVNULL if restore else subprocess.PIPE, stderr=errors)
            import threading
            timer = threading.Timer(timeout, process.kill)
            timer.start()
            try:
                if restore:
                    with gzip.open(path, 'rb') as source:
                        shutil.copyfileobj(source, process.stdin)
                    process.stdin.close()
                else:
                    with (gzip.open(path, 'xb', compresslevel=1) if compress else path.open('xb')) as output:
                        shutil.copyfileobj(process.stdout, output)
                    process.stdout.close()
                need(process.wait(timeout=30) == 0, 'Docker stream failed')
            finally:
                timer.cancel()
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()

    def resume(self):
        if self.paused:
            self.docker('start', self.paused)
            self.paused = None
            (self.root / 'paused-backend.json').unlink(missing_ok=True)
        deadline = time.monotonic() + 120
        while True:
            try:
                self.health()
                return
            except Exception:
                need(time.monotonic() < deadline, 'Backend did not recover')
                time.sleep(2)

    def capture(self, states):
        self.paused = states['sam-yolo-backend']['id']
        safe_write(self.root / 'paused-backend.json', json.dumps({'id': self.paused}).encode())
        try:
            self.docker('stop', '--time', '120', self.paused)
            need(self.sql("SELECT COUNT(*) FROM detection_tasks WHERE status IN ('pending','processing');") == '0', 'Detection arrived during stop')
            self.stream(['exec', states['sam-yolo-mysql']['id'], 'sh', '-c', DUMP], self.output / 'database.sql.gz')
            with (self.output / 'files.tar.gz').open('xb') as archive, tempfile.TemporaryFile() as manifest:
                capture_user_files(self.config, archive, manifest)
                manifest.seek(0)
                self.report['files'] = json.load(manifest)
            # Native tar emits gzip already; preserve volume contents and names.
            self.stream(['exec', states['sam-yolo-gateway']['id'], 'tar', '-C', '/data', '-czf', '-', '.'],
                        self.output / 'caddy-data.tar.gz', compress=False)
        finally:
            self.resume()

    def cache_images(self, states):
        """Save each exact deployed image once; snapshots refer to this cache."""
        cache = self.root / 'images'
        cache.mkdir(mode=0o750, exist_ok=True)
        trusted(cache, directory=True)
        os.chown(cache, 0, self.config['gid'])
        self.report['images'] = {}
        for image in sorted({state['image'] for state in states.values()}):
            need(re.fullmatch('sha256:[0-9a-f]{64}', image), 'Unexpected image ID')
            target = cache / (image.split(':')[1] + '.tar.gz')
            if not target.exists():
                temporary = target.with_suffix('.partial')
                if temporary.exists():
                    trusted(temporary)
                    temporary.unlink()  # Only this exact, root-owned failed export.
                self.stream(['image', 'save', image], temporary, timeout=1200)
                checksum(temporary, compressed=True)  # Read entire gzip incl. CRC.
                temporary.rename(target)
                os.chown(target, 0, self.config['gid'])
                target.chmod(0o640)
            trusted(target)
            self.report['images'][image] = {'path': 'images/' + target.name, 'sha256': checksum(target)}

    def cache_models(self):
        """One archive per installed Ollama model inventory, read as ollama UID."""
        inventory=self.report.get('ollama_models')
        need(isinstance(inventory,dict) and inventory.get('models'),'Ollama inventory unavailable')
        # Ignore changing API metadata; identify the installed content digests.
        digests=sorted((model['name'],model['digest']) for model in inventory['models'])
        def same_inventory():
            current = self.ollama_inventory()
            need(sorted((model['name'], model['digest']) for model in current.get('models', [])) == digests,
                 'Ollama API inventory changed during backup')
        same_inventory()
        identity=hashlib.sha256(json.dumps(digests).encode()).hexdigest()
        cache=self.root/'models'
        cache.mkdir(mode=0o750,exist_ok=True)
        trusted(cache,directory=True)
        os.chown(cache,0,self.config['gid'])
        target=cache/(identity+'.tar.gz')
        if not target.exists():
            temporary=target.with_suffix('.partial')
            if temporary.exists():
                trusted(temporary)
                temporary.unlink()
            with temporary.open('xb') as output:
                capture_native_models(self.config, output)
            self.report['native_model_validation'] = validate_native_models(temporary, digests)
            temporary.rename(target)
            os.chown(target,0,self.config['gid'])
            target.chmod(0o640)
        trusted(target)
        self.report['native_models']={'path':'models/'+target.name,'sha256':checksum(target),'inventory':digests}
        same_inventory()

    def verify(self, states):
        credentials={'MYSQL_DATABASE':'yolo','MYSQL_USER':'yolo_app',
                     'MYSQL_PASSWORD':secrets.token_hex(24),'MYSQL_ROOT_PASSWORD':secrets.token_hex(24)}
        label = 'sam.yolo.managed-restore=' + self.stamp
        self.volume = 'sam-yolo-managed-restore-' + self.stamp.lower()
        self.docker('volume', 'create', '--label', label, self.volume)
        labels = json.loads(self.docker('volume', 'inspect', '--format', '{{json .Labels}}', self.volume))
        need(labels.get('sam.yolo.managed-restore') == self.stamp, 'Unexpected restore volume')
        defaults = self.report['database_defaults']
        self.temporary = self.docker('create', '--name', self.volume, '--label', label,
            '--network', 'none', '--cpus', '2', '--memory', '2g', '--log-driver', 'none',
            '-e','MYSQL_DATABASE','-e','MYSQL_USER','-e','MYSQL_PASSWORD','-e','MYSQL_ROOT_PASSWORD',
            '--mount', f'type=volume,source={self.volume},target=/var/lib/mysql',
            states['sam-yolo-mysql']['image'], '--character-set-server=' + defaults['charset'],
            '--collation-server=' + defaults['collation'],private_env=credentials).strip()
        del credentials
        need(re.fullmatch('[0-9a-f]{64}', self.temporary), 'Invalid temporary container')
        self.docker('start', self.temporary)
        deadline = time.monotonic() + 120
        while True:
            try:
                if self.sql('SELECT 1;', self.temporary) == '1':
                    break
            except RuntimeError:
                pass
            need(time.monotonic() < deadline, 'Restore DB not ready')
            time.sleep(2)
        self.stream(['exec', '-i', self.temporary, 'sh', '-c', SQL_CLIENT, 'mysql'], self.output / 'database.sql.gz', restore=True)
        restored = self.output / 'restored.sql.gz'
        self.stream(['exec', self.temporary, 'sh', '-c', DUMP], restored)
        need(normalized_sql(self.output / 'database.sql.gz') == normalized_sql(restored), 'Restored SQL differs')
        restore_files=self.output/'.restore-files'
        restore_files.mkdir(mode=0o700)
        with tarfile.open(self.output / 'files.tar.gz') as archive:
            seen = set()
            for member in archive:
                relative=Path(member.name)
                need(member.isfile() and not relative.is_absolute() and '..' not in relative.parts
                     and member.name in self.report['files'] and member.name not in seen, 'Unexpected archive member')
                target=restore_files/relative
                target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                with archive.extractfile(member) as stream:
                    with target.open('xb') as output:
                        shutil.copyfileobj(stream,output)
                need(target.stat().st_size == self.report['files'][member.name]['size']
                     and checksum(target) == self.report['files'][member.name]['sha256'], 'File verification failed')
                seen.add(member.name)
            need(seen == set(self.report['files']), 'Incomplete archive')
        with tarfile.open(self.output / 'caddy-data.tar.gz') as archive:
            for member in archive:
                need(not member.issym() and not member.islnk() and '..' not in Path(member.name).parts
                     and not Path(member.name).is_absolute() and (member.isfile() or member.isdir()), 'Unsafe certificate archive')
                if member.isfile():
                    with archive.extractfile(member) as stream:
                        while stream.read(1024 * 1024):
                            pass
        restored.unlink()
        self.report['restore_verified'] = True

    def cleanup(self):
        if self.temporary:
            labels = self.inspect(self.temporary).get('labels') or {}
            need(labels.get('sam.yolo.managed-restore') == self.stamp, 'Refusing foreign container cleanup')
            self.docker('rm', '-f', self.temporary)
            self.temporary = None
        if self.volume:
            labels = json.loads(self.docker('volume', 'inspect', '--format', '{{json .Labels}}', self.volume))
            need(labels.get('sam.yolo.managed-restore') == self.stamp, 'Refusing foreign volume cleanup')
            self.docker('volume', 'rm', self.volume)
            self.volume = None
        (self.output / 'restore.env').unlink(missing_ok=True)
        restored=self.output/'.restore-files'
        if restored.exists():
            need(restored.is_dir() and not restored.is_symlink(),'Unexpected file restore directory')
            shutil.rmtree(restored)

    def run(self):
        self.output.mkdir(mode=0o700)
        try:
            self.report['stage'] = 'preflight'
            states = self.preflight()
            print('PASS: managed preflight / DB / disk / service ownership',flush=True)
            self.report['stage'] = 'image-cache'
            self.cache_images(states)
            print('PASS: exact image cache',flush=True)
            self.report['stage'] = 'model-cache'
            self.cache_models()
            print('PASS: native Ollama manifests / blob SHA-256 cache',flush=True)
            self.report['stage'] = 'capture'
            self.capture(states)
            print('PASS: SQL / source / media / checkpoints / config / certificate capture; backend resumed',flush=True)
            self.report['stage'] = 'isolated-restore'
            self.verify(states)
            print('PASS: isolated SQL restore / file restore SHA-256',flush=True)
            self.report['stage'] = 'service-verification'
            self.cleanup()
            self.health()
            for name, state in states.items():
                current = self.inspect(name)
                need((current['id'], current['mounts'], current['running']) == (state['id'], state['mounts'], True), 'Service identity changed')
            self.report['artifacts'] = {p.name: checksum(p) for p in self.output.iterdir() if p.is_file()}
            self.report['database_sql_sha256'] = checksum(self.output / 'database.sql.gz', compressed=True)
            self.report['success'] = True
            self.report['worker_sha256'] = self.config['worker_sha256']
            self.report['stage'] = 'complete'
        except Exception as exc:
            self.report['error'] = str(exc) if type(exc) is RuntimeError else type(exc).__name__
        finally:
            try:
                if self.paused:
                    self.resume()
                self.cleanup()
            except Exception:
                self.report.update(success=False, recovery_error=True)
            safe_write(self.output / 'manifest.json', json.dumps(self.report, indent=2).encode())
            for path in self.output.iterdir():
                os.chown(path, 0, self.config['gid'])
                path.chmod(0o640)
            os.chown(self.output, 0, self.config['gid'])
            self.output.chmod(0o750)
        if self.report['success']:
            for path in retained_candidates(self.root, self.config['keep']):
                trusted(path, directory=True)
                shutil.rmtree(path)
        print(('PASS' if self.report['success'] else 'FAIL') + ': managed backup ' + self.stamp, flush=True)
        if self.report.get('error'):
            print('Backup failure [' + self.report['stage'] + ']: ' + self.report['error'], flush=True)
        if self.report.get('operational_warning'):
            print('WARN: '+self.report['operational_warning'],flush=True)
        return 0 if self.report['success'] and not self.report.get('operational_warning') else 1


def hash_stream(stream):
    digest = hashlib.sha256()
    for data in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(data)
    return digest.hexdigest()


def main():
    need(os.getuid() == 0, 'Run the installed system service')
    os.umask(0o077)
    trusted(CONFIG)
    trusted(Path(__file__))
    config = json.loads(CONFIG.read_text())
    parser = argparse.ArgumentParser()
    parser.add_argument('--recover', action='store_true')
    arguments = parser.parse_args()
    if arguments.recover:
        marker = ROOT / 'paused-backend.json'
        if marker.exists():
            trusted(marker)
            identity = json.loads(marker.read_text())['id']
            maintenance = Maintenance(config)
            current = maintenance.inspect('sam-yolo-backend')
            need(current['id'] == identity and (current.get('labels') or {}).get('com.docker.compose.service') == 'backend', 'Recovery container identity changed')
            maintenance.paused = identity
            maintenance.resume()
        return 0
    trusted(ROOT,directory=True)
    descriptor=os.open(ROOT/'.maintenance.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'a') as lock:
        trusted(ROOT/'.maintenance.lock')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        shared = Path(config['home']) / '.config/yolo-system/compose-apply.lock'
        fd = os.open(shared, os.O_RDONLY | os.O_NOFOLLOW)
        info = os.fstat(fd)
        need(stat.S_ISREG(info.st_mode) and info.st_uid == config['uid'], 'Invalid shared deployment lock')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        def interrupted(*_):
            raise RuntimeError('Maintenance interrupted')
        signal.signal(signal.SIGTERM, interrupted)
        try:
            return Maintenance(config).run()
        finally:
            os.close(fd)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('FAIL: ' + (str(exc) if type(exc) is RuntimeError else type(exc).__name__))
        raise SystemExit(1)

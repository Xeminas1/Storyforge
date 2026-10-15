"""Validated Storyforge ZIP updater, also used by the unattended release watcher. Never install files under data/.

A release ZIP must contain a Storyforge/ directory with an update-manifest.json
listing SHA-256 checksums for every installable file. This detects corruption,
not malicious publishers; only use packages from a trusted source.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
import urllib.parse
import logging
import uuid
import zipfile
from pathlib import Path, PurePosixPath

VERSION = "0.7.0"
MAX_ZIP_SIZE = 30 * 1024 * 1024
MAX_UNPACKED = 80 * 1024 * 1024
MAX_FILES = 250
UPDATES_DIR = "updates"
INSTALL_PREFIX = "Storyforge/"
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
TOKEN_PATTERN = re.compile(r"^[a-f0-9]{32}$")


def version_tuple(v: str) -> tuple[int, int, int]:
    if not isinstance(v, str) or not VERSION_PATTERN.fullmatch(v):
        raise ValueError("Invalid update version")
    return tuple(map(int, v.split('.')))


def installable(path: str) -> bool:
    """Allow only application source; never database, secrets, executables, or services."""
    if not path or '\\' in path or path.startswith('/'):
        return False
    if not re.fullmatch(r'[a-zA-Z0-9_./-]+', path) or '//' in path:
        return False
    p = PurePosixPath(path)
    if '..' in p.parts or '.' in p.parts or any(x.startswith('.') for x in p.parts):
        return False
    if len(p.parts) == 1:
        return p.name in {"server.py", "engine.py", "narration.py", "updater.py", "README.md"}
    if len(p.parts) == 2 and p.parts[0] == 'static':
        return p.suffix in {'.html', '.css', '.js'}
    if p.parts == ('tools', 'build_release.py'):
        return True
    if len(p.parts) == 2 and p.parts[0] == 'tests':
        return p.name.startswith('test_') and p.suffix == '.py'
    return False


def update_home(root: Path) -> Path:
    return root / 'data' / UPDATES_DIR


def status_path(root: Path) -> Path:
    return update_home(root) / 'status.json'


def _atomic_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def set_status(root: Path, phase: str, **details) -> None:
    _atomic_json(status_path(root), {"phase": phase, "timestamp": int(time.time()), **details})


def get_status(root: Path) -> dict:
    try:
        result = json.loads(status_path(root).read_text(encoding='utf-8'))
        if not isinstance(result, dict):
            result = {}
    except (OSError, ValueError):
        result = {}
    return {"version": VERSION, "status": result, "local_install": True,
            "automatic_releases": True, "channel": channel_status(root)}


def validate_package(data: bytes, current_version: str = VERSION) -> tuple[dict, dict[str, bytes]]:
    if len(data) > MAX_ZIP_SIZE:
        raise ValueError("Update ZIP is too large (30 MB limit)")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("Choose a valid Storyforge update ZIP") from exc
    with archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if len(infos) < 2 or len(infos) > MAX_FILES:
            raise ValueError("Unexpected number of files in update")
        files = {}
        seen = set()
        total_size = 0
        for info in infos:
            name = info.filename
            if not name.startswith(INSTALL_PREFIX):
                raise ValueError("ZIP must contain a Storyforge/ root folder")
            key = name[len(INSTALL_PREFIX):]
            if key.casefold() in seen:
                raise ValueError("Duplicate filename in update ZIP")
            seen.add(key.casefold())
            if '\\' in name or '..' in PurePosixPath(name).parts or name.startswith('/'):
                raise ValueError("Unsafe file path in update ZIP")
            unix_mode = info.external_attr >> 16
            if stat.S_IFMT(unix_mode) == stat.S_IFLNK:
                raise ValueError("Update ZIP must not contain symbolic links")
            if key != 'update-manifest.json' and not installable(key):
                raise ValueError(f"Update includes a disallowed file: {key}")
            if info.file_size > 15 * 1024 * 1024:
                raise ValueError("An update file is too large")
            total_size += info.file_size
            if total_size > MAX_UNPACKED:
                raise ValueError("Update expands beyond its allowed size")
            files[key] = archive.read(info)
        manifest_bytes = files.pop('update-manifest.json', None)
        if manifest_bytes is None or len(manifest_bytes) > 512_000:
            raise ValueError("Missing or oversized update manifest")
        try:
            manifest = json.loads(manifest_bytes)
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Malformed update manifest") from exc
        if not isinstance(manifest, dict) or not isinstance(manifest.get('files'), dict):
            raise ValueError("Manifest must specify the release files")
        version = manifest.get('version')
        if version_tuple(version) <= version_tuple(current_version):
            raise ValueError(f"Update v{version} is not newer than v{current_version}")
        declared = manifest['files']
        if set(declared) != set(files):
            raise ValueError("Update files do not match the manifest")
        for key, content in files.items():
            checksum = declared[key]
            if not isinstance(checksum, str) or not re.fullmatch('[a-f0-9]{64}', checksum):
                raise ValueError("Invalid SHA-256 checksum in manifest")
            if hashlib.sha256(content).hexdigest() != checksum:
                raise ValueError("Update failed file integrity verification")
        if not {'server.py', 'updater.py', 'static/app.js'}.issubset(files):
            raise ValueError("Update ZIP is missing required program files")
        return manifest, files


def stage_package(root: Path, payload: bytes, current_version: str = VERSION) -> dict:
    manifest, files = validate_package(payload, current_version)
    token = uuid.uuid4().hex
    staging = update_home(root) / 'staging' / token
    staging.mkdir(parents=True, exist_ok=False)
    for name, content in files.items():
        target = staging / 'files' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    metadata = {'token': token, 'version': manifest['version'], 'files': manifest['files']}
    _atomic_json(staging / 'metadata.json', metadata)
    # Worker runs outside the app so that Windows can replace app files after shutdown.
    shutil.copyfile(Path(__file__).resolve(), staging / 'worker.py')
    return {'token': token, 'version': manifest['version'], 'file_count': len(files),
            'contains_database': False}


def backup_database(root: Path, db: Path, token: str) -> str | None:
    if not db.is_file():
        return None
    folder = update_home(root) / 'backups' / token
    folder.mkdir(parents=True, exist_ok=True)
    outfile = folder / 'storyforge.db'
    with sqlite3.connect(str(db)) as source, sqlite3.connect(str(outfile)) as destination:
        source.backup(destination)
    return str(outfile)


def begin_install(root: Path, db: Path, token: str, server, host: str, port: int) -> dict:
    if not TOKEN_PATTERN.fullmatch(str(token)):
        raise ValueError("Invalid staged update ID")
    staging = update_home(root) / 'staging' / token
    meta = json.loads((staging / 'metadata.json').read_text(encoding='utf-8'))
    if meta.get('token') != token or not isinstance(meta.get('files'), dict):
        raise ValueError("Staged update metadata is invalid")
    if version_tuple(meta['version']) <= version_tuple(VERSION):
        raise ValueError("This update is no longer newer than the running version")
    for name, digest in meta['files'].items():
        if not installable(name) or hashlib.sha256((staging / 'files' / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Staged update verification failed")
    db_backup = backup_database(root, db, token)
    set_status(root, 'scheduled', target_version=meta['version'], db_backup=db_backup)

    def launch_when_ready():
        # Give the HTTP client time to receive the confirmation response.
        time.sleep(0.7)
        logdir = update_home(root)
        logdir.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, str(staging / 'worker.py'), '--apply', str(root),
                   token, str(os.getpid()), host, str(port)]
        flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == 'nt' else 0
        try:
            with (logdir / 'updater.log').open('ab') as logfile:
                subprocess.Popen(command, cwd=str(root), stdin=subprocess.DEVNULL,
                                 stdout=logfile, stderr=subprocess.STDOUT,
                                 creationflags=flags, start_new_session=os.name != 'nt')
        except Exception as exc:
            set_status(root, 'failed', error=f"Could not start updater: {exc}")
            return
        server.shutdown()

    threading.Thread(target=launch_when_ready, daemon=True).start()
    return {'ok': True, 'version': meta['version'], 'message': 'Storyforge is restarting to install the update.'}


def parent_stopped(pid: int, timeout: float = 35) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.name == 'nt':
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if not handle:
                return True
            try:
                if ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 0:
                    return True
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        else:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
        time.sleep(.15)
    return False


def launch_server(root: Path, host: str, port: int) -> subprocess.Popen:
    log = (update_home(root) / 'server.log').open('ab')
    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == 'nt' else 0
    try:
        return subprocess.Popen([sys.executable, str(root / 'server.py')], cwd=str(root),
                                env={**os.environ, 'STORYFORGE_HOST': host, 'STORYFORGE_PORT': str(port)},
                                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                creationflags=flags, start_new_session=os.name != 'nt')
    finally:
        log.close()


def wait_for_health(host: str, port: int, version: str, child: subprocess.Popen, seconds: int = 35) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if child.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f'http://{host}:{port}/api/health', timeout=1.5) as reply:
                if json.loads(reply.read().decode('utf-8')).get('version') == version:
                    return True
        except Exception:
            pass
        time.sleep(.5)
    return False


def apply_staged(root: Path, token: str, parent_pid: int, host: str, port: int) -> int:
    if not TOKEN_PATTERN.fullmatch(token):
        raise ValueError("Invalid update token")
    staging = update_home(root) / 'staging' / token
    meta = json.loads((staging / 'metadata.json').read_text(encoding='utf-8'))
    if meta.get('token') != token:
        raise ValueError("Update token mismatch")
    new_version = meta['version']
    if not parent_stopped(parent_pid):
        set_status(root, 'failed', error='Old Storyforge process did not stop')
        return 2
    backup_dir = update_home(root) / 'backups' / token / 'code'
    original_files: dict[str, bool] = {}
    replaced: list[str] = []
    server_process = None
    try:
        set_status(root, 'installing', target_version=new_version)
        for name, digest in meta['files'].items():
            if not installable(name):
                raise ValueError("Disallowed update filename")
            content = (staging / 'files' / name).read_bytes()
            if hashlib.sha256(content).hexdigest() != digest:
                raise ValueError("Staged update checksum mismatch")
            dest = root / name
            original_files[name] = dest.exists()
            if dest.exists():
                saved = backup_dir / name
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, saved)
            dest.parent.mkdir(parents=True, exist_ok=True)
            next_file = dest.with_name(dest.name + '.updating')
            next_file.write_bytes(content)
            os.replace(next_file, dest)
            replaced.append(name)
        server_process = launch_server(root, host, port)
        if not wait_for_health(host, port, new_version, server_process):
            raise RuntimeError('Updated server did not become healthy')
        set_status(root, 'completed', version=new_version,
                   backup=str((update_home(root) / 'backups' / token).resolve()))
        return 0
    except Exception as exc:
        if server_process is not None and server_process.poll() is None:
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
        rollback_error = None
        try:
            for name in reversed(replaced):
                dest = root / name
                if original_files.get(name):
                    shutil.copy2(backup_dir / name, dest)
                elif dest.exists():
                    dest.unlink()
            set_status(root, 'rolled_back', error=str(exc),
                       backup=str((update_home(root) / 'backups' / token).resolve()))
            launch_server(root, host, port)
        except Exception as recovery_exc:
            rollback_error = str(recovery_exc)
            set_status(root, 'failed', error=f'{exc}; rollback failed: {rollback_error}')
        return 3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', nargs=5, metavar=('ROOT', 'TOKEN', 'PID', 'HOST', 'PORT'))
    args = parser.parse_args()
    if not args.apply:
        parser.error('This helper is launched by Storyforge itself.')
    root, token, pid, host, port = args.apply
    sys.exit(apply_staged(Path(root), token, int(pid), host, int(port)))


REPOSITORY = 'Xeminas1/Storyforge'
API_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
CHECK_INTERVAL = 4 * 3600
IDLE_SECONDS = 10 * 60
POLL_SECONDS = 30
MAX_METADATA_BYTES = 256 * 1024
HEX_SHA256 = re.compile(r'^sha256:([0-9a-f]{64})$')


def _paths(root: Path) -> tuple[Path, Path]:
    home = update_home(root)
    return home / 'channel-settings.json', home / 'channel-status.json'


def channel_enabled(root: Path) -> bool:
    path, _ = _paths(root)
    try:
        obj = json.loads(path.read_text(encoding='utf8'))
        return obj.get('auto_install', True) is True
    except (OSError, ValueError, TypeError):
        # User expressly opted in; new installations default to unattended updates.
        return True


def set_channel_enabled(root: Path, value: bool) -> bool:
    if type(value) is not bool:
        raise ValueError('Expected true or false')
    path, _ = _paths(root)
    _atomic_json(path, {'auto_install': value})
    return value


def channel_status(root: Path) -> dict:
    _, path = _paths(root)
    try:
        progress = json.loads(path.read_text(encoding='utf8'))
        if not isinstance(progress, dict):
            progress = {}
    except (OSError, ValueError):
        progress = {}
    return {'enabled': channel_enabled(root), 'repository': REPOSITORY,
            'poll_hours': CHECK_INTERVAL // 3600, 'idle_minutes': IDLE_SECONDS // 60,
            'source_configured': progress.get('source_configured', False),
            'last_check': progress.get('last_check'), 'latest': progress.get('latest'),
            'phase': progress.get('phase', 'pending'), 'error': progress.get('error')}


def save_channel_status(root: Path, **fields) -> None:
    _, path = _paths(root)
    _atomic_json(path, {**channel_status(root), **fields})


class TrustedRedirects(urllib.request.HTTPRedirectHandler):
    """Only follow HTTPS redirects to GitHub-owned release asset servers."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urllib.parse.urlsplit(newurl)
        host = parts.hostname or ''
        allowed = (host == 'github.com' or host == 'api.github.com'
                   or host == 'release-assets.githubusercontent.com'
                   or host == 'objects.githubusercontent.com'
                   or host.endswith('.githubusercontent.com'))
        if parts.scheme != 'https' or not allowed or parts.username or parts.password:
            raise ValueError('Untrusted release download redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(TrustedRedirects())


def _fetch(url: str, max_bytes: int, *, accept: str = 'application/json') -> bytes:
    request = urllib.request.Request(url, headers={
        'User-Agent': f'Storyforge/{VERSION}',
        'Accept': accept,
        'X-GitHub-Api-Version': '2022-11-28',
    })
    with _OPENER.open(request, timeout=16) as response:
        if response.status != 200:
            raise ValueError('GitHub release request failed')
        result = response.read(max_bytes + 1)
        if len(result) > max_bytes:
            raise ValueError('GitHub release data is too large')
        return result


def parse_release(data: bytes, current_version: str = VERSION) -> dict | None:
    """Parse release and ensure both origin and asset digest are pinned/verified."""
    if len(data) > MAX_METADATA_BYTES:
        raise ValueError('Release metadata too large')
    release = json.loads(data)
    if not isinstance(release, dict) or release.get('draft') or release.get('prerelease'):
        raise ValueError('No stable release available')
    version = str(release.get('tag_name', '')).removeprefix('v')
    if version_tuple(version) <= version_tuple(current_version):
        return None
    filename = f'Storyforge_v{version}.zip'
    for asset in release.get('assets', []):
        if asset.get('name') != filename:
            continue
        url = str(asset.get('browser_download_url', ''))
        parts = urllib.parse.urlsplit(url)
        # Never let GitHub-provided JSON select a different publisher or server.
        correct_path = f'/{REPOSITORY}/releases/download/'
        if (parts.scheme != 'https' or parts.netloc != 'github.com' or
            not parts.path.startswith(correct_path) or
            not parts.path.endswith('/' + filename) or parts.query or parts.fragment):
            raise ValueError('Release asset URL did not match the pinned publisher')
        digest = str(asset.get('digest') or '')
        match = HEX_SHA256.fullmatch(digest)
        if not match:
            raise ValueError('GitHub has not supplied the release asset SHA-256 digest')
        if not isinstance(asset.get('size'), int) or not (100 <= asset['size'] <= MAX_ZIP_SIZE):
            raise ValueError('Release asset size is missing or invalid')
        return {'version': version, 'url': url, 'sha256': match.group(1),
                'size': asset['size']}
    raise ValueError(f'Missing required GitHub release asset: {filename}')


def read_latest() -> dict | None:
    return parse_release(_fetch(API_URL, MAX_METADATA_BYTES))


def download_verified(info: dict) -> bytes:
    contents = _fetch(info['url'], MAX_ZIP_SIZE, accept='application/octet-stream')
    if len(contents) != info['size']:
        raise ValueError('Downloaded release size differs from GitHub metadata')
    if hashlib.sha256(contents).hexdigest() != info['sha256']:
        raise ValueError('Downloaded release SHA-256 does not match GitHub')
    manifest, _ = validate_package(contents)
    if manifest['version'] != info['version']:
        raise ValueError('Release tag disagrees with package version')
    return contents


class UpdateWatcher:
    def __init__(self, root: Path, db: Path, server):
        self.root, self.db, self.server = root, db, server
        self.wake = threading.Event()
        self.stop = threading.Event()
        self._last_checked = 0.0
        self._pending: dict | None = None
        self._last_activity = time.monotonic()
        self._lock = threading.Lock()
        self._operation_lock = threading.Lock()  # Serialize discovery and installation jobs.
        self._manual_lock = threading.Lock()  # Reject double-clicked install requests.
        self.thread: threading.Thread | None = None

    def user_active(self):
        with self._lock:
            self._last_activity = time.monotonic()

    def is_idle(self):
        with self._lock:
            return time.monotonic() - self._last_activity >= IDLE_SECONDS

    def check_now(self):
        self._last_checked = 0
        self.wake.set()

    def start(self):
        self.thread = threading.Thread(target=self.run, name='storyforge-release-watch', daemon=True)
        self.thread.start()

    def check(self):
        if not channel_enabled(self.root) or self._manual_lock.locked():
            return
        if not self._operation_lock.acquire(blocking=False):
            return
        try:
            save_channel_status(self.root, last_check=int(time.time()), phase='checking', error=None)
            try:
                latest = read_latest()
                self._pending = latest
                save_channel_status(self.root, last_check=int(time.time()), source_configured=True,
                            latest=latest['version'] if latest else None,
                            phase='queued' if latest else 'current', error=None)
            except urllib.error.HTTPError as exc:
                save_channel_status(self.root, last_check=int(time.time()),
                            source_configured=(exc.code != 404), phase='unavailable',
                            error=('Storyforge GitHub release repository or releases not ready yet'
                                   if exc.code == 404 else f'GitHub HTTP {exc.code}'))
            except Exception as exc:
                logging.warning('Storyforge release check failed: %s', exc)
                save_channel_status(self.root, last_check=int(time.time()), phase='unavailable',
                            error=str(exc)[:300])
        finally:
            self._operation_lock.release()

    def install_latest_now(self) -> dict:
        """Explicit local-user action: verify and install now, ignoring idle/auto preferences."""
        if not self._manual_lock.acquire(blocking=False):
            raise ValueError('An immediate update is already underway')
        try:
            self._last_checked = time.monotonic()
            save_channel_status(self.root, phase='checking', error=None,
                                last_check=int(time.time()))
            threading.Thread(target=self._install_now_worker,
                             name='storyforge-install-now', daemon=True).start()
        except Exception:
            self._manual_lock.release()
            raise
        return {'ok': True, 'message': 'Checking GitHub and installing the latest verified release now'}

    def _install_now_worker(self) -> None:
        try:
            # Wait for any regular update check or background install to finish.
            with self._operation_lock:
                info = read_latest()
                self._pending = info
                if info is None:
                    save_channel_status(self.root, source_configured=True, latest=None,
                                        phase='current', error=None, last_check=int(time.time()))
                    return
                save_channel_status(self.root, source_configured=True, latest=info['version'],
                                    phase='downloading', error=None, last_check=int(time.time()))
                raw = download_verified(info)
                stage = stage_package(self.root, raw)
                save_channel_status(self.root, phase='installing', latest=info['version'])
                begin_install(self.root, self.db, stage['token'], self.server,
                              self.server.server_address[0], self.server.server_address[1])
                self._pending = None
                self.stop.set()
        except Exception as exc:
            logging.exception('Immediate GitHub update failed')
            save_channel_status(self.root, phase='failed', error=str(exc)[:300])
        finally:
            self._manual_lock.release()

    def run(self):
        # Always let the app finish opening before touching release discovery.
        self.stop.wait(5)
        while not self.stop.is_set():
            now = time.monotonic()
            if (not self._manual_lock.locked() and channel_enabled(self.root)
                    and now - self._last_checked >= CHECK_INTERVAL):
                self._last_checked = now
                self.check()
            if (not self._manual_lock.locked() and channel_enabled(self.root)
                    and self._pending and self.is_idle()):
                self.install_pending()
            self.wake.wait(POLL_SECONDS)
            self.wake.clear()

    def install_pending(self):
        if self._manual_lock.locked() or not self._operation_lock.acquire(blocking=False):
            return
        try:
            info = self._pending
            if not info or not channel_enabled(self.root) or not self.is_idle():
                return
            self._pending = None
            try:
                save_channel_status(self.root, phase='downloading', latest=info['version'], error=None)
                raw = download_verified(info)
                if not channel_enabled(self.root) or not self.is_idle():
                    self._pending = info
                    save_channel_status(self.root, phase='queued')
                    return
                stage = stage_package(self.root, raw)
                save_channel_status(self.root, phase='installing', latest=info['version'])
                begin_install(self.root, self.db, stage['token'], self.server,
                                      self.server.server_address[0], self.server.server_address[1])
                self.stop.set()
            except Exception as exc:
                logging.exception('Unattended update failed')
                save_channel_status(self.root, phase='failed', error=str(exc)[:300])
                # Don't repeatedly retry potentially corrupt releases every 30s.
        finally:
            self._operation_lock.release()


if __name__ == '__main__':
    main()

"""Self-updater reliability and archive safety tests."""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import updater


def make_zip(files: dict[str, bytes], version='0.12.1', checksums=None):
    file_hashes = {p: hashlib.sha256(data).hexdigest() for p, data in files.items()}
    if checksums is not None:
        file_hashes = checksums
    with io.BytesIO() as out:
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr('Storyforge/' + name, content)
            archive.writestr('Storyforge/update-manifest.json', json.dumps({'version': version, 'files': file_hashes}))
        return out.getvalue()


RELEASE_FILES = {'server.py': b'print("new server")', 'updater.py': b'print("updater")',
                 'static/app.js': b'console.log("new client")', 'README.md': b'new readme'}


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_release_stages_and_checksums(self):
        info = updater.stage_package(self.root, make_zip(RELEASE_FILES))
        self.assertEqual(info['version'], '0.12.1')
        self.assertEqual(info['file_count'], 4)
        self.assertFalse(info['contains_database'])
        stage = self.root / 'data' / 'updates' / 'staging' / info['token']
        self.assertEqual((stage / 'files' / 'static' / 'app.js').read_bytes(), RELEASE_FILES['static/app.js'])
        self.assertTrue((stage / 'worker.py').is_file())
        self.assertFalse((self.root / 'server.py').exists(), 'Inspect may not overwrite the installed app')

    def test_reject_old_version(self):
        with self.assertRaisesRegex(ValueError, 'not newer'):
            updater.validate_package(make_zip(RELEASE_FILES, '0.3.0'))

    def test_reject_mismatched_checksum(self):
        bad = {p:'0'*64 for p in RELEASE_FILES}
        with self.assertRaisesRegex(ValueError, 'integrity'):
            updater.validate_package(make_zip(RELEASE_FILES, checksums=bad))

    def test_reject_data_and_traversal_and_executable(self):
        for name in ('data/storyforge.db', '../malicious.py', 'static/../../escape.js',
                     'malware.exe', '.env', 'static/fake.py', 'static/subdir/hack.js'):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, '(disallowed|Unsafe)'):
                    updater.validate_package(make_zip({**RELEASE_FILES, name: b'bad'}))

    def test_reject_manifest_file_inconsistency(self):
        checksum = {p:hashlib.sha256(data).hexdigest() for p,data in RELEASE_FILES.items()}
        checksum['extra.py'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'do not match'):
            updater.validate_package(make_zip(RELEASE_FILES, checksums=checksum))

    def test_database_backup_is_readable_and_non_destructive(self):
        path = self.root / 'data' / 'storyforge.db'
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE entries (value TEXT)')
            db.execute('INSERT INTO entries VALUES (?)', ('Xeminas',))
        saved = updater.backup_database(self.root, path, 'abcdef1234')
        with sqlite3.connect(saved) as db:
            self.assertEqual(db.execute('SELECT value FROM entries').fetchone()[0], 'Xeminas')
        self.assertTrue(path.exists())

    def test_apply_preserves_data_and_old_source(self):
        (self.root / 'data').mkdir()
        (self.root / 'server.py').write_text('old source')
        (self.root / 'data' / 'storyforge.db').write_bytes(b'PRESERVE SAVE')
        stage = updater.stage_package(self.root, make_zip(RELEASE_FILES))
        fake_process = mock.MagicMock()
        with mock.patch.object(updater, 'parent_stopped', return_value=True), \
             mock.patch.object(updater, 'launch_server', return_value=fake_process), \
             mock.patch.object(updater, 'wait_for_health', return_value=True):
            result = updater.apply_staged(self.root, stage['token'], 123, '127.0.0.1', 8123)
        self.assertEqual(result, 0)
        self.assertEqual((self.root / 'server.py').read_bytes(), RELEASE_FILES['server.py'])
        self.assertEqual((self.root / 'data' / 'storyforge.db').read_bytes(), b'PRESERVE SAVE')
        self.assertEqual((self.root / 'data' / 'updates' / 'backups' / stage['token'] / 'code' / 'server.py').read_text(), 'old source')
        self.assertEqual(updater.get_status(self.root)['status']['phase'], 'completed')

    def test_unhealthy_update_rolls_back(self):
        (self.root / 'server.py').write_text('original code')
        stage = updater.stage_package(self.root, make_zip(RELEASE_FILES))
        proc = mock.MagicMock(); proc.poll.return_value=None
        with mock.patch.object(updater, 'parent_stopped', return_value=True), \
             mock.patch.object(updater, 'launch_server', return_value=proc) as launcher, \
             mock.patch.object(updater, 'wait_for_health', return_value=False):
            outcome = updater.apply_staged(self.root, stage['token'], 456, '127.0.0.1', 8123)
        self.assertEqual(outcome, 3)
        self.assertEqual((self.root / 'server.py').read_text(), 'original code')
        self.assertFalse((self.root / 'static' / 'app.js').exists())
        self.assertEqual(launcher.call_count, 2)
        self.assertEqual(updater.get_status(self.root)['status']['phase'], 'rolled_back')

    def test_requires_known_version_and_root(self):
        with self.assertRaises(ValueError):
            updater.validate_package(make_zip(RELEASE_FILES, version='banana'))
        with self.assertRaises(ValueError):
            updater.validate_package(b'not a zip')


if __name__ == '__main__':
    unittest.main()

"""Offline regression tests for the pinned GitHub automatic update channel."""
import hashlib
import json
import pathlib
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import updater as ch
import updater
from test_updater import make_zip, RELEASE_FILES


def release(version='0.5.1', url=None, digest=None, size=2500, **kw):
    if url is None:
        url = f'https://github.com/Xeminas1/Storyforge/releases/download/v{version}/Storyforge_v{version}.zip'
    if digest is None:
        digest='sha256:' + 'a'*64
    doc=dict(tag_name='v'+version, draft=False, prerelease=False,
             assets=[dict(name=f'Storyforge_v{version}.zip', browser_download_url=url,
                          digest=digest, size=size)])
    doc.update(kw)
    return json.dumps(doc).encode()


class ReleaseChannelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.tmp.name)

    def tearDown(self): self.tmp.cleanup()

    def test_matching_publisher_and_digest(self):
        detail=ch.parse_release(release())
        self.assertEqual(detail['version'],'0.5.1')
        self.assertEqual(detail['sha256'],'a'*64)

    def test_reject_other_publisher_or_host(self):
        for u in (
            'https://github.com/attacker/Storyforge/releases/download/v0.5.1/Storyforge_v0.5.1.zip',
            'https://github.com.evil.com/Xeminas1/Storyforge/releases/download/v0.5.1/Storyforge_v0.5.1.zip',
            'http://github.com/Xeminas1/Storyforge/releases/download/v0.5.1/Storyforge_v0.5.1.zip',
            'https://github.com/Xeminas1/Storyforge/releases/download/v0.5.1/Storyforge_v0.5.1.zip?other=1',
        ):
            with self.subTest(u=u), self.assertRaisesRegex(ValueError,'pinned publisher'):
                ch.parse_release(release(url=u))

    def test_old_release_ignored(self):
        self.assertIsNone(ch.parse_release(release('0.5.0')))

    def test_reject_unhashed_asset(self):
        with self.assertRaisesRegex(ValueError, 'digest'):
            ch.parse_release(release(digest=''))

    def test_reject_prerelease(self):
        with self.assertRaisesRegex(ValueError, 'stable'):
            ch.parse_release(release(prerelease=True))

    def test_download_hash_and_zip_required(self):
        zipped=make_zip(RELEASE_FILES,version='0.5.1')
        detail=ch.parse_release(release(size=len(zipped),digest='sha256:'+hashlib.sha256(zipped).hexdigest()))
        with mock.patch.object(ch, '_fetch',return_value=zipped):
            self.assertEqual(ch.download_verified(detail),zipped)
        with mock.patch.object(ch, '_fetch',return_value=zipped+b'invalid'):
            with self.assertRaisesRegex(ValueError, 'size'):
                ch.download_verified(detail)
        with mock.patch.object(ch, '_fetch',return_value=zipped[:-2]+b'xx'):
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                ch.download_verified(detail)

    def test_settings_toggle_durable(self):
        self.assertTrue(ch.channel_enabled(self.root))
        ch.set_channel_enabled(self.root,False)
        self.assertFalse(ch.channel_enabled(self.root))
        self.assertFalse(ch.channel_status(self.root)['enabled'])
        ch.set_channel_enabled(self.root,True)
        self.assertTrue(ch.channel_enabled(self.root))

    def test_not_install_while_active_or_disabled(self):
        server=mock.MagicMock()
        watcher=ch.UpdateWatcher(self.root,self.root/'data'/'storyforge.db',server)
        watcher._pending={'version':'0.5.1'}
        with mock.patch.object(ch,'download_verified') as download:
            watcher.install_pending()
            download.assert_not_called()
            watcher._last_activity = time.monotonic() - ch.IDLE_SECONDS - 1
            ch.set_channel_enabled(self.root,False)
            watcher.install_pending()
            download.assert_not_called()

    def test_background_stages_installs_without_prompt_when_idle(self):
        server=mock.MagicMock()
        server.server_address=('127.0.0.1',8787)
        watcher=ch.UpdateWatcher(self.root,self.root/'data'/'storyforge.db',server)
        watcher._last_activity = time.monotonic() - ch.IDLE_SECONDS - 1
        watcher._pending={'version':'0.5.1'}
        with mock.patch.object(ch,'download_verified',return_value=make_zip(RELEASE_FILES)),\
             mock.patch.object(updater,'begin_install',return_value={'ok':True}) as begin:
            watcher.install_pending()
            begin.assert_called_once()
            self.assertTrue(watcher.stop.is_set())

if __name__=='__main__': unittest.main()

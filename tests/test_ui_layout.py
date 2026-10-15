"""Quick, dependency-free invariants for the v0.5.0 story layout and update status."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IdScanner(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.attrs = {}

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        if props.get('id'):
            self.ids.append(props['id'])
            self.attrs[props['id']] = props


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'static' / 'index.html').read_text(encoding='utf-8')
        cls.js = (ROOT / 'static' / 'app.js').read_text(encoding='utf-8')
        cls.css = (ROOT / 'static' / 'styles.css').read_text(encoding='utf-8')
        cls.scanner = IdScanner()
        cls.scanner.feed(cls.html)

    def test_every_unique_dom_id(self):
        self.assertEqual(len(self.scanner.ids), len(set(self.scanner.ids)))

    def test_story_core_and_voice_controls_retained(self):
        for name in ('story-feed', 'action', 'send-action', 'autoplay', 'voice-engine',
                     'voices', 'speed', 'volume', 'pause-voice', 'stop-voice-top',
                     'replay', 'edit-character', 'import-world', 'nav-worlds',
                     'open-updates', 'modal-content', 'campaign-links', 'worlds'):
            with self.subTest(name=name):
                self.assertIn(name, self.scanner.ids)

    def test_three_panel_layout_and_accessible_tabs(self):
        for tab in ('scene', 'character', 'world'):
            element = self.scanner.attrs[f'select-{tab}']
            self.assertEqual(element['role'], 'tab')
            self.assertEqual(element['aria-controls'], f'tab-{tab}')
            self.assertEqual(self.scanner.attrs[f'tab-{tab}']['role'], 'tabpanel')
        self.assertIn('.adventure-layout{height:100%', self.css)
        self.assertIn('grid-template-columns:minmax(0,1fr) 330px', self.css)

    def test_update_badge_shows_only_newer_version(self):
        self.assertIn('function updateIndicator(data)', self.js)
        self.assertIn('id="install-latest-now"', self.js)
        self.assertIn("'/api/updates/install-latest'", self.js)
        self.assertIn('versionCompare(channel.latest,version)>0', self.js)
        self.assertIn("'Update available':'Updates'", self.js)
        self.assertIn('refreshUpdateIndicator();', self.js)
        self.assertIn('setInterval(refreshUpdateIndicator,60000)', self.js)

    def test_html_escapes_world_and_message_content(self):
        self.assertIn('${escapeHtml(entry.title', self.js)
        self.assertIn('${escapeHtml(m.content)', self.js)
        self.assertIn('${escapeHtml(c.pc_name)}', self.js)


if __name__ == '__main__':
    unittest.main()

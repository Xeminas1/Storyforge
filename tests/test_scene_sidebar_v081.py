"""Ensure larger location art and full-view controls survive future layout changes."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / 'static/styles.css').read_text(encoding='utf-8')
HTML = (ROOT / 'static/index.html').read_text(encoding='utf-8')
JS = (ROOT / 'static/app.js').read_text(encoding='utf-8')

class SceneSidebarTests(unittest.TestCase):
    def test_desktop_sidebar_wider(self):
        self.assertIn('grid-template-columns:minmax(0,1fr) clamp(365px,25vw,430px)', CSS)
        self.assertIn('height:clamp(305px,38vh,405px)', CSS)
        self.assertIn('width:min(96vw,395px)', CSS)

    def test_title_outside_artwork_and_controls_preserved(self):
        self.assertLess(HTML.index('class="scene-visual-heading"'),HTML.index('id="scene-art"'))
        self.assertNotIn('class="scene-art-bottom"',HTML)
        for ident in ('scene-image','scene-generate','scene-refresh','scene-lock','scene-art-status'):
            self.assertIn(f'id="{ident}"',HTML)

    def test_open_uncropped_art_and_escape(self):
        for ident in ('scene-expand','scene-lightbox','scene-lightbox-image','scene-lightbox-close'):
            self.assertIn(f'id="{ident}"',HTML)
        self.assertIn('object-fit:contain',CSS)
        self.assertIn("$('scene-lightbox').showModal()",JS)
        self.assertIn("$('scene-lightbox-close').onclick",JS)
        self.assertIn("$('scene-expand').disabled=!data.url",JS)

if __name__=='__main__': unittest.main()

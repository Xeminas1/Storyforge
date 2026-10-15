from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class MenusV060(unittest.TestCase):
    def test_full_character_and_world_views(self):
        html=(ROOT/'static/index.html').read_text()
        js=(ROOT/'static/app.js').read_text()
        for id in ('codex-overlay','codex-body','codex-close','scene-image','scene-generate','scene-refresh','scene-lock'):
            self.assertIn('id="'+id+'"',html)
        for menu in ('showCodex(\'character\')','showCodex(\'world\')','showCodex(\'journal\')'):
            self.assertIn(menu,js)
        for tab in ('Character Sheet','Inventory','Spellbook','Progression','Relationships','Memories'):
            self.assertIn(tab,js)
    def test_artist_files_are_updatable_and_not_in_saves(self):
        import sys
        sys.path.insert(0,str(ROOT))
        import updater
        self.assertFalse(updater.installable('artwork.py'))
        self.assertFalse(updater.installable('data/artwork/portraits/example.png'))
if __name__=='__main__': unittest.main()

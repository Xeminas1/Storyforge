"""Narrative format, player agency and scene state regression tests."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine


class StorytellingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = engine.open_db(Path(self.tmp.name) / 'world.db')
        self.world = engine.make_world(self.con, {'title': 'The Lantern Court', 'description': 'Veyr harbour', 'sections': [{'title': 'The Ash Quay', 'kind': 'location', 'content': 'A lively quay.'}]})
        self.campaign = engine.new_campaign(self.con, {'world_id': self.world['id'], 'pc_name': 'Xeminas'})

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_header_added_to_unformatted_model_output_and_persisted(self):
        def fake_chat(messages, model):
            self.assertIn('80% story and interaction', messages[0]['content'])
            self.assertIn('player character', messages[0]['content'])
            self.assertIn('word of mouth', messages[0]['content'])
            return json.dumps({'narration': 'A notice reads *Docks closed until morning.* Then the guard bellows **GET BACK!**',
                               'state_updates': {'location': 'The Ash Quay', 'parent_area': 'Veyr', 'time_of_day': 'Dusk'}})
        result = engine.play_turn(self.con, self.campaign['id'], 'I inspect the notice', chat=fake_chat)
        self.assertTrue(result['narration'].startswith('[The Ash Quay - Veyr - Dusk]\n\n'))
        self.assertIn('*Docks closed until morning.*', result['narration'])
        self.assertIn('**GET BACK!**', result['narration'])
        self.assertEqual(engine.speech_friendly_prose(result['narration']), 'A notice reads Docks closed until morning. Then the guard bellows GET BACK!')
        self.assertEqual(result['state']['time_of_day'], 'Dusk')
        self.assertEqual(result['state']['parent_area'], 'Veyr')

    def test_existing_model_heading_not_duplicated(self):
        text = '[Royal Cellars - Black Fortress - Midnight]\n\nA door creaks.'
        self.assertEqual(engine.scene_heading(text, {}, 'Wrong world'), text)

    def test_unknown_time_is_labelled_not_invented(self):
        result = engine.play_turn(self.con, self.campaign['id'], 'I look around', chat=lambda *_: json.dumps({'narration': 'Nearby merchants argue.', 'state_updates': {'location': 'The Ash Quay'}}))
        self.assertIn('[The Ash Quay - The Lantern Court - Time unspecified]', result['narration'])

    def test_older_campaign_state_keeps_working(self):
        state = {'location': 'West Market', 'inventory': [], 'journal': [], 'last_action': ''}
        changed = engine.apply_patch(state, {'parent_area': 'Veyr', 'time_of_day': 'Morning'}, 'Walk')
        self.assertEqual(changed['parent_area'], 'Veyr')
        self.assertNotIn('parent_area', state)

    def test_markers_are_only_removed_for_spoken_audio(self):
        raw = 'A *long letter of apology* lies nearby. "**HELP ME!**"'
        self.assertEqual(engine.preserve_narrative_emphasis(raw), raw)
        self.assertNotIn('*', engine.speech_friendly_prose(raw))
        self.assertEqual(engine.preserve_narrative_emphasis('An omen: \\* wrong \\*'), 'An omen: wrong')


if __name__ == '__main__':
    unittest.main()

"""Regression tests for expanded characters and optional neural speech."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import engine
import narration


class CharactersV020Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = engine.open_db(pathlib.Path(self.tmp.name) / 'save.db')
        self.world = engine.make_world(self.db, {'title': 'The Empire', 'description': 'Magic and intrigue'})

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_new_character_fields_in_gm_context(self):
        camp = engine.new_campaign(self.db, {
            'world_id': self.world['id'], 'pc_name': 'Xeminas', 'species': 'High Elf',
            'mannerisms': 'Speaks softly and treats manners as currency',
            'personality': 'Formal and calculating', 'appearance': 'Regal robes',
            'aliases': 'The Dark Monarch', 'abilities': 'Necromancy\nShadow magic',
            'starting_items': 'Obsidian crown\nRunic ring', 'starting_location': 'Black throne room',
            'strength': '20',
        })
        self.assertEqual(camp['pc_profile']['mannerisms'], 'Speaks softly and treats manners as currency')
        self.assertEqual(camp['pc_profile']['abilities'], ['Necromancy', 'Shadow magic'])
        self.assertEqual(camp['state']['inventory'], ['Obsidian crown','Runic ring'])
        self.assertEqual(camp['state']['location'], 'Black throne room')
        seen = {}
        def mock_chat(messages, model):
            seen['context'] = messages[0]['content']
            return json.dumps({'narration':'Your visitor bows.', 'state_updates': {}})
        engine.play_turn(self.db, camp['id'], '__START__', chat=mock_chat)
        self.assertIn('Speaks softly and treats manners as currency', seen['context'])
        self.assertIn('The Dark Monarch', seen['context'])

    def test_edit_old_campaign_keeps_messages_state(self):
        camp = engine.new_campaign(self.db, {'world_id':self.world['id'], 'pc_name':'Original', 'description':'Original look'})
        def mock_chat(m, model):
            return json.dumps({'narration':'The inn is quiet.', 'state_updates': {'journal_entry':'Visited inn'}})
        engine.play_turn(self.db,camp['id'],'Visit the inn',chat=mock_chat)
        before=engine.get_messages(self.db,camp['id'])
        updated=engine.update_character(self.db,camp['id'],{'pc_name':'Xeminas','mannerisms':'Never raises his voice','appearance':'Platinum hair'})
        self.assertEqual(updated['pc_name'],'Xeminas')
        self.assertEqual(updated['pc_profile']['description'],'Original look')
        self.assertEqual(updated['pc_profile']['mannerisms'],'Never raises his voice')
        self.assertEqual(engine.get_messages(self.db,camp['id']),before)
        self.assertEqual(updated['state']['journal'], ['Visited inn'])
        self.assertEqual(updated['pc_profile']['appearance'], 'Platinum hair')


class NeuralTTSV020Tests(unittest.TestCase):
    def test_invalid_text_voice_and_speed_never_call_service(self):
        with mock.patch.object(narration.urllib.request, 'urlopen') as call:
            for body in [{'text':''},{'text':'a'*(narration.MAX_TEXT+1)},
                         {'text':'hi','voice':'../../etc/passwd'},
                         {'text':'hi','speed':100}]:
                with self.assertRaises(ValueError):
                    narration.synthesize(body)
            call.assert_not_called()

    def test_proxy_uses_localhost_only_and_mp3(self):
        class Response:
            headers={'Content-Type':'audio/mpeg'}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return b'ID3-FAKE-MP3'
        with mock.patch.object(narration.urllib.request, 'urlopen', return_value=Response()) as call:
            self.assertEqual(narration.synthesize({'text':'Hello there','voice':'bm_george','speed':0.9}),b'ID3-FAKE-MP3')
            request=call.call_args.args[0]
            self.assertEqual(request.full_url,'http://127.0.0.1:7860/v1/audio/speech')
            data=json.loads(request.data)
            self.assertEqual(data['voice'],'bm_george')
            self.assertEqual(data['input'],'Hello there')

if __name__ == '__main__': unittest.main()

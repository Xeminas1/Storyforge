import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = engine.open_db(Path(self.tmp.name)/'test.db')

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def add_world(self):
        return engine.make_world(self.con, {
            'title': 'Winter Keep', 'author': 'Community maker',
            'source_url': 'https://play.fables.gg/worlds/example',
            'sections': [{'title': 'Queen Aster', 'kind': 'npc',
                          'content': 'Queen Aster is suspicious of travellers and does not trust mages.'},
                         {'title': 'Ice Bridge', 'kind': 'location', 'content': 'A bridge guarded by sentries.'}]
        })

    def test_world_attribution_and_persistence(self):
        w = self.add_world()
        self.assertEqual(engine.get_world(self.con,w['id'])['author'], 'Community maker')
        self.assertEqual(engine.list_worlds(self.con)[0]['section_count'], 2)

    def test_reject_bad_world(self):
        with self.assertRaises(ValueError):
            engine.make_world(self.con, {'title': '', 'sections':[]})
        with self.assertRaises(ValueError):
            engine.make_world(self.con, {'title':'x','description':'lore','source_url':'javascript:evil()'})

    def test_cdf_archive_import(self):
        memory = io.BytesIO()
        with zipfile.ZipFile(memory,'w') as archive:
            archive.writestr('Outer/Characters/Queen.character.json', json.dumps({'name':'Queen Aster','description':'Cautious ruler'}))
            archive.writestr('Outer/Lore/Geography.md', '# Ice lands\nCold mountains')
            archive.writestr('.craft/settings.json', '{"something":"ignore"}')
            archive.writestr('../escaped.md','bad archive entry')
        world = engine.import_world_zip(self.con,memory.getvalue(),title='Icy Kingdom',author='Someone')
        self.assertEqual(len(world['sections']),2)
        self.assertEqual(world['sections'][0]['title'],'Queen Aster')
        self.assertIn('Cold mountains',world['sections'][1]['content'])

    def test_reject_bad_archive(self):
        with self.assertRaisesRegex(ValueError, 'valid ZIP'):
            engine.import_world_zip(self.con,b'invalid')

    def test_story_is_saved_and_state_updated(self):
        world = self.add_world()
        camp = engine.new_campaign(self.con,{'world_id':world['id'],'pc_name':'Wren','abilities':'Fireball\nDisguise','description':'A rogue mage'})
        def fake_chat(messages,model):
            self.assertEqual(model,'example')
            self.assertIn('Queen Aster',messages[0]['content'])
            self.assertIn('Fireball',messages[0]['content'])
            return json.dumps({'narration':'The queen refuses to yield.','state_updates':{'location':'Throne Room','journal_entry':'The queen refused the traveller','inventory_add':['iron key']}})
        answer = engine.play_turn(self.con,camp['id'],'I demand an audience with the queen',model='example',chat=fake_chat)
        self.assertEqual(answer['state']['location'],'Throne Room')
        self.assertEqual(answer['state']['inventory'],['iron key'])
        self.assertEqual([m['role'] for m in answer['messages']],['player','gm'])
        self.assertEqual(engine.get_campaign(self.con,camp['id'])['state']['journal'],['The queen refused the traveller'])

    def test_failed_generation_does_not_append_message(self):
        w=self.add_world(); c=engine.new_campaign(self.con,{'world_id':w['id'],'pc_name':'Fae'})
        def fail(messages,model):raise RuntimeError('Ollama not started')
        with self.assertRaises(RuntimeError):engine.play_turn(self.con,c['id'],'hello',chat=fail)
        self.assertEqual(engine.get_messages(self.con,c['id']),[])

    def test_intro_has_only_gm_message(self):
        w=self.add_world();c=engine.new_campaign(self.con,{'world_id':w['id'],'pc_name':'Fae'})
        answer=engine.play_turn(self.con,c['id'],'__START__',chat=lambda messages,model:'{"narration":"A cold night begins.","state_updates":{}}')
        self.assertEqual(len(answer['messages']),1)
        self.assertEqual(answer['messages'][0]['role'],'gm')

    def test_patch_filters_invalid_lists(self):
        state={'location':'Unknown','inventory':['coin'],'journal':[],'last_action':''}
        patched=engine.apply_patch(state,{'location':'Dock','inventory_add':['map','map'],'inventory_remove':['coin'],'journal_entry':'A boat arrived'},'I inspect the boat')
        self.assertEqual(patched['inventory'],['map'])
        self.assertEqual(patched['journal'],['A boat arrived'])
        self.assertEqual(state['inventory'],['coin'])

    def test_retrieval_prefers_matching_lore(self):
        sections=[{'title':'River','kind':'lore','content':'deep water'}, {'title':'The necromancer','kind':'npc','content':'A sorcerer commanding the dead'}]
        result=engine.pick_sections(sections,'Find the necromancer',max_characters=150)
        self.assertTrue(result.startswith('[npc: The necromancer]'))

    def test_parse_invalid_model_output(self):
        with self.assertRaises(ValueError):engine.parse_gm_response('not json')
        narration,patch=engine.parse_gm_response('```json\n{"narration":"Yes.","state_updates":{}}\n```')
        self.assertEqual(narration,'Yes.')


if __name__=='__main__':unittest.main()

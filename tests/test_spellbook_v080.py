"""Expanded ability definitions, voice-safe prose, and local artwork regression tests."""
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import engine
import narration

MINI_PNG=bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000b49444154789c636000020000050001a5f645400000000049454e44ae426082')

class SpellbookV080(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Path(self.temp.name)/'storyforge.db'
        self.con=engine.open_db(self.db)
        self.world=engine.make_world(self.con,{'title':'Test world','description':'world lore'})
        self.char=engine.create_character(self.con,{'pc_name':'Xeminas','abilities':'Gravitational Grasp\nHorde Summon'})
    def tearDown(self):
        self.con.close();self.temp.cleanup()

    def test_legacy_ability_names_migrate_to_stable_ids(self):
        a=engine.get_character(self.con,self.char['id'])
        first=a['profile']['ability_details']
        self.assertEqual([x['name'] for x in first],['Gravitational Grasp','Horde Summon'])
        self.assertEqual(first,[x for x in engine.get_character(self.con,self.char['id'])['profile']['ability_details']])
        self.assertTrue(all(x['id'] for x in first))

    def test_edit_definitions_and_reuse_without_losing_other_fields(self):
        original=engine.get_character(self.con,self.char['id'])
        rows=original['profile']['ability_details']
        rows[0].update(kind='Spell',effect='Pins a target under intense gravity',visual='Violet distortion',
                       cost='Some mana',limitations='Strong enemies may resist')
        saved=engine.save_library_abilities(self.con,self.char['id'],rows)
        self.assertEqual(saved['profile']['ability_details'][0]['effect'],'Pins a target under intense gravity')
        self.assertEqual(saved['profile']['abilities'],['Gravitational Grasp','Horde Summon'])
        game=engine.new_campaign(self.con,{'world_id':self.world['id'],'character_id':self.char['id']})
        self.assertEqual(game['pc_profile']['ability_details'][0]['effect'],'Pins a target under intense gravity')
        changed=engine.update_character(self.con,game['id'],{'personality':'Polite and calculating'})
        self.assertEqual(changed['pc_profile']['ability_details'][0]['cost'],'Some mana')
        self.assertEqual(changed['pc_profile']['personality'],'Polite and calculating')

    def test_casting_spell_references_effect_and_limit_in_gm_prompt(self):
        records=engine.get_character(self.con,self.char['id'])['profile']['ability_details']
        records[0].update(effect='Puts immense pressure on the target',limitations='No effect through lead walls')
        engine.save_library_abilities(self.con,self.char['id'],records)
        campaign=engine.new_campaign(self.con,{'world_id':self.world['id'],'character_id':self.char['id']})
        captures=[]
        def llm(messages,model):
            captures.append(messages)
            return json.dumps({'narration':'The guard feels the pressure.','state_updates':{}})
        engine.play_turn(self.con,campaign['id'],'I cast Gravitational Grasp at the guard',chat=llm)
        system=captures[0][0]['content']
        self.assertIn('Puts immense pressure on the target',system)
        self.assertIn('No effect through lead walls',system)
        self.assertIn('Do not assume the character always succeeds',system)

    def test_gm_removes_markup_and_preserves_plain_prose(self):
        s=engine.speech_friendly_prose('The word \\* wrong \\* echoes. The answer is **no**.')
        self.assertEqual(s,'The word wrong echoes. The answer is no.')
        narrative,_=engine.parse_gm_response(json.dumps({'narration':'A *wrong* decision.','state_updates':{}}))
        self.assertEqual(narrative,'A wrong decision.')
        self.assertEqual(engine.speech_friendly_prose('2 * 3'),'2 times 3')

    def test_spell_images_are_local(self):
        spell=engine.get_character(self.con,self.char['id'])['profile']['ability_details'][0]
        saved=engine.save_spell_image(self.db,spell['id'],MINI_PNG)
        self.assertTrue(saved.is_file())
        self.assertIn('artwork/spells/',str(saved))
        self.assertEqual(engine.spell_image_file(self.db,spell['id']),saved)
        self.assertEqual(engine.find_spell(self.char['profile'] if self.char['profile'].get('ability_details') else engine.get_character(self.con,self.char['id'])['profile'],spell['id'])['name'],'Gravitational Grasp')
        with self.assertRaises(LookupError):engine.find_spell(engine.get_character(self.con,self.char['id'])['profile'],'not-a-real-spell')

    def test_reject_duplicate_spells(self):
        with self.assertRaisesRegex(ValueError,'unique'):
            engine.save_library_abilities(self.con,self.char['id'],[{'name':'Fire'}, {'name':'fire'}])

if __name__=='__main__':unittest.main()

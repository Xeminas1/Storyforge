"""Reusable character identities and legacy campaign migration."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import engine

class ReusableCharactersTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'data'/'storyforge.db'
        self.con=engine.open_db(self.path)
        self.world=engine.make_world(self.con,{'title':'Library World','description':'World lore'})

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_create_reuse_and_isolation(self):
        original=engine.create_character(self.con,{'pc_name':'Xeminas','species':'High Elf',
          'mannerisms':'Speaks politely','abilities':'Shadow grasp\nRaise dead','starting_items':'Black ring'})
        one=engine.new_campaign(self.con,{'world_id':self.world['id'],'character_id':original['id']})
        two=engine.new_campaign(self.con,{'world_id':self.world['id'],'character_id':original['id']})
        self.assertNotEqual(one['id'],two['id'])
        self.assertEqual(two['pc_profile']['mannerisms'],'Speaks politely')
        self.assertEqual(two['state']['inventory'],['Black ring'])
        engine.update_character(self.con,one['id'],{'pc_name':'Xeminas','mannerisms':'Folded hands'})
        self.assertEqual(engine.get_character(self.con,original['id'])['profile']['mannerisms'],'Folded hands')
        self.assertEqual(engine.get_campaign(self.con,two['id'])['pc_profile']['mannerisms'],'Speaks politely')
        self.assertEqual(engine.get_campaign(self.con,one['id'])['state']['inventory'],['Black ring'])

    def test_existing_campaign_saved_into_library_once(self):
        legacy=engine.new_campaign(self.con,{'world_id':self.world['id'], 'pc_name':'Old Hero','appearance':'Silver hair'})
        legacy_id=legacy['id']
        char_id=legacy['character_id']
        # Simulate a v0.6 database before the character_id column existed.
        self.con.execute('DROP TABLE character_library')
        self.con.execute('ALTER TABLE campaigns DROP COLUMN character_id')
        self.con.commit();self.con.close()
        with engine.open_db(self.path) as con:
            items=engine.list_characters(con)
            self.assertEqual(len(items),1)
            self.assertEqual(items[0]['name'],'Old Hero')
            self.assertEqual(engine.get_campaign(con,legacy_id)['pc_profile']['appearance'],'Silver hair')
        with engine.open_db(self.path) as con:
            self.assertEqual(len(engine.list_characters(con)),1)

    def test_profile_updates_preserve_other_characters(self):
        a=engine.create_character(self.con,{'pc_name':'Xeminas','mannerisms':'Cold'})
        b=engine.create_character(self.con,{'pc_name':'Alaric','mannerisms':'Kind'})
        engine.edit_library_character(self.con,a['id'],{'mannerisms':'Imperious','pc_name':'Dark Monarch'})
        self.assertEqual(engine.get_character(self.con,a['id'])['profile']['mannerisms'],'Imperious')
        self.assertEqual(engine.get_character(self.con,b['id'])['profile']['mannerisms'],'Kind')
        with self.assertRaises(LookupError):engine.new_campaign(self.con,{'world_id':self.world['id'],'character_id':'not-exists'})

    def test_existing_portrait_copied_to_new_campaign(self):
        c=engine.create_character(self.con,{'pc_name':'Portrait hero'})
        png=(b'\x89PNG\r\n\x1a\n'+b'\0'*4+b'IHDR'+b'\0'*40)
        engine.save_portrait(self.path,c['id'],png)
        new=engine.new_campaign(self.con,{'world_id':self.world['id'],'character_id':c['id']})
        self.assertEqual(engine.character_file(self.path,new['id']).read_bytes(),png)
        self.assertEqual(engine.character_file(self.path,c['id']).read_bytes(),png)

if __name__=='__main__':unittest.main()

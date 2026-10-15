"""Narrator/player agency and source-attributed franchise discovery regression."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import engine
import lore

class LoreAgencyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.con=engine.open_db(Path(self.temp.name)/'test.db')
        self.world=engine.make_world(self.con,{'title':'Wizarding World','description':'Wizarding setting'})
        self.pc=engine.new_campaign(self.con,{'world_id':self.world['id'],'pc_name':'Xeminas'})
    def tearDown(self):
        self.con.close();self.temp.cleanup()
    def test_related_searches(self):
        terms=lore.terms_for_universe('harry potter: wizarding world','magnificent beasts')
        self.assertIn('Fantastic Beasts',terms)
        self.assertIn('List of Harry Potter characters',terms)
    def test_lore_search_deduplicates_and_attributes(self):
        def fake(q):
            return [{'id':'123','title':'Hogwarts','kind':'location','summary':'An ancient magical school','url':'https://en.wikipedia.org/?curid=123','license':'CC BY-SA 4.0'}]
        data=lore.discover('Harry Potter',fetch=fake)
        self.assertEqual(len(data['entries']),1)
        sections=lore.as_sections(data['entries'])
        self.assertIn('Source: https://en.wikipedia.org/',sections[0]['content'])
        first=engine.append_world_lore(self.con,self.world['id'],sections)
        self.assertEqual(first['added'],1)
        second=engine.append_world_lore(self.con,self.world['id'],sections)
        self.assertEqual(second['added'],0)
        self.assertEqual(len(first['sections']),2)
    def test_unapproved_external_url_rejected(self):
        with self.assertRaisesRegex(ValueError,'Wikipedia'):
            lore.as_sections([{'title':'Fake','summary':'fake','url':'http://127.0.0.1/admin'}])
    def test_invalid_model_talks_for_player_and_retry(self):
        samples=iter([json.dumps({'narration':'“I am Xeminas,” you declare, as you raise a hand.','state_updates':{}}),
            json.dumps({'narration':'A stranger steps aside and stares at the visitor in silence.','state_updates':{}})])
        calls=[]
        def chat(messages,model):calls.append(messages);return next(samples)
        result=engine.play_turn(self.con,self.pc['id'],'I approach the stranger',chat=chat)
        self.assertEqual(len(calls),2)
        self.assertNotIn('you declare',result['narration'])
        self.assertIn('REWRITE THIS TURN',calls[1][-1]['content'])
        self.assertEqual(len(engine.get_messages(self.con,self.pc['id'])),2)
    def test_bad_repeated_reply_does_not_consume_action(self):
        bad=json.dumps({'narration':'“I am the Dark Monarch,” you declare. You raise your hand.','state_updates':{'location':'The throne room'}})
        before=self.con.execute('SELECT count(*) FROM messages').fetchone()[0]
        with self.assertRaisesRegex(ValueError,'Nothing was saved'):
            engine.play_turn(self.con,self.pc['id'],'I stand quietly',chat=lambda *_:bad)
        self.assertEqual(self.con.execute('SELECT count(*) FROM messages').fetchone()[0],before)
        self.assertEqual(engine.get_campaign(self.con,self.pc['id'])['state']['location'],'Unknown')
    def test_first_person_npc_quote_allowed(self):
        line='“I am the guard,” the sentry says, reaching for his whistle.'
        self.assertEqual(engine.player_agency_violations(line,'Xeminas','I approach'),[])
    def test_plain_invalid_response_retried_without_saving(self):
        results=iter(['The air is shimmering',json.dumps({'narration':'An old wizard waits.','state_updates':{}})])
        answer=engine.play_turn(self.con,self.pc['id'],'I wait',chat=lambda *_:next(results))
        self.assertIn('wizard waits',answer['narration'])

if __name__=='__main__':unittest.main()

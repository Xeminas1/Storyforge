"""Regression coverage of reported Hogwarts first-person and stored-journal hallucinations."""
import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import engine


class AgencyHotfixTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=engine.open_db(pathlib.Path(self.tmp.name)/'db.sqlite3')
        self.world=engine.make_world(self.db,{'title':'Wizarding World','description':'A magical setting'})
        self.pc=engine.new_campaign(self.db,{'world_id':self.world['id'],'pc_name':'Xeminas'})
        self.action='i smile knowing that voldemort seeks me, i continue on'
    def tearDown(self):
        self.db.close();self.tmp.cleanup()
    def test_exact_reported_hallucinations_are_rejected(self):
        paragraph=("[Hogwarts Castle - Harry Potter: Wizarding World - Time unspecified]\n\n"
          "The figure in tattered robes steps forward. 'No... you are not Voldemort,' they whisper. "
          "The Sorting Hat's warning echoes in my mind. I raise my hand and the air crackles.")
        errors=engine.player_agency_violations(paragraph,'Xeminas',self.action)
        self.assertTrue(any('first-person' in e for e in errors),errors)
        self.assertTrue(engine.player_agency_violations('Xeminas raises his hand.','Xeminas',self.action))
        self.assertTrue(engine.player_agency_violations('The Dark Monarch declared his name.','Xeminas',self.action))
        self.assertTrue(engine.player_agency_violations('You decide to confront him.','Xeminas',self.action))
    def test_spoken_npc_first_person_is_allowed(self):
        good='“I am the guard,” the sentry says. You smile and continue past him.'
        self.assertEqual(engine.player_agency_violations(good,'Xeminas',self.action),[])
    def test_story_developments_are_checked_as_well_as_narration(self):
        examples=iter([
            json.dumps({'narration':'An ancient wizard steps away from the door.','state_updates':{'journal_entry':'He thought I was Voldemort, but I made it clear I am the Dark Monarch.'}}),
            json.dumps({'narration':'The wizard turns and speaks with the passing guards.','state_updates':{'journal_entry':'An old wizard mistakes the traveller for Voldemort.'}})
        ])
        r=engine.play_turn(self.db,self.pc['id'],self.action,chat=lambda *args: next(examples))
        self.assertEqual(r['state']['journal'],['An old wizard mistakes the traveller for Voldemort.'])
        self.assertEqual(len(r['messages']),2)
    def test_bad_both_attempts_no_save(self):
        raw=json.dumps({'narration':'I raise my hand.','state_updates':{'journal_entry':'I made it clear I was the Dark Monarch'}})
        with self.assertRaisesRegex(ValueError,'Nothing was saved'):
            engine.play_turn(self.db,self.pc['id'],self.action,chat=lambda *args:raw)
        self.assertFalse(engine.get_messages(self.db,self.pc['id']))
        self.assertFalse(engine.get_campaign(self.db,self.pc['id'])['state']['journal'])
    def test_bad_old_journal_not_presented_as_canon(self):
        state=engine.get_campaign(self.db,self.pc['id'])['state']
        state['journal']=['He thought I was Voldemort, but I made it clear I am the Dark Monarch','A new visitor was seen near the station']
        self.db.execute('UPDATE campaigns SET state_json=? WHERE id=?',(json.dumps(state),self.pc['id']))
        self.db.commit()
        calls=[]
        def chat(messages,model):
            calls.append(messages)
            return json.dumps({'narration':'A stranger asks the conductor for directions.','state_updates':{}})
        engine.play_turn(self.db,self.pc['id'],'I watch the crowd',chat=chat)
        self.assertNotIn('I made it clear',calls[0][0]['content'])
        self.assertIn('A new visitor was seen',calls[0][0]['content'])
    def test_player_removes_only_false_journal_entry(self):
        record=engine.get_campaign(self.db,self.pc['id'])
        state=record['state'];state['journal']=['False memory','True memory']
        self.db.execute('UPDATE campaigns SET state_json=? WHERE id=?',(json.dumps(state),self.pc['id']))
        self.db.commit()
        with self.assertRaisesRegex(ValueError,'Refresh'):
            engine.remove_journal_entry(self.db,self.pc['id'],0,'Not the current text')
        got=engine.remove_journal_entry(self.db,self.pc['id'],0,'False memory')
        self.assertEqual(got['state']['journal'],['True memory'])
        self.assertEqual(engine.get_campaign(self.db,self.pc['id'])['state']['journal'],['True memory'])

if __name__=='__main__':unittest.main()

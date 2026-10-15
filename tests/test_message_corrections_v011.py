"""Storyforge v0.11.0: message rewind, resending, safe retries and local feedback."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import engine


def response(narration, **patch):
    return json.dumps({'narration': narration, 'state_updates': patch})


class MessageCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'storyforge.db'
        self.db = engine.open_db(self.path)
        world = engine.make_world(self.db, {'title':'Veyr','description':'Lantern docks'})
        self.campaign = engine.new_campaign(self.db, {'world_id':world['id'],'pc_name':'Xeminas'})
        self.cid=self.campaign['id']

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def turn(self, action, text='A sentry peers across the river.', **changes):
        return engine.play_turn(self.db,self.cid,action,chat=lambda *_:response(text,**changes))

    def test_messages_have_checkpoints_and_state_before_after(self):
        self.turn('I approach the dock','The sentinel beckons.',inventory_add=['silver key'],location='The Ash Quay')
        self.turn('I wait quietly','A fisherman shouts.',journal_entry='Waited for boats',inventory_remove=['silver key'])
        msg=engine.get_messages(self.db,self.cid)
        self.assertEqual([m['role'] for m in msg],['player','gm','player','gm'])
        self.assertTrue(msg[1]['has_checkpoint'])
        cp=self.db.execute('SELECT state_before,state_after,source_action FROM turn_checkpoints WHERE gm_message_id=?',(msg[1]['id'],)).fetchone()
        self.assertEqual(json.loads(cp['state_before'])['location'],'Unknown')
        self.assertEqual(json.loads(cp['state_after'])['inventory'],['silver key'])
        self.assertEqual(cp['source_action'],'I approach the dock')

    def test_retry_gm_uses_same_input_and_rolls_back_subsequent_events(self):
        self.turn('I walk to the docks','A dockworker shouts.',inventory_add=['coin'],location='Docks')
        self.turn('I sit','A crow flies off.',inventory_add=['feather'],journal_entry='The crow fled',location='Market')
        gm=engine.get_messages(self.db,self.cid)[1]
        calls=[]
        def fake(messages,model):
            calls.append(messages)
            return response('A harbourmaster asks for your papers.',inventory_add=['ledger'],location='The Jetty')
        result=engine.retry_message(self.db,self.cid,gm['id'],feedback='Never invent player dialogue.',chat=fake)
        self.assertEqual([m['role'] for m in result['messages']],['player','gm'])
        self.assertEqual(result['messages'][0]['content'],'I walk to the docks')
        self.assertEqual(result['state']['inventory'],['ledger'])
        self.assertEqual(result['state']['location'],'The Jetty')
        self.assertFalse(result['state']['journal'])
        self.assertEqual(calls[0][-1]['content'],'I walk to the docks')
        self.assertIn('Never invent player dialogue.',calls[0][0]['content'])
        self.assertEqual(self.db.execute('SELECT count(*) FROM gm_feedback').fetchone()[0],1)

    def test_delete_gm_preserves_player_then_resend_without_duplicate(self):
        self.turn('I study the book','A mage speaks.',inventory_add=['gem'],journal_entry='Found gem')
        original=engine.get_messages(self.db,self.cid)
        removed=engine.delete_message(self.db,self.cid,original[1]['id'],reason='Wrong outcome')
        self.assertEqual([m['role'] for m in removed['messages']],['player'])
        self.assertEqual(removed['state']['inventory'],[])
        self.assertEqual(removed['state']['journal'],[])
        resend=engine.retry_message(self.db,self.cid,original[0]['id'],feedback='Make the mage ask a question.',chat=lambda *_:response('The mage asks about the book.',inventory_add=['map']))
        self.assertEqual([m['role'] for m in resend['messages']],['player','gm'])
        self.assertEqual(resend['messages'][0]['id'],original[0]['id'])
        self.assertEqual(resend['state']['inventory'],['map'])
        self.assertNotIn('gem',resend['state']['inventory'])

    def test_delete_player_rewinds_dependent_gm_and_later_actions(self):
        self.turn('I enter','A guard answers.',location='Castle',inventory_add=['book'])
        self.turn('I leave','A horse whinnies.',location='Street')
        first=engine.get_messages(self.db,self.cid)[0]
        result=engine.delete_message(self.db,self.cid,first['id'])
        self.assertEqual(result['messages'],[])
        self.assertEqual(result['state']['location'],'Unknown')
        self.assertEqual(result['state']['inventory'],[])

    def test_retry_failure_preserves_entire_conversation(self):
        self.turn('I listen','The dock remains silent.',location='Dock')
        before=engine.get_messages(self.db,self.cid)
        prior_state=engine.get_campaign(self.db,self.cid)['state']
        with self.assertRaises(RuntimeError):
            engine.retry_message(self.db,self.cid,before[-1]['id'],feedback='Not lively enough',chat=lambda *_:(_ for _ in ()).throw(RuntimeError('Ollama down')))
        self.assertEqual(before,engine.get_messages(self.db,self.cid))
        self.assertEqual(prior_state,engine.get_campaign(self.db,self.cid)['state'])
        self.assertEqual(self.db.execute('SELECT count(*) FROM gm_feedback').fetchone()[0],0)

    def test_feedback_influences_subsequent_turn_without_retraining(self):
        self.turn('I wait','A guard scratches his nose.')
        gm=engine.get_messages(self.db,self.cid)[-1]
        engine.retry_message(self.db,self.cid,gm['id'],feedback='No invented speech for Xeminas.',chat=lambda *_:response('The guard asks your name.'))
        collected=[]
        def fake(messages,model):
            collected.append(messages[0]['content'])
            return response('The guard pauses.')
        self.turn('I stand silently','A wind gusts.')
        engine.play_turn(self.db,self.cid,'I examine a sword',chat=fake)
        self.assertIn('No invented speech for Xeminas.',collected[0])

    def test_invalid_message_id_and_wrong_campaign(self):
        self.turn('hello')
        with self.assertRaises(LookupError):engine.delete_message(self.db,self.cid,88888)
        with self.assertRaises(LookupError):engine.retry_message(self.db,self.cid,88888)
        with self.assertRaises(LookupError):engine.delete_message(self.db,'bad-campaign',1)

    def test_legacy_messages_preserve_current_state_and_are_flagged(self):
        self.turn('I travel','An empty street appears.',location='Old Town',inventory_add=['ring'])
        old=engine.get_messages(self.db,self.cid)[-1]
        self.db.execute('DELETE FROM turn_checkpoints WHERE gm_message_id=?',(old['id'],))
        self.db.commit()
        result=engine.retry_message(self.db,self.cid,old['id'],chat=lambda *_:response('A shop opens.',inventory_add=['map']))
        self.assertTrue(result['legacy_state_warning'])
        self.assertEqual(result['state']['inventory'],['ring','map'])

    def test_intro_can_retry_without_creating_player_message(self):
        intro=self.turn('__START__','Sunrise brightens the shore.',location='Harbour')
        self.assertEqual(len(intro['messages']),1)
        new=engine.retry_message(self.db,self.cid,intro['messages'][0]['id'],chat=lambda *_:response('Dusk deepens over the shore.',location='Meadow'))
        self.assertEqual(len(new['messages']),1)
        self.assertEqual(new['messages'][0]['role'],'gm')
        self.assertEqual(new['state']['location'],'Meadow')

    def test_cannot_add_new_action_over_unanswered_player_message(self):
        self.turn('I find a map')
        gm=engine.get_messages(self.db,self.cid)[-1]
        engine.delete_message(self.db,self.cid,gm['id'])
        with self.assertRaisesRegex(ValueError,'Resend'):
            self.turn('I find a second map')

    def test_atomic_revision_conflict_does_not_save_rewrite(self):
        self.turn('I enter','The innkeeper waves.')
        gm=engine.get_messages(self.db,self.cid)[-1]
        def concurrent(messages,model):
            with engine.open_db(self.path) as another:
                with another:
                    another.execute('UPDATE campaigns SET revision=revision+1 WHERE id=?',(self.cid,))
            return response('A stranger whistles.')
        before=engine.get_messages(self.db,self.cid)
        with self.assertRaisesRegex(ValueError,'changed during generation'):
            engine.retry_message(self.db,self.cid,gm['id'],chat=concurrent)
        self.assertEqual(before,engine.get_messages(self.db,self.cid))
        self.assertFalse(self.db.execute('SELECT 1 FROM gm_feedback').fetchone())


if __name__=='__main__':unittest.main()

# HTTP-level checks do not need a running Ollama model.
class CorrectionHttpTests(unittest.TestCase):
    def setUp(self):
        import server
        from http.server import ThreadingHTTPServer
        from threading import Thread
        from unittest.mock import MagicMock
        self.server_module=server
        self.temp=tempfile.TemporaryDirectory()
        self.dbfile=Path(self.temp.name)/'storyforge.db'
        server.DB_PATH=self.dbfile
        with engine.open_db(self.dbfile) as db:
            w=engine.make_world(db,{'title':'Local Story','description':'A wooden tavern'})
            c=engine.new_campaign(db,{'world_id':w['id'],'pc_name':'Xeminas'})
            self.cid=c['id']
            engine.play_turn(db,self.cid,'I enter',chat=lambda *_:response('A witch glances over.',location='Workshop'))
        self.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.http.release_watcher=MagicMock()
        self.thread=Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(2)
        self.temp.cleanup()

    def send(self,path,body):
        import urllib.request,urllib.error
        req=urllib.request.Request('http://127.0.0.1:'+str(self.http.server_port)+path,
           headers={'Content-Type':'application/json'},data=json.dumps(body).encode(),method='POST')
        try:
            with urllib.request.urlopen(req,timeout=4) as reply:
                return reply.status,json.load(reply)
        except urllib.error.HTTPError as exc:return exc.code,json.load(exc)

    def test_http_delete_then_resend(self):
        with engine.open_db(self.dbfile) as db:
            messages=engine.get_messages(db,self.cid)
        gm_id=messages[-1]['id']
        path=f'/api/campaigns/{self.cid}/messages/{gm_id}/delete'
        code,res=self.send(path,{'feedback':'No control of Xeminas.'})
        self.assertEqual(code,400)
        self.assertIn('confirmation',res['error'])
        code,res=self.send(path,{'feedback':'No control of Xeminas.','confirm':'REWIND'})
        self.assertEqual(code,200)
        self.assertEqual(len(res['messages']),1)
        from unittest.mock import patch
        original=engine.retry_message
        def fake(con,*args,**kw):
            return original(con,*args,chat=lambda *_:response('The witch nods respectfully.',location='Workshop'),**kw)
        with patch.object(engine,'retry_message',side_effect=fake):
            code,new=self.send(f'/api/campaigns/{self.cid}/messages/{messages[0]["id"]}/retry',
                         {'feedback':'Allow me to speak for myself.'})
        self.assertEqual(code,200)
        self.assertEqual([x['role'] for x in new['messages']],['player','gm'])
        with engine.open_db(self.dbfile) as db:
            corrections=db.execute('SELECT operation, reason FROM gm_feedback ORDER BY id').fetchall()
        self.assertEqual(len(corrections),2)
        self.assertEqual(corrections[1]['operation'],'resend')

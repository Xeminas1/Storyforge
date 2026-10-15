"""v0.12: regression checks for repeated GM prose, safe retries and music UI."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import engine


def payload(narration):
    return json.dumps({'narration':narration,'state_updates':{}})

class AmbientAndRepeatTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=engine.open_db(Path(self.tmp.name)/'storyforge.db')
        world=engine.make_world(self.db,{'title':'Tavern world','description':'A bright tavern'})
        self.cid=engine.new_campaign(self.db,{'world_id':world['id'],'pc_name':'Xeminas'})['id']
    def tearDown(self):
        self.db.close();self.tmp.cleanup()
    def test_repeating_previous_reply_is_rewritten_and_prior_saved_once(self):
        earlier=('The captain lights the first harbour lantern while the people of the quay '
            'begin to sing about lost ships and rumours of the royal court. '*3)
        engine.play_turn(self.db,self.cid,'I wait',chat=lambda *_:payload(earlier))
        calls=[]
        def chat(msg,model):
            calls.append(msg)
            return payload(earlier if len(calls)==1 else 'A messenger enters with a sealed letter. The captain asks whether you wish to read it.')
        res=engine.play_turn(self.db,self.cid,'I observe the captain',chat=chat)
        self.assertEqual(len(calls),2)
        self.assertIn('do not repeat earlier narration',calls[1][-1]['content'])
        self.assertIn('A messenger enters',res['narration'])
        self.assertEqual(len(engine.get_messages(self.db,self.cid)),4)
    def test_twice_repeated_reply_preserves_existing_history(self):
        earlier='The messenger has arrived and rings the ancient bell. '*7
        engine.play_turn(self.db,self.cid,'I remain still',chat=lambda *_:payload(earlier))
        before=engine.get_messages(self.db,self.cid)
        with self.assertRaisesRegex(ValueError,'Nothing was saved'):
            engine.retry_message(self.db,self.cid,before[-1]['id'],feedback='Stop repeating',chat=lambda *_:payload(earlier))
        self.assertEqual(before,engine.get_messages(self.db,self.cid))
    def test_repeated_short_place_name_does_not_block_new_scene(self):
        prior=[{'role':'gm','content':'A guard stands at The Ash Quay.'}]
        self.assertEqual(engine.gm_repetition_violations('The Ash Quay has another visitor today.',prior),[])
    def test_inner_paragraph_duplication(self):
        para='A dark procession moves under the bridge while the night guards ring their bells and the inns shut their doors to strangers.'
        self.assertTrue(engine.gm_repetition_violations(para+'\n\n'+para,[]))
    def test_model_request_bounded_and_thinking_disabled(self):
        class FakeReply:
            def __enter__(self):return self
            def __exit__(self,*_):pass
        with patch('engine.urllib.request.urlopen',return_value=FakeReply()) as call,patch('engine.json.load',return_value={'message':{'content':'{}'}}):
            engine.ollama_chat([{'role':'user','content':'Hi'}],'qwen3:8b')
        request=call.call_args.args[0]
        sent=json.loads(request.data)
        self.assertFalse(sent['think'])
        self.assertEqual(sent['options']['num_predict'],1050)
        self.assertLessEqual(call.call_args.kwargs['timeout'],70)
    def test_ui_music_controls_and_scene_matching(self):
        root=Path(__file__).resolve().parents[1]
        html=(root/'static/index.html').read_text()
        js=(root/'static/app.js').read_text()
        for name in ('ambient-toggle','ambient-auto','ambient-volume','ambient-mood','ambient-status'):
            self.assertIn('id="'+name+'"',html)
        self.assertIn('function ambientSceneMood()',js)
        self.assertIn('function ambientSetVolume()',js)
        self.assertIn('function ambientStartMood()',js)
        self.assertIn('ambientSetVolume();',js)
        self.assertIn('clearInterval(ambient.tick)',js)
        self.assertIn('AudioContext',js)

if __name__=='__main__':unittest.main()

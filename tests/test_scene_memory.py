"""Evidence-bound state and additive, rewindable campaign continuity."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import engine


def response(narration, **changes):
    return json.dumps({'narration':narration,'state_updates':changes})


def fact(text, evidence=None):
    return {'text':text,'evidence':evidence or text}


class SceneMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(tempfile.TemporaryDirectory())
        self.db=engine.open_db(Path(self.temp)/'test.db')
        self.addCleanup(self.db.close)
        world=engine.make_world(self.db,{'title':'River Gate','description':'A sentry watches the harbour.'})
        self.cid=engine.new_campaign(self.db,{'world_id':world['id'],'pc_name':'Xeminas'})['id']

    def dump(self):
        return '\n'.join(self.db.iterdump())

    def play(self,text,changes=None,action='I listen.'):
        return engine.play_turn(self.db,self.cid,action,chat=lambda *_:response(text,**(changes or {})))

    def test_production_rejects_unnarrated_state_and_keeps_database_identical(self):
        before=self.dump()
        raw=response('A porter checks the arrival board.',location='Great Hall',
                     inventory_add=['Sorting Hat'],journal_entry='The ceremony has finished.')
        with patch.object(engine,'ollama_chat',return_value=raw) as chat:
            with self.assertRaisesRegex(ValueError,'Nothing was saved'):
                engine.play_turn(self.db,self.cid,'I wait.',chat=chat)
        self.assertEqual(chat.call_count,2)
        self.assertEqual(self.dump(),before)

    def test_production_accepts_state_only_from_exact_visible_evidence(self):
        text='At River Gate, the sentry puts a brass token into your hand. The sentry calls for the gatekeeper.'
        raw=response(text,location='River Gate',inventory_add=['brass token'],
                     journal_entry='The sentry calls for the gatekeeper.',
                     evidence={'location':text,'inventory_add':text,
                               'journal_entry':'The sentry calls for the gatekeeper.'})
        with patch.object(engine,'ollama_chat',return_value=raw) as chat:
            result=engine.play_turn(self.db,self.cid,'I listen.',chat=chat)
        self.assertEqual(result['state']['location'],'River Gate')
        self.assertEqual(result['state']['inventory'],['brass token'])
        self.assertNotIn('evidence',result['state'])

    def test_unrelated_evidence_does_not_justify_a_different_state_value(self):
        raw=response('The sentry watches the harbour.',location='Great Hall',
                     evidence={'location':'The sentry watches the harbour.'})
        before=self.dump()
        with patch.object(engine,'ollama_chat',return_value=raw) as chat:
            with self.assertRaisesRegex(ValueError,'Nothing was saved'):
                engine.play_turn(self.db,self.cid,'I wait.',chat=chat)
        self.assertEqual(self.dump(),before)

    def test_memory_preserves_npcs_open_threads_and_established_events(self):
        text='Maribel guards the brass observatory key. A sealed letter awaits an answer.'
        proposal={'summary':fact(text),
                  'npcs':[{'name':'Maribel','fact':'Maribel guards the brass observatory key.',
                           'evidence':'Maribel guards the brass observatory key.'}],
                  'open_threads':[fact('A sealed letter awaits an answer.')],
                  'events':[fact('Maribel guards the brass observatory key.')]}
        first=self.play(text,{'scene_memory':proposal})
        memory=first['state']['scene_memory']
        self.assertEqual(memory['npcs'][0]['name'],'Maribel')
        self.assertEqual(memory['open_threads'],['A sealed letter awaits an answer.'])
        calls=[]
        def chat(messages,model):
            calls.append(messages)
            return response('Maribel studies the letter seal.')
        engine.play_turn(self.db,self.cid,'I wait.',chat=chat)
        self.assertIn('brass observatory key',calls[0][0]['content'])
        self.assertEqual(engine.get_campaign(self.db,self.cid)['state']['scene_memory'],memory)

    def test_memory_without_narrative_evidence_never_saves(self):
        before=self.dump()
        proposal={'events':[fact('The Sorting Ceremony is complete.','A porter waits.')]}
        with self.assertRaisesRegex(ValueError,'Nothing was saved'):
            self.play('A porter waits.',{'scene_memory':proposal})
        self.assertEqual(self.dump(),before)

    def test_player_is_not_stored_as_a_gm_controlled_npc(self):
        before=self.dump()
        proposal={'npcs':[{'name':'Xeminas','fact':'Xeminas stands at the gate.',
                           'evidence':'Xeminas stands at the gate.'}]}
        with self.assertRaisesRegex(ValueError,'Nothing was saved'):
            self.play('Xeminas stands at the gate.',{'scene_memory':proposal},action='I stand at the gate.')
        self.assertEqual(self.dump(),before)

    def test_retry_restores_memory_before_target_without_later_facts(self):
        first_text='Maribel guards a brass key.'
        self.play(first_text,{'scene_memory':{'events':[fact(first_text)]}})
        before=copy.deepcopy(engine.get_campaign(self.db,self.cid)['state']['scene_memory'])
        second_text='A courier delivers a sealed letter.'
        second=self.play(second_text,{'scene_memory':{'events':[fact(second_text)]}})
        target=second['messages'][-1]['id']
        self.play('A clock strikes midnight.',{'scene_memory':{'events':[fact('A clock strikes midnight.')]}})
        result=engine.retry_message(self.db,self.cid,target,
                     chat=lambda *_:response('The courier waits outside.'))
        self.assertEqual(result['state']['scene_memory'],before)
        self.assertEqual(len(result['messages']),4)

    def test_existing_saves_are_not_given_invented_memory(self):
        state=engine.get_campaign(self.db,self.cid)['state']
        self.assertNotIn('scene_memory',state)
        self.play('The sentry watches the harbour.')
        self.assertNotIn('scene_memory',engine.get_campaign(self.db,self.cid)['state'])


class StrictModelTypes(unittest.TestCase):
    def test_invalid_types_are_rejected_instead_of_coerced(self):
        for narration,updates in [({'text':'A guard waits.'},{}),
                                  ('A guard waits.',[]),
                                  ('A guard waits.',{'location':{'name':'Dock'}}),
                                  ('A guard waits.',{'inventory_add':['key',{'claim':'oath'}]})]:
            with self.subTest(narration=narration,updates=updates):
                with self.assertRaises(ValueError):
                    engine.parse_gm_response(json.dumps({'narration':narration,'state_updates':updates}))


if __name__=='__main__':
    unittest.main()

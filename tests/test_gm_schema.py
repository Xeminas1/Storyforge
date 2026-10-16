"""Exercise the response contract and incomplete local-model completions.

These are protocol tests; semantic narration quality still needs a live model.
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine


class GameMasterSchemaTests(unittest.TestCase):
    def response(self, content=None, **metadata):
        if content is None:
            content = json.dumps({'narration': 'The sentry opens the shutter.', 'state_updates': {}})
        return io.BytesIO(json.dumps({'message': {'content': content}, **metadata}).encode())

    def test_actual_request_constrains_the_envelope_and_current_state_types(self):
        with patch('engine.urllib.request.urlopen', return_value=self.response()) as request:
            engine.ollama_chat([{'role': 'user', 'content': 'I wait.'}], 'qwen3:8b')
        body = json.loads(request.call_args.args[0].data)
        schema = body['format']
        self.assertEqual(schema['type'], 'object')
        self.assertEqual(set(schema['required']), {'narration', 'state_updates'})
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['narration']['type'], 'string')
        state = schema['properties']['state_updates']
        self.assertFalse(state['additionalProperties'])
        self.assertNotIn('required', state)  # Legacy/unchanged state_updates:{} remains valid.
        for field in ('location', 'parent_area', 'time_of_day', 'journal_entry'):
            self.assertEqual(state['properties'][field]['type'], 'string')
        for field in ('inventory_add', 'inventory_remove'):
            self.assertEqual(state['properties'][field]['type'], 'array')
            self.assertEqual(state['properties'][field]['items']['type'], 'string')
            self.assertEqual(state['properties'][field]['maxItems'], 15)

    def test_proposed_memory_and_patch_evidence_have_bounded_typed_contracts(self):
        state = engine.GM_RESPONSE_SCHEMA['properties']['state_updates']['properties']
        evidence = state['evidence']
        self.assertFalse(evidence['additionalProperties'])
        self.assertEqual(set(evidence['properties']), {
            'location', 'parent_area', 'time_of_day', 'journal_entry', 'inventory_add', 'inventory_remove'})
        self.assertTrue(all(rule == {'type': 'string', 'maxLength': 1000}
                            for rule in evidence['properties'].values()))
        memory = state['scene_memory']
        self.assertFalse(memory['additionalProperties'])
        self.assertNotIn('required', memory)
        summary = memory['properties']['summary']
        self.assertEqual(set(summary['required']), {'text', 'evidence'})
        self.assertEqual(summary['properties']['text']['maxLength'], 500)
        self.assertFalse(summary['additionalProperties'])
        for field in ('npcs', 'open_threads', 'events', 'resolve_threads'):
            rule = memory['properties'][field]
            self.assertEqual(rule['type'], 'array')
            self.assertEqual(rule['maxItems'], 8)
            item = rule['items']
            self.assertFalse(item['additionalProperties'])
            expected = {'name', 'fact', 'evidence'} if field == 'npcs' else {'text', 'evidence'}
            self.assertEqual(set(item['required']), expected)
            self.assertEqual(item['properties']['evidence'], {'type': 'string', 'maxLength': 600})

    def test_qwen8b_uses_its_nonthinking_sampling_without_changing_other_models(self):
        for model in ('qwen3:8b', 'qwen3:14b', 'qwen3:30b-a3b', 'llama3.2', 'custom-story-model'):
            with self.subTest(model=model), patch(
                    'engine.urllib.request.urlopen', return_value=self.response()) as request:
                engine.ollama_chat([], model)
                body = json.loads(request.call_args.args[0].data)
                options = body['options']
                self.assertEqual(options['num_ctx'], 8192)
                self.assertEqual(options['num_predict'], 1050)
                if model == 'qwen3:8b':
                    self.assertFalse(body['think'])
                    self.assertEqual({key: options[key] for key in ('temperature', 'top_p', 'top_k', 'min_p')},
                                     {'temperature': 0.7, 'top_p': 0.8, 'top_k': 20, 'min_p': 0})
                else:
                    self.assertEqual(options, {'temperature': 0.6, 'num_ctx': 8192, 'num_predict': 1050})

    def test_length_limited_reply_is_rejected_even_if_the_json_is_complete(self):
        private = json.dumps({'narration': 'PRIVATE_STORY_TEXT', 'state_updates': {}})
        with patch('engine.urllib.request.urlopen', return_value=self.response(
                private, done_reason='length', eval_count=1050)) as request:
            with self.assertLogs('engine.ollama', level='WARNING') as logs:
                with self.assertRaisesRegex(RuntimeError, 'response token limit.*Nothing was saved') as caught:
                    engine.ollama_chat([{'role': 'user', 'content': 'PRIVATE_ACTION'}], 'qwen3:8b')
        self.assertEqual(request.call_count, 1)
        self.assertNotIn('PRIVATE', str(caught.exception))
        self.assertNotIn('PRIVATE', '\n'.join(logs.output))
        metadata = json.loads(logs.output[0].split('Ollama request ', 1)[1])
        self.assertEqual(metadata['status'], 'incomplete_response')
        self.assertEqual(metadata['eval_count'], 1050)

    def test_incomplete_turn_leaves_campaign_and_messages_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            with closing(engine.open_db(Path(directory) / 'storyforge.db')) as con:
                world = engine.make_world(con, {'title': 'River Gate', 'description': 'A sentry keeps watch.'})
                campaign = engine.new_campaign(con, {'world_id': world['id'], 'pc_name': 'Xeminas'})
                before = '\n'.join(con.iterdump())
                with patch('engine.urllib.request.urlopen', return_value=self.response(
                        done_reason='length')) as request:
                    with self.assertLogs('engine.ollama', level='WARNING'):
                        with self.assertRaisesRegex(RuntimeError, 'Nothing was saved'):
                            engine.play_turn(con, campaign['id'], 'I wait.', chat=engine.ollama_chat)
                self.assertEqual(request.call_count, 1)
                self.assertEqual('\n'.join(con.iterdump()), before)

    def test_completed_content_stays_available_for_separate_semantic_validation(self):
        # A schema cannot establish who owns an action. The existing turn layer
        # must assess the content, not assume that well-shaped JSON is safe canon.
        content = json.dumps({'narration': 'Xeminas raises a hand.', 'state_updates': {}})
        with patch('engine.urllib.request.urlopen', return_value=self.response(content, done_reason='stop')):
            self.assertEqual(engine.ollama_chat([], 'qwen3:8b'), content)


if __name__ == '__main__':
    unittest.main()

"""Offline transport checks for bounded, private Ollama generation diagnostics."""
from pathlib import Path
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine


def reply(payload):
    return io.BytesIO(json.dumps(payload).encode('utf-8'))


class GenerationRuntimeTests(unittest.TestCase):
    def test_default_request_keeps_generation_limits_and_model_behavior(self):
        for model, thinking in (('qwen3:8b', False), ('qwen3.5:9b', False), ('other:8b', None)):
            with self.subTest(model=model):
                with patch('engine.urllib.request.urlopen', return_value=reply({'message': {'content': '{}'}})) as call:
                    self.assertEqual(engine.ollama_chat([], model, 'http://localhost:11434'), '{}')
                call.assert_called_once()
                self.assertEqual(call.call_args.kwargs['timeout'], 70)
                sent = json.loads(call.call_args.args[0].data)
                self.assertEqual(sent['options']['num_predict'], 1050)
                self.assertEqual(sent['options']['num_ctx'], 8192)
                self.assertFalse(sent['stream'])
                self.assertEqual(sent.get('think'), thinking)

    def test_keyword_timeout_shares_budget_and_cannot_exceed_70_seconds(self):
        for requested, expected in ((12.25, 12.25), (200, 70)):
            with self.subTest(timeout=requested):
                with patch('engine.urllib.request.urlopen', return_value=reply({'message': {'content': '{}'}})) as call:
                    engine.ollama_chat([], 'qwen3:8b', timeout=requested)
                self.assertEqual(call.call_args.kwargs['timeout'], expected)
                call.assert_called_once()

    def test_invalid_timeout_does_not_start_network_request(self):
        for timeout in (0, -1, float('inf'), float('nan'), True, '70', None):
            with self.subTest(timeout=timeout), patch('engine.urllib.request.urlopen') as call:
                with self.assertRaisesRegex(ValueError, 'positive number'):
                    engine.ollama_chat([], 'qwen3:8b', timeout=timeout)
                call.assert_not_called()

    def test_request_diagnostics_are_numeric_and_do_not_include_private_text(self):
        response = {'message': {'content': 'PRIVATE_RESPONSE'}, 'model': 'PRIVATE_RESPONSE_MODEL',
                    'prompt_eval_count': 123, 'eval_count': 45, 'total_duration': 2_500_000_000,
                    'load_duration': 1_000_000_000, 'prompt_eval_duration': 500_000_000,
                    'eval_duration': 1_000_000_000, 'error': 'PRIVATE_ERROR'}
        messages = [{'role': 'system', 'content': 'PRIVATE_WORLD'}, {'role': 'user', 'content': 'PRIVATE_PLAYER'}]
        with self.assertLogs('engine.ollama', level='INFO') as logs:
            with patch('engine.urllib.request.urlopen', return_value=reply(response)), \
                 patch('engine.time.monotonic', side_effect=[10, 10.125]):
                self.assertEqual(engine.ollama_chat(messages, 'qwen3:8b', timeout=20), 'PRIVATE_RESPONSE')
        self.assertEqual(len(logs.output), 1)
        logged = logs.output[0]
        self.assertNotIn('PRIVATE_', logged)
        self.assertNotIn('localhost', logged)
        diagnostic = json.loads(logged.split('Ollama request ', 1)[1])
        self.assertEqual(diagnostic['status'], 'ok')
        self.assertEqual(diagnostic['model'], 'qwen3:8b')
        self.assertEqual(diagnostic['wall_ms'], 125)
        self.assertEqual(diagnostic['message_count'], 2)
        self.assertGreater(diagnostic['request_bytes'], 0)
        self.assertEqual(diagnostic['output_chars'], len('PRIVATE_RESPONSE'))
        self.assertEqual(diagnostic['prompt_eval_count'], 123)
        self.assertEqual(diagnostic['eval_count'], 45)
        self.assertEqual(diagnostic['total_ms'], 2500)
        self.assertEqual(diagnostic['load_ms'], 1000)
        self.assertRegex(diagnostic['request_id'], r'^[a-f0-9]{32}$')

    def test_metric_values_and_unusual_model_names_cannot_inject_private_log_text(self):
        response = {'message': {'content': '{}'}, 'eval_count': 'PRIVATE_COUNT',
                    'prompt_eval_count': True, 'eval_duration': -1, 'load_duration': 10**400}
        with self.assertLogs('engine.ollama', level='INFO') as logs:
            with patch('engine.urllib.request.urlopen', return_value=reply(response)):
                engine.ollama_chat([], 'PRIVATE_MODEL\nPRIVATE_LOG_LINE')
        diagnostic = json.loads(logs.output[0].split('Ollama request ', 1)[1])
        self.assertEqual(diagnostic['model'], 'custom')
        self.assertNotIn('PRIVATE_', logs.output[0])
        self.assertNotIn('eval_count', diagnostic)
        self.assertNotIn('prompt_eval_count', diagnostic)
        self.assertNotIn('eval_ms', diagnostic)
        self.assertNotIn('load_ms', diagnostic)

    def test_timeouts_provide_actionable_message_without_hidden_http_retry(self):
        for failure in (TimeoutError('PRIVATE_TIMEOUT'), urllib.error.URLError(TimeoutError('PRIVATE_TIMEOUT'))):
            with self.subTest(failure=type(failure).__name__):
                with self.assertLogs('engine.ollama', level='WARNING') as logs:
                    with patch('engine.urllib.request.urlopen', side_effect=failure) as call:
                        with self.assertRaisesRegex(RuntimeError, r'12.5-second limit.*Nothing was saved') as raised:
                            engine.ollama_chat([], 'qwen3:8b', timeout=12.5)
                call.assert_called_once()
                self.assertIn('"status": "timeout"', logs.output[0])
                self.assertNotIn('PRIVATE_', str(raised.exception) + logs.output[0])

    def test_http_errors_do_not_read_or_disclose_ollama_error_body(self):
        for code, guidance in ((404, 'installed'), (500, 'available memory'), (400, 'configuration')):
            with self.subTest(code=code):
                body = io.BytesIO(b'PRIVATE_RESPONSE_BODY')
                failure = urllib.error.HTTPError('http://PRIVATE_HOST', code, 'PRIVATE_REASON', {}, body)
                with patch.object(body, 'read', wraps=body.read) as read:
                    with self.assertLogs('engine.ollama', level='WARNING') as logs:
                        with patch('engine.urllib.request.urlopen', side_effect=failure) as call:
                            with self.assertRaisesRegex(RuntimeError, f'Ollama HTTP {code}') as raised:
                                engine.ollama_chat([], 'qwen3:8b')
                    read.assert_not_called()
                call.assert_called_once()
                self.assertIn(guidance, str(raised.exception))
                self.assertIn('Nothing was saved', str(raised.exception))
                self.assertNotIn('PRIVATE_', str(raised.exception) + logs.output[0])
                self.assertTrue(body.closed)

    def test_connection_failures_do_not_disclose_exception_details_or_retry(self):
        failures = (urllib.error.URLError('PRIVATE_URL_DETAIL'), ConnectionResetError('PRIVATE_SOCKET_DETAIL'))
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                with self.assertLogs('engine.ollama', level='WARNING') as logs:
                    with patch('engine.urllib.request.urlopen', side_effect=failure) as call:
                        with self.assertRaisesRegex(RuntimeError, 'Nothing was saved') as raised:
                            engine.ollama_chat([], 'qwen3:8b')
                call.assert_called_once()
                self.assertNotIn('PRIVATE_', str(raised.exception) + logs.output[0])

    def test_invalid_server_response_is_not_logged_or_retried(self):
        for body in (b'PRIVATE_INVALID_JSON', b'{"message": {"content": null}}', b'[]'):
            with self.subTest(body=body):
                with self.assertLogs('engine.ollama', level='WARNING') as logs:
                    with patch('engine.urllib.request.urlopen', return_value=io.BytesIO(body)) as call:
                        with self.assertRaisesRegex(RuntimeError, 'unexpected response') as raised:
                            engine.ollama_chat([], 'qwen3:8b')
                call.assert_called_once()
                self.assertIn('"status": "invalid_response"', logs.output[0])
                self.assertNotIn('PRIVATE_', str(raised.exception) + logs.output[0])

    def test_external_and_userinfo_spoofed_ollama_hosts_are_rejected(self):
        for host in ('https://external.example:11434', 'http://localhost:11434@external.example',
                     'http://127.0.0.1:11434@external.example', 'http://localhost:bad',
                     'http://localhost:11434/private?credential=PRIVATE_TOKEN'):
            with self.subTest(host=host), patch('engine.urllib.request.urlopen') as call:
                with self.assertRaisesRegex(ValueError, 'local Ollama'):
                    engine.ollama_chat([], 'qwen3:8b', host)
                call.assert_not_called()


class SharedGenerationBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = engine.open_db(Path(self.tmp.name) / 'storyforge.db')
        world = engine.make_world(self.db, {'title': 'Lantern Quay', 'description': 'A quiet river landing.'})
        self.cid = engine.new_campaign(self.db, {'world_id': world['id'], 'pc_name': 'Xeminas'})['id']

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_second_attempt_receives_only_remaining_turn_budget(self):
        calls = []

        def transport(messages, model, *, timeout):
            calls.append((json.loads(json.dumps(messages)), timeout))
            if len(calls) == 1:
                return 'PRIVATE_MALFORMED_DRAFT'
            return json.dumps({'narration': 'A sentry lights a lantern.', 'state_updates': {}})

        with patch('engine.ollama_chat', transport), patch('engine.time.monotonic', side_effect=[100, 100, 170]):
            result = engine.play_turn(self.db, self.cid, 'I wait.', chat=engine.ollama_chat)
        self.assertEqual([timeout for _, timeout in calls], [70, 25])
        self.assertIn('A sentry lights a lantern.', result['narration'])
        self.assertNotIn('PRIVATE_MALFORMED_DRAFT', json.dumps(calls[1][0]))
        self.assertEqual([m['role'] for m in result['messages']], ['player', 'gm'])

    def test_exhausted_retry_budget_preserves_messages_state_and_feedback(self):
        engine.play_turn(self.db, self.cid, 'I wait.', chat=lambda *_: json.dumps({
            'narration': 'A sentry watches the river.',
            'state_updates': {'location': 'Dock', 'inventory_add': ['river chart'], 'journal_entry': 'The sentry watches the river.'}}))
        target = engine.get_messages(self.db, self.cid)[-1]['id']
        before = list(self.db.iterdump())
        calls = []

        def transport(messages, model, *, timeout):
            calls.append(timeout)
            return 'PRIVATE_MALFORMED_DRAFT'

        with patch('engine.ollama_chat', transport), patch('engine.time.monotonic', side_effect=[100, 100, 196]):
            with self.assertRaisesRegex(RuntimeError, '95-second turn budget.*Nothing was saved'):
                engine.retry_message(self.db, self.cid, target, feedback='Make the scene livelier.', chat=engine.ollama_chat)
        self.assertEqual(calls, [70])
        self.assertEqual(list(self.db.iterdump()), before)

    def test_rejected_player_agency_draft_is_absent_from_corrective_context(self):
        calls = []

        def transport(messages, model, *, timeout):
            calls.append(json.loads(json.dumps(messages)))
            if len(calls) == 1:
                return json.dumps({'narration': 'You raise your hand. PRIVATE_REJECTED_PROSE',
                                   'state_updates': {'journal_entry': 'PRIVATE_REJECTED_STATE'}})
            return json.dumps({'narration': 'The sentry asks for a name.', 'state_updates': {}})

        with patch('engine.ollama_chat', transport), patch('engine.time.monotonic', side_effect=[100, 100, 101]):
            result = engine.play_turn(self.db, self.cid, 'I wait.', chat=engine.ollama_chat)
        self.assertEqual(len(calls), 2)
        self.assertNotIn('PRIVATE_REJECTED_', json.dumps(calls[1]))
        self.assertFalse(any(m['role'] == 'assistant' for m in calls[1]))
        self.assertIn('REWRITE THIS TURN', calls[1][-1]['content'])
        self.assertIn('I wait.', calls[1][-1]['content'])
        self.assertIn('The sentry asks for a name.', result['narration'])
        self.assertEqual(result['state']['journal'], [])

    def test_custom_two_argument_chat_adapter_remains_supported(self):
        calls = []

        def custom_chat(messages, model):
            calls.append(model)
            return json.dumps({'narration': 'A bell rings across the river.', 'state_updates': {}})

        engine.play_turn(self.db, self.cid, 'I listen.', chat=custom_chat)
        self.assertEqual(calls, ['qwen3:8b'])


if __name__ == '__main__':
    unittest.main()

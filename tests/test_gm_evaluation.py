"""Offline checks for synthetic, local-only model comparison and its CLI."""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine
import server


def accepted(_messages, _model):
    return json.dumps({'narration': 'Mara checks the seal. "I saw the boat arrive," the sentry says.',
                       'state_updates': {}})


class GMEvaluationTests(unittest.TestCase):
    def test_cases_cover_agency_continuity_lore_spells_and_retry(self):
        cases = engine.gm_evaluation_cases()
        self.assertEqual(len(cases), 10)
        self.assertEqual(len({c['id'] for c in cases}), len(cases))
        for name in ('agency_observation', 'agency_authorized_smile', 'authorized_dialogue',
                     'npc_first_person', 'spell_limits', 'hogwarts_opening',
                     'hogwarts_continuation', 'creator_canon_conflict', 'scene_progression', 'retry_preservation'):
            self.assertIn(name, {c['id'] for c in cases})
        cases[0]['review'].append('local mutation')
        self.assertNotIn('local mutation', engine.gm_evaluation_cases()[0]['review'])

    def test_offline_runner_uses_only_disposable_databases_and_keeps_user_files(self):
        with tempfile.TemporaryDirectory() as directory:
            personal = Path(directory) / 'private-data'
            personal.mkdir()
            (personal / 'storyforge.db').write_bytes(b'PRIVATE SAVED CAMPAIGN')
            (personal / 'portrait.png').write_bytes(b'PRIVATE ARTWORK')
            (personal / 'settings.json').write_text('{"model":"personal-model"}')
            before = {p.name: p.read_bytes() for p in personal.iterdir()}
            original = engine.open_db
            paths = []
            def disposable_only(path):
                paths.append(Path(path))
                self.assertNotIn(personal, Path(path).parents)
                return original(path)
            with patch.dict(os.environ, {'STORYFORGE_DB': str(personal / 'storyforge.db')}), \
                 patch('engine.open_db', side_effect=disposable_only), \
                 patch('engine.urllib.request.urlopen') as network, \
                 patch('engine._gm_evaluation_model_metadata') as metadata, \
                 patch('server.bootstrap') as bootstrap, patch('server.updater.UpdateWatcher') as watcher:
                report = engine.evaluate_local_gm('offline-fixture:8b', chat=accepted)
            self.assertEqual(before, {p.name: p.read_bytes() for p in personal.iterdir()})
            self.assertEqual(len(paths), 10)
            self.assertTrue(all(not p.exists() for p in paths))
            network.assert_not_called()
            metadata.assert_not_called()
            bootstrap.assert_not_called()
            watcher.assert_not_called()
        self.assertEqual(report['summary']['completed'], 10)
        self.assertEqual(report['summary']['failed'], 0)
        self.assertEqual(report['execution'], 'offline_test_adapter')
        self.assertTrue(report['manual_review_required'])
        self.assertEqual(report['summary']['manual_review_pending'], 10)
        self.assertNotIn('PRIVATE', json.dumps(report))
        for result in report['results']:
            self.assertEqual(result['manual_review']['status'], 'pending')
            self.assertTrue(result['automatic_checks']['stored_state_matches_result'])
            self.assertIn('Mara checks', result['narration'])
            self.assertIn('Mara checks', result['attempts'][0]['response'])

    def test_guard_rejections_are_distinct_and_failed_turns_preserve_fixture(self):
        def unauthorized(_messages, _model):
            return json.dumps({'narration': 'You raise your hand.', 'state_updates': {}})
        report = engine.evaluate_local_gm('offline-fixture:8b', chat=unauthorized)
        self.assertEqual(report['summary']['guardrail_rejected'], 10)
        self.assertEqual(report['summary']['transport_error'], 0)
        self.assertEqual(report['summary']['not_run'], 0)
        self.assertEqual(report['summary']['failed'], 10)
        for result in report['results']:
            self.assertEqual(len(result['attempts']), 2)
            self.assertTrue(result['automatic_checks']['campaign_unchanged_on_failure'])
            self.assertIsNone(result['narration'])
            self.assertIn('You raise your hand.', result['attempts'][0]['response'])

    def test_malformed_output_is_reported_separately(self):
        report = engine.evaluate_local_gm('offline-fixture:8b', chat=lambda *_: 'This is not JSON')
        self.assertEqual(report['summary']['invalid_response'], 10)
        self.assertEqual(report['summary']['guardrail_rejected'], 0)
        self.assertEqual(report['summary']['transport_error'], 0)
        self.assertTrue(all(r['automatic_checks']['campaign_unchanged_on_failure'] for r in report['results']))

    def test_accepted_rewrites_keep_rejected_drafts_and_regeneration_counts(self):
        def corrected(messages, model):
            if 'REWRITE THIS TURN' in messages[-1]['content']:
                return accepted(messages, model)
            return json.dumps({'narration': 'You raise your hand.', 'state_updates': {}})
        report = engine.evaluate_local_gm('offline-fixture:8b', chat=corrected)
        self.assertEqual(report['summary']['completed'], 10)
        self.assertEqual(report['summary']['cases_with_regeneration'], 10)
        self.assertEqual(report['summary']['generation_requests'], 20)
        for result in report['results']:
            self.assertEqual(result['attempts'][0]['pipeline_outcome'], 'rejected_before_retry')
            self.assertEqual(result['attempts'][1]['pipeline_outcome'], 'accepted')
            self.assertIn('You raise your hand.', result['attempts'][0]['response'])

    def test_transport_failure_marks_remaining_cases_unrun_without_repeated_calls(self):
        calls = []
        def model_adapter(messages, model):
            calls.append(model)
            if model == 'missing:8b':
                raise RuntimeError('Ollama HTTP 404. Check that this model is installed.')
            return accepted(messages, model)
        report = engine.evaluate_local_gm(['missing:8b', 'installed:8b'], repeat=2, chat=model_adapter)
        self.assertEqual(calls.count('missing:8b'), 1)
        self.assertEqual(calls.count('installed:8b'), 20)
        self.assertEqual(report['summary']['total'], 40)
        self.assertEqual(report['summary']['attempted'], 21)
        self.assertEqual(report['summary']['completed'], 20)
        self.assertEqual(report['summary']['transport_error'], 1)
        self.assertEqual(report['summary']['failed'], 1)
        self.assertEqual(report['summary']['not_run'], 19)
        self.assertEqual(report['summary']['manual_review_pending'], 21)
        unrun = [r for r in report['results'] if r['status'] == 'not_run']
        self.assertTrue(all(r['attempts'] == [] for r in unrun))
        self.assertTrue(report['results'][0]['automatic_checks']['campaign_unchanged_on_failure'])

    def test_fixture_context_and_retry_failure_probe_use_real_turn_pipeline(self):
        report = engine.evaluate_local_gm('offline-fixture:8b', chat=accepted)
        by_id = {r['case_id']: r for r in report['results']}
        spell = json.dumps(by_id['spell_limits']['attempts'][0]['messages'])
        self.assertIn('Cannot pass through warded stone', spell)
        self.assertIn('Cannot carry an unwilling passenger', spell)
        self.assertIn('10 mana per successful use', spell)
        hall = by_id['hogwarts_continuation']
        self.assertEqual(hall['input']['state_before']['location'], 'Hogwarts Entrance Hall')
        self.assertIn('Sorting Ceremony has not begun', json.dumps(hall['attempts'][0]['messages']))
        self.assertIn('black iron key', json.dumps(by_id['creator_canon_conflict']['attempts'][0]['messages']))
        retry = by_id['retry_preservation']
        self.assertEqual(retry['input']['operation'], 'retry')
        self.assertTrue(retry['forced_retry_failure_check']['existing_campaign_preserved'])
        self.assertEqual(retry['forced_retry_failure_check']['status'], 'checked')
        self.assertIn('Do not speak', json.dumps(retry['attempts'][0]['messages']))

    def test_production_runner_uses_current_local_transport_and_captures_numeric_diagnostics(self):
        requests = []
        def local_reply(request, *, timeout):
            requests.append((request, timeout))
            return io.BytesIO(json.dumps({'message': {'content': accepted([], '')},
                'eval_count': 21, 'prompt_eval_count': 100, 'total_duration': 1_250_000_000}).encode())
        with patch('engine.urllib.request.urlopen', side_effect=local_reply), \
             patch('engine._gm_evaluation_model_metadata', return_value={'status': 'unavailable'}):
            report = engine.evaluate_local_gm('installed:8b')
        self.assertEqual(report['execution'], 'local_ollama')
        self.assertEqual(report['summary']['completed'], 10)
        self.assertEqual(len(requests), 10)
        for request, timeout in requests:
            self.assertEqual(request.full_url, 'http://127.0.0.1:11434/api/chat')
            body = json.loads(request.data)
            self.assertEqual(body['model'], 'installed:8b')
            self.assertFalse(body['stream'])
            self.assertLessEqual(timeout, 70)
            self.assertGreater(timeout, 0)
        diagnostic = report['results'][0]['attempts'][0]['diagnostics'][0]
        self.assertEqual(diagnostic['eval_count'], 21)
        self.assertEqual(diagnostic['total_ms'], 1250)

    def test_production_wrapper_retains_state_evidence_checks(self):
        raw = json.dumps({'narration': 'Mara examines the red seal.',
                          'state_updates': {'location': 'Unvisited Secret Cave'}})
        def unsupported_state(_request, *, timeout):
            return io.BytesIO(json.dumps({'message': {'content': raw}}).encode())
        with patch('engine.urllib.request.urlopen', side_effect=unsupported_state), \
             patch('engine._gm_evaluation_model_metadata', return_value={'status': 'unavailable'}):
            report = engine.evaluate_local_gm('installed:8b')
        self.assertEqual(report['summary']['guardrail_rejected'], 10)
        self.assertEqual(report['summary']['completed'], 0)
        self.assertTrue(all(r['automatic_checks']['campaign_unchanged_on_failure'] for r in report['results']))

    def test_invalid_arguments_do_not_open_a_database_or_contact_a_model(self):
        invalid = [([], 1), (['x'] * 6, 1), ('', 1), ('bad\nmodel', 1),
                   ('valid:8b', 0), ('valid:8b', 6), ('valid:8b', True), ('valid:8b', 1.5)]
        with patch('engine.open_db') as database, patch('engine.urllib.request.urlopen') as network:
            for models, repeat in invalid:
                with self.subTest(models=models, repeat=repeat), self.assertRaises(ValueError):
                    engine.evaluate_local_gm(models, repeat=repeat)
            database.assert_not_called()
            network.assert_not_called()


class GMEvaluationMetadataTests(unittest.TestCase):
    def test_only_selected_model_metadata_is_retained_and_redirects_are_blocked(self):
        documents = {
            'version': {'version': '0.13.0-rc1', 'private': 'PRIVATE_SERVER_DATA'},
            'tags': {'models': [
                {'name': 'PRIVATE_OTHER_MODEL', 'digest': 'b' * 64},
                {'name': ['malformed', 'entry'], 'model': {}},
                {'name': 'qwen3:8b', 'digest': 'a' * 64,
                 'details': {'quantization_level': 'Q4_K_M', 'parameter_size': '8.2B', 'private': 'PRIVATE_DETAILS'}}]},
            'show': {'template': 'PRIVATE_MODEL_TEMPLATE', 'system': 'PRIVATE_SYSTEM_PROMPT',
                     'license': 'PRIVATE_LICENSE', 'modelfile': 'PRIVATE_BLOB_PATH',
                     'model_info': {'general.architecture': 'qwen3', 'qwen3.context_length': 40960,
                                    'private_value': 'PRIVATE_INFO'},
                     'capabilities': ['completion', 'tools', 'thinking', 'PRIVATE_CAPABILITY'],
                     'details': {'quantization_level': 'Q4_K_M', 'parameter_size': '8.2B'}}}
        requests = []
        def metadata_reply(request, *, timeout):
            requests.append((request, timeout))
            return io.BytesIO(json.dumps(documents[request.full_url.rsplit('/', 1)[-1]]).encode())
        with patch('engine.urllib.request.build_opener') as build:
            build.return_value.open.side_effect = metadata_reply
            metadata = engine._gm_evaluation_model_metadata('qwen3:8b', 'http://localhost:11434')
        self.assertEqual(metadata['status'], 'available')
        self.assertEqual(metadata['ollama_version'], '0.13.0-rc1')
        self.assertEqual(metadata['digest'], 'a' * 64)
        self.assertEqual(metadata['quantization'], 'Q4_K_M')
        self.assertEqual(metadata['parameter_size'], '8.2B')
        self.assertEqual(metadata['declared_context_length'], 40960)
        self.assertEqual(metadata['capabilities'], ['completion', 'tools', 'thinking'])
        self.assertTrue(metadata['supports_thinking'])
        self.assertNotIn('PRIVATE', json.dumps(metadata))
        self.assertEqual(len(requests), 3)
        self.assertTrue(all(timeout == 3 for _request, timeout in requests))
        self.assertEqual([r.get_method() for r, _ in requests], ['GET', 'GET', 'POST'])
        self.assertEqual(json.loads(requests[2][0].data), {'model': 'qwen3:8b', 'verbose': False})
        redirect_handler = build.call_args.args[0]
        self.assertIsNone(redirect_handler.redirect_request(requests[0][0], None, 302, 'Redirect', {}, 'https://external.example/private'))

    def test_metadata_failures_do_not_suppress_live_case_requests(self):
        metadata_calls = []
        def unsupported(request, *, timeout):
            metadata_calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 404, 'PRIVATE_ERROR', {}, io.BytesIO(b'PRIVATE_BODY'))
        def chat_reply(_request, *, timeout):
            return io.BytesIO(json.dumps({'message': {'content': accepted([], '')}}).encode())
        with patch('engine.urllib.request.build_opener') as build, \
             patch('engine.urllib.request.urlopen', side_effect=chat_reply) as actual_chat:
            build.return_value.open.side_effect = unsupported
            report = engine.evaluate_local_gm('installed:8b')
        self.assertEqual(len(metadata_calls), 3)
        self.assertEqual(actual_chat.call_count, 10)
        self.assertEqual(report['summary']['completed'], 10)
        self.assertEqual(report['model_metadata']['installed:8b']['status'], 'unavailable')
        self.assertNotIn('PRIVATE', json.dumps(report))

    def test_nonlocal_or_decorated_metadata_hosts_never_create_an_opener(self):
        hosts = ('https://localhost:11434', 'http://external.example:11434',
                 'http://localhost:11434@external.example', 'http://user:secret@localhost:11434',
                 'http://localhost:11434/private', 'http://localhost:11434?secret=x',
                 'http://localhost:11434#private', 'http://localhost:bad',
                 'http://localhost:70000', 'http://localhost:0', 'http://local\nhost:11434')
        with patch('engine.urllib.request.build_opener') as opener:
            for host in hosts:
                with self.subTest(host=host):
                    self.assertEqual(engine._gm_evaluation_model_metadata('qwen3:8b', host)['status'], 'unavailable')
            opener.assert_not_called()

    def test_metadata_bodies_are_bounded_and_invalid_fields_are_ignored(self):
        bodies = [io.BytesIO(b'x' * 70000), io.BytesIO(b'[]'),
                  io.BytesIO(json.dumps({'details': {'quantization_level': ['bad'], 'parameter_size': 'PRIVATE_SIZE'},
                    'model_info': {'general.architecture': 'qwen3', 'qwen3.context_length': True},
                    'capabilities': 'PRIVATE_CAPABILITIES'}).encode())]
        reads = []
        class BoundedResponse:
            def __init__(self, body):
                self.body = body
            def __enter__(self):
                return self
            def __exit__(self, *_):
                self.body.close()
            def read(self, amount):
                reads.append(amount)
                return self.body.read(amount)
        with patch('engine.urllib.request.build_opener') as build:
            build.return_value.open.side_effect = [BoundedResponse(body) for body in bodies]
            metadata = engine._gm_evaluation_model_metadata('installed:8b')
        self.assertEqual(reads, [65537, 65537, 65537])
        self.assertEqual(metadata['status'], 'unavailable')
        self.assertNotIn('PRIVATE', json.dumps(metadata))

    def test_untagged_model_uses_only_matching_latest_digest_when_show_unavailable(self):
        documents = [b'{"version":"0.12.0"}',
            json.dumps({'models': [{'name': 'other:latest', 'digest': 'b' * 64},
                                  {'name': 'example:latest', 'digest': 'a' * 64}]}).encode(), b'not JSON']
        with patch('engine.urllib.request.build_opener') as build:
            build.return_value.open.side_effect = [io.BytesIO(body) for body in documents]
            metadata = engine._gm_evaluation_model_metadata('example')
        self.assertEqual(metadata['status'], 'partial')
        self.assertEqual(metadata['digest'], 'a' * 64)
        self.assertNotIn('capabilities', metadata)


class GMEvaluationCLITests(unittest.TestCase):
    def test_plain_launch_still_calls_existing_run(self):
        with patch('server.run') as run, patch('engine.evaluate_local_gm') as evaluate:
            self.assertEqual(server.main([]), 0)
        run.assert_called_once_with()
        evaluate.assert_not_called()

    def test_existing_report_is_preserved_before_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'existing.json'
            report.write_text('private-existing-data')
            with patch('engine.evaluate_local_gm') as evaluate, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    server.main(['--evaluate-model', 'installed:8b', '--report', str(report)])
            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(report.read_text(), 'private-existing-data')
            evaluate.assert_not_called()

    def test_evaluation_cli_saves_report_without_starting_app_and_returns_failure_status(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'reports' / 'model-check.json'
            report = {'schema': 'storyforge.local-gm-evaluation', 'schema_version': 1,
                      'manual_review_required': True, 'summary': {'completed': 0, 'failed': 1, 'not_run': 9}}
            with patch('engine.evaluate_local_gm', return_value=report) as evaluate, \
                 patch('server.run') as run, patch('server.bootstrap') as bootstrap, \
                 patch('server.updater.UpdateWatcher') as watcher, redirect_stdout(io.StringIO()):
                status = server.main(['--evaluate-model', 'qwen3:8b', '--evaluate-model', 'alternative:8b',
                                      '--repeat', '2', '--report', str(destination)])
            self.assertEqual(status, 1)
            self.assertEqual(json.loads(destination.read_text()), report)
            self.assertEqual(evaluate.call_args.args[0], ['qwen3:8b', 'alternative:8b'])
            self.assertEqual(evaluate.call_args.kwargs['repeat'], 2)
            run.assert_not_called()
            bootstrap.assert_not_called()
            watcher.assert_not_called()

    def test_cli_rejects_invalid_and_irrelevant_options(self):
        for args in (['--repeat', '2'], ['--report', 'output.json'],
                     ['--evaluate-model', 'x', '--repeat', '0'],
                     ['--evaluate-model', 'x', '--report', 'output.txt']):
            with self.subTest(args=args), patch('server.run') as run, \
                 patch('engine.evaluate_local_gm') as evaluate, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    server.main(args)
                self.assertEqual(raised.exception.code, 2)
                run.assert_not_called()
                evaluate.assert_not_called()


if __name__ == '__main__':
    unittest.main()

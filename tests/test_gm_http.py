"""Exercise the real HTTP/SQLite/Ollama adapter with a local scripted model.

This verifies protocol and transaction boundaries, not live model intelligence.
"""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine
import server


def output(text, **state):
    return json.dumps({'narration': text, 'state_updates': state})


class ScriptedOllama(BaseHTTPRequestHandler):
    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append(data)
        result = {'message': {'content': self.server.replies.pop(0)},
                  'eval_count': 30, 'eval_duration': 1000000}
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class GameMasterHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(self.temp) / 'storyforge.db'
        self.enterContext(patch.object(server, 'DB_PATH', self.path))
        with closing(engine.open_db(self.path)) as con:
            world = engine.make_world(con, {'title': 'River Gate', 'description': 'A sentry keeps watch.'})
            self.cid = engine.new_campaign(con, {'world_id': world['id'], 'pc_name': 'Xeminas'})['id']
        self.model = self.start_server(ScriptedOllama)
        self.model.requests = []
        self.model.replies = []
        self.enterContext(patch.dict(os.environ, {'OLLAMA_URL': f'http://127.0.0.1:{self.model.server_port}'}))
        self.app = self.start_server(server.Handler)
        self.app.release_watcher = MagicMock()
        self.base = f'http://127.0.0.1:{self.app.server_port}'

    def start_server(self, handler):
        http = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=lambda: http.serve_forever(poll_interval=0.02), daemon=True)
        thread.start()
        def cleanup():
            http.shutdown()
            http.server_close()
            thread.join(2)
        self.addCleanup(cleanup)
        return http

    def post(self, suffix, payload, expected=200):
        request = urllib.request.Request(self.base + '/api/campaigns/' + self.cid + suffix,
                                         data=json.dumps(payload).encode(),
                                         headers={'Content-Type': 'application/json'})
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            result = json.load(response)
            self.assertEqual(response.status, expected, result)
            return result

    def dump(self):
        with closing(engine.open_db(self.path)) as con:
            return '\n'.join(con.iterdump())

    def test_rejected_draft_is_rewritten_through_actual_model_protocol(self):
        bad = 'Xeminas believes the stranger is trustworthy.'
        self.model.replies = [
            output(bad, location='Throne Room'),
            output('The sentry calls for the gatekeeper.', location='River Gate'),
        ]
        result = self.post('/turn', {'action': 'I watch the sentry.', 'model': 'qwen3:8b'})
        self.assertEqual(len(self.model.requests), 2)
        self.assertEqual(result['state']['location'], 'River Gate')
        self.assertEqual([m['role'] for m in result['messages']], ['player', 'gm'])
        self.assertTrue(result['messages'][-1]['has_checkpoint'])
        sent = self.model.requests[-1]
        self.assertEqual(sent['format'], 'json')
        self.assertFalse(sent['think'])
        self.assertNotIn(bad, json.dumps(sent['messages']))

    def test_invalid_real_model_responses_leave_database_identical(self):
        self.model.replies = [output('The sentry keeps watch.', location='Xeminas believes the sentry.')]*2
        before = self.dump()
        result = self.post('/turn', {'action': 'I watch.'}, expected=400)
        self.assertIn('Nothing was saved', result['error'])
        self.assertEqual(self.dump(), before)
        self.assertEqual(len(self.model.requests), 2)

    def test_retry_later_turn_uses_prior_history_without_crashing(self):
        self.model.replies = [output('The sentry calls for a lantern.', inventory_add=['gate token'])]
        self.post('/turn', {'action': 'I listen.'})
        self.model.replies = [output('A gatekeeper opens the shutter.', journal_entry='The shutter opened.')]
        second = self.post('/turn', {'action': 'I wait.'})
        target = second['messages'][-1]['id']
        self.model.replies = [output('The gatekeeper asks the sentry for a lantern.')]
        result = self.post(f'/messages/{target}/retry', {'feedback': 'Advance the conversation.'})
        self.assertEqual(len(result['messages']), 4)
        self.assertEqual(result['state']['inventory'], ['gate token'])
        self.assertEqual(result['state']['journal'], [])
        self.assertTrue(any(m['role'] == 'assistant' and 'sentry calls' in m['content']
                            for m in self.model.requests[-1]['messages']))


if __name__ == '__main__':
    unittest.main()

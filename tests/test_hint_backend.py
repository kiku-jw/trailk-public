"""Actual local routes with a fake audio session and fake text worker."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

SRC = Path(__file__).parents[1] / 'src'
sys.path.insert(0, str(SRC))
from text_provider import TextConsent, MODEL, Ledger


class HintBackendTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        with patch.dict(os.environ, CALM_DATA_ROOT=self.directory.name,
                        CALM_KEYCHAIN_BRIDGE='/nonexistent-offline-bridge', CALM_VERIFY_OFFLINE='0'):
            spec = importlib.util.spec_from_file_location('hint_backend_under_test', SRC / 'backend_server.py')
            self.service = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.service)
        owner = self
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0
        class Audio:
            lock = threading.RLock()
            current = 'synthetic-session'
            running = True
            def stop(self):
                self.running = False
        class Adapter:
            consent = None
            busy = threading.Lock()
            ledger = Ledger(Path(owner.directory.name) / 'synthetic-budget.json')
            def generate(self, *args, control=None, **kwargs):
                owner.calls += 1
                owner.started.set()
                while not owner.release.wait(.01):
                    control.check()
                control.check()
                return {'options': [], 'metadata': {}}
        self.service.audio = Audio()
        self.service.adapter = Adapter()
        self.service.text_consent = lambda: TextConsent('openai', MODEL, .1, True) if self.service.audio.running else None
        self.server = self.service.Server(('127.0.0.1', 0), self.service.Handler)
        self.service.HOST = '127.0.0.1:' + str(self.server.server_port)
        self.base = 'http://' + self.service.HOST
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.release.set()
        self.service.hints.close()
        self.service.hints.worker.join(1)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(1)
        self.directory.cleanup()

    def call(self, path, body, token=None, origin=None):
        headers = {'Content-Type': 'application/json', 'X-Pilot-Token': self.service.TOKEN if token is None else token}
        if origin:
            headers['Origin'] = origin
        request = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.load(error)

    def body(self, generation=1):
        return {'mode': 'reply', 'hint_generation': generation, 'hint_session': 'synthetic-session'}

    def start_hint(self):
        results = []
        thread = threading.Thread(target=lambda: results.append(self.call('/api/text', self.body())))
        thread.start()
        self.assertTrue(self.started.wait(1))
        return thread, results

    def test_authenticated_cancel_interrupts_exact_session_and_prevents_late_success(self):
        thread, results = self.start_hint()
        self.assertEqual(self.call('/api/text/cancel', {**self.body(), 'hint_session': 'older-session'})[0], 200)
        self.assertFalse(self.service.hints.active.control.cancelled.is_set())
        self.assertEqual(self.call('/api/text/cancel', self.body())[0], 200)
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0][0], 400)
        self.assertEqual(self.calls, 1)

    def test_stop_and_spontaneous_audio_end_revoke_results(self):
        thread, results = self.start_hint()
        self.assertEqual(self.call('/api/stop', {})[0], 200)
        thread.join(1)
        self.assertEqual(results[0][0], 400)

    def test_spontaneous_end_is_checked_after_worker_completion(self):
        thread, results = self.start_hint()
        self.service.audio.running = False
        self.release.set()
        thread.join(1)
        self.assertEqual(results[0][0], 400)

    def test_wrong_session_token_origin_and_early_cancel_never_start_text(self):
        self.assertEqual(self.call('/api/text', self.body(), token='wrong')[0], 403)
        self.assertEqual(self.call('/api/text', self.body(), origin='https://example.invalid')[0], 403)
        self.assertEqual(self.call('/api/text', {**self.body(), 'hint_session': 'wrong-session'})[0], 400)
        self.call('/api/text/cancel', self.body())
        self.assertEqual(self.call('/api/text', self.body())[0], 400)
        self.assertEqual(self.calls, 0)

    def test_changed_profile_is_rejected_before_queued_worker_uses_it(self):
        with patch.object(self.service.personal_context, 'read', side_effect=[
                {'text': 'Old synthetic profile', 'revision': 'old'},
                {'text': '', 'revision': 'new'}]):
            self.assertEqual(self.call('/api/text', self.body())[0], 400)
        self.assertEqual(self.calls, 0)

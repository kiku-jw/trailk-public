"""Synthetic scheduling tests; no audio, credentials, or provider calls."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from hint_queue import HintQueue
from request_control import RequestControl, RequestCancelled
from text_provider import TextAdapter, TextConsent, Ledger, MODEL


class HintQueueTests(unittest.TestCase):
    def setUp(self):
        self.queue = HintQueue()
        self.release = threading.Event()

    def tearDown(self):
        self.release.set()
        self.queue.close()
        self.queue.worker.join(1)
        self.assertFalse(self.queue.worker.is_alive())

    def test_latest_pending_replaces_obsolete_without_running_it(self):
        started = threading.Event()
        calls = []
        def blocked(control):
            started.set()
            self.release.wait(2)
            control.check()
        first = self.queue.submit(1, blocked)
        self.assertTrue(started.wait(1))
        second = self.queue.submit(2, lambda control: calls.append(2))
        third = self.queue.submit(3, lambda control: calls.append(3) or 'latest')
        self.assertTrue(self.queue.snapshot()['active'])
        self.assertTrue(self.queue.snapshot()['pending'])
        for old in (first, second):
            with self.assertRaises(RequestCancelled):
                old.result()
        self.release.set()
        self.assertEqual(third.result(), 'latest')
        self.assertEqual(calls, [3])

    def test_late_cancel_cannot_cancel_replacement_and_early_cancel_is_remembered(self):
        self.queue.cancel(1)  # The cancel HTTP request may beat submission.
        with self.assertRaises(RequestCancelled):
            self.queue.submit(1, lambda control: self.fail('Cancelled job ran'))
        started = threading.Event()
        def work(control):
            started.set()
            self.release.wait(2)
            control.check()
            return 2
        job = self.queue.submit(2, work)
        self.assertTrue(started.wait(1))
        self.queue.cancel(1)
        self.assertFalse(job.control.cancelled.is_set())
        self.release.set()
        self.assertEqual(job.result(), 2)

    def test_duplicates_and_invalid_generations_fail_closed(self):
        self.assertEqual(self.queue.submit(2, lambda control: 'ok').result(), 'ok')
        for generation in (1, 2):
            with self.assertRaises(RequestCancelled):
                self.queue.submit(generation, lambda control: self.fail('Duplicate ran'))
        for generation in (True, 0, -1, 1.5, '3', 2**53):
            with self.assertRaises(ValueError):
                self.queue.submit(generation, lambda control: None)

    def test_metrics_are_bounded_numeric_metadata_and_reset_revokes_work(self):
        for generation in range(1, 141):
            self.queue.submit(generation, lambda control: 'SYNTHETIC-TEXT').result()
        summary = self.queue.snapshot()
        self.assertEqual(summary['request_ms']['samples'], 128)
        self.assertLessEqual(summary['request_ms']['p50'], summary['request_ms']['p95'])
        self.assertNotIn('SYNTHETIC-TEXT', json.dumps(summary))
        self.queue.reset()
        self.assertEqual(self.queue.submit(1, lambda control: 'new session').result(), 'new session')
        self.queue.close()
        with self.assertRaises(RequestCancelled):
            self.queue.submit(2, lambda control: None)

    def test_cancel_before_dispatch_reads_no_key_and_reserves_nothing(self):
        class NoStore:
            def load_for_application(self):
                raise AssertionError('Credential read')
        control = RequestControl()
        control.cancel()
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / 'budget.json')
            adapter = TextAdapter(NoStore(), ledger, TextConsent('openai', MODEL, .1))
            with self.assertRaises(RequestCancelled):
                adapter.generate('Повторите, пожалуйста.', control=control)
            self.assertFalse(ledger.path.exists())

    def test_cancel_after_dispatch_keeps_reservation_without_retry_or_display(self):
        calls = []
        control = RequestControl()
        class FakeStore:
            def load_for_application(self):
                return 'DUMMY-NOT-A-CREDENTIAL'
        def transport(*args):
            calls.append(1)
            control.cancel()
            return {'status': 'completed'}
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / 'budget.json')
            adapter = TextAdapter(FakeStore(), ledger, TextConsent('openai', MODEL, .1), transport)
            with self.assertRaises(RequestCancelled):
                adapter.generate('Повторите, пожалуйста.', control=control)
            self.assertEqual(calls, [1])
            self.assertEqual(json.loads(ledger.path.read_text())['reserved_usd'], .05)
            self.assertFalse(adapter.busy.locked())

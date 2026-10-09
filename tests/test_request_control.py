"""Loopback fake HTTP tests. No external access or real credentials."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from request_control import request_json, RequestControl, RequestCancelled, RequestDeadline, HTTPStatusFailure


class RequestControlTests(unittest.TestCase):
    def setUp(self):
        self.release = threading.Event()
        self.received = threading.Event()
        self.calls = []
        owner = self
        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *args):
                pass
            def do_POST(self):
                owner.calls.append(self.path)
                self.rfile.read(int(self.headers['Content-Length']))
                owner.received.set()
                status = int(self.path[1:]) if self.path[1:].isdigit() else 200
                if self.path == '/headers':
                    owner.release.wait(2)
                body = b'{"ok":true}' if self.path == '/ok' else b'PRIVATE-SYNTHETIC-ERROR' if status != 200 else b'x' * 65537
                if self.path in ('/body', '/drip'):
                    body = b' ' * 1000
                try:
                    self.send_response(status)
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    if self.path == '/body':
                        self.wfile.write(body[:1]); self.wfile.flush()
                        owner.release.wait(2)
                        self.wfile.write(body[1:])
                    elif self.path == '/drip':
                        for byte in body:
                            self.wfile.write(bytes([byte])); self.wfile.flush()
                            if owner.release.wait(.01):
                                break
                    else:
                        self.wfile.write(body)
                except OSError:
                    pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(1)

    def call(self, path, control=None):
        return request_json(self.base + path, b'{}', 'DUMMY-NOT-A-CREDENTIAL', control)

    def test_complete_json_and_non_success_never_redirect_or_retry(self):
        self.assertEqual(self.call('/ok'), {'ok': True})
        for status in (302, 429, 500):
            with self.assertRaises(HTTPStatusFailure) as error:
                self.call('/' + str(status))
            self.assertNotIn('PRIVATE-SYNTHETIC-ERROR', str(error.exception))
        self.assertEqual(self.calls, ['/ok', '/302', '/429', '/500'])

    def test_response_size_is_bounded(self):
        with self.assertRaises(ValueError) as error:
            self.call('/large')
        self.assertNotIn('xxxx', str(error.exception))
        self.assertEqual(len(self.calls), 1)

    def test_total_deadline_stops_header_and_dripping_body(self):
        for path in ('/headers', '/drip'):
            with self.subTest(path=path):
                started = time.monotonic()
                with self.assertRaises(RequestDeadline):
                    self.call(path, RequestControl(overall_seconds=.18, idle_seconds=.5))
                self.assertLess(time.monotonic() - started, 1)

    def test_idle_body_timeout_is_bounded_without_retry(self):
        started = time.monotonic()
        with self.assertRaises(ValueError):
            self.call('/body', RequestControl(overall_seconds=2, idle_seconds=.1))
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(self.calls, ['/body'])

    def test_cancel_wakes_blocked_header_or_detached_connection_close_body(self):
        for path in ('/headers', '/body'):
            with self.subTest(path=path):
                self.received.clear()
                control = RequestControl(overall_seconds=2, idle_seconds=1.5)
                errors = []
                def work():
                    try:
                        self.call(path, control)
                    except Exception as error:
                        errors.append(error)
                thread = threading.Thread(target=work)
                thread.start()
                self.assertTrue(self.received.wait(1))
                control.cancel()
                thread.join(.8)
                self.assertFalse(thread.is_alive())
                self.assertIsInstance(errors[0], RequestCancelled)

    def test_pre_cancel_and_unapproved_plain_http_do_not_connect(self):
        control = RequestControl(); control.cancel()
        with self.assertRaises(RequestCancelled):
            self.call('/ok', control)
        for url in ('http://example.com/v1', 'http://localhost/v1', self.base + '/v1#fragment', 'http://user:password@127.0.0.1/v1'):
            with self.assertRaises(ValueError):
                request_json(url, b'{}', 'DUMMY-NOT-A-CREDENTIAL')
        self.assertEqual(self.calls, [])

"""Bounded HTTP lifetime. Cancellation never retries or refunds a request."""
import http.client
import json
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit


class RequestCancelled(ValueError):
    def __init__(self):
        super().__init__('Подсказка отменена или заменена новой репликой. Повтора нет.')


class RequestDeadline(ValueError):
    def __init__(self):
        super().__init__('Истекло время ожидания подсказки. Повтора нет.')


class HTTPStatusFailure(ValueError):
    def __init__(self, status):
        super().__init__('Текстовый API вернул HTTP' + str(status) + '. Повтора нет.')


class RequestControl:
    def __init__(self, overall_seconds=30, idle_seconds=10, clock=time.monotonic):
        self.cancelled = threading.Event()
        self.clock = clock
        self.started = clock()
        self.deadline = self.started + overall_seconds
        self.idle_seconds = idle_seconds

    def cancel(self):
        self.cancelled.set()

    def check(self):
        if self.cancelled.is_set():
            raise RequestCancelled()
        if self.clock() >= self.deadline:
            raise RequestDeadline()


def request_json(url, body, key, control=None, connection_factory=None):
    control = control or RequestControl()
    control.check()
    parts = urlsplit(url)
    if parts.username or parts.password or parts.fragment:
        raise ValueError('Invalid provider URL')
    if parts.scheme == 'https':
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
        factory = connection_factory or http.client.HTTPSConnection
        connection = factory(parts.hostname, parts.port or 443,
                             timeout=control.idle_seconds, context=context)
    elif parts.scheme == 'http' and parts.hostname == '127.0.0.1':
        factory = connection_factory or http.client.HTTPConnection
        connection = factory(parts.hostname, parts.port or 80, timeout=control.idle_seconds)
    else:
        raise ValueError('Invalid provider URL')

    # Connect explicitly so cancellation during DNS/TCP/TLS is checked before HTTP.
    # If the watcher closes the socket, HTTPConnection.send must not reconnect it.
    connection.auto_open = 0
    finished = threading.Event()
    response = None
    active_socket = [None]

    def interrupt():
        while not finished.wait(.025):
            try:
                control.check()
            except (RequestCancelled, RequestDeadline):
                # shutdown wakes a blocked response/header read before closing it.
                sock = active_socket[0] or connection.sock
                if sock:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                connection.close()
                return

    watcher = threading.Thread(target=interrupt, daemon=True)
    watcher.start()
    try:
        path = parts.path or '/'
        if parts.query:
            path += '?' + parts.query
        control.check()
        connection.connect()
        active_socket[0] = connection.sock
        control.check()
        connection.request('POST', path, body=body,
                           headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
        control.check()
        response = connection.getresponse()
        control.check()
        if not 200 <= response.status < 300:
            raise HTTPStatusFailure(response.status)  # Never follow redirects/read error bodies.
        raw = bytearray()
        while True:
            control.check()
            chunk = response.read1(min(8192, 65537 - len(raw)))
            control.check()
            if not chunk:
                break
            raw.extend(chunk)
            if len(raw) > 65536:
                raise ValueError('Provider response exceeded size limit')
        return json.loads(raw)
    except (RequestCancelled, RequestDeadline, HTTPStatusFailure):
        raise
    except Exception:
        control.check()
        raise ValueError('Provider request failed; response and credentials omitted') from None
    finally:
        finished.set()
        if response:
            response.close()
        connection.close()
        watcher.join(timeout=.2)

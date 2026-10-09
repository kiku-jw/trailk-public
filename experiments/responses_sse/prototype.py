"""Disabled, isolated Responses SSE experiment. Not imported by the product.

Closed EN/RU/kind pairs are checked and staged in RAM. CURRENT CONTRACT requires
a successful full group and terminal response.completed before any publication.
No partial JSON, pair text, key or source context is persisted by this module.
"""
import codecs
import json
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
import reply_choices
import reply_context
import text_budget
from text_provider import MODEL, NoRedirect, TextError, mode_instructions, request_data, usage_metadata, validate_result

ENDPOINT = 'https://api.openai.com/v1/responses'
MAX_JSON_BYTES = 65536
MAX_STREAM_BYTES = 262144


def no_duplicates(items):
    out = {}
    for key, value in items:
        if key in out:
            raise TextError('duplicate_json_key')
        out[key] = value
    return out


DECODER = json.JSONDecoder(object_pairs_hook=no_duplicates)


def decode_json(text):
    try:
        return DECODER.decode(text)
    except (ValueError, TypeError, RecursionError):
        raise TextError('invalid_json') from None


def utf8_size(text):
    try:
        return len(text.encode('utf-8'))
    except (UnicodeError, AttributeError):
        raise TextError('invalid_unicode') from None


class SSEDecoder:
    """Incremental UTF-8 + SSE framing, including CRLF and multiline data."""
    def __init__(self):
        self.utf8 = codecs.getincrementaldecoder('utf-8')('strict')
        self.line = ''
        self.line_bytes = 0
        self.data = []
        self.data_bytes = 0
        self.event_type = None
        self.total_bytes = 0
        self.pending_cr = False
        self.ended = False

    def _line(self):
        line, self.line = self.line, ''
        self.line_bytes = 0
        if not line:
            if not self.data:
                self.event_type = None
                return None
            text = '\n'.join(self.data)
            value = {'type': 'transport.done'} if text == '[DONE]' else decode_json(text)
            expected, self.data, self.event_type = self.event_type, [], None
            self.data_bytes = 0
            if not isinstance(value, dict) or not isinstance(value.get('type'), str):
                raise TextError('invalid_sse_event')
            if expected and expected != value['type']:
                raise TextError('sse_event_type_mismatch')
            return value
        if line.startswith(':'):
            return None
        field, _, value = line.partition(':')
        value = value[1:] if value.startswith(' ') else value
        if field == 'data':
            self.data.append(value)
            self.data_bytes += utf8_size(value) + 1
            if self.data_bytes > MAX_JSON_BYTES:
                raise TextError('sse_event_too_large')
        elif field == 'event':
            self.event_type = value
        return None

    def feed(self, chunk):
        if self.ended or not isinstance(chunk, bytes):
            raise TextError('invalid_sse_feed')
        self.total_bytes += len(chunk)
        if self.total_bytes > MAX_STREAM_BYTES:
            raise TextError('sse_stream_too_large')
        try:
            decoded = self.utf8.decode(chunk)
        except UnicodeError:
            raise TextError('invalid_sse_utf8') from None
        events = []
        for char in decoded:
            if self.pending_cr:
                self.pending_cr = False
                if char == '\n':
                    continue
            if char in '\r\n':
                event = self._line()
                if event is not None:
                    events.append(event)
                self.pending_cr = char == '\r'
            else:
                self.line += char
                self.line_bytes += utf8_size(char)
                if self.line_bytes > MAX_JSON_BYTES:
                    raise TextError('sse_line_too_large')
        return events

    def finish(self):
        self.ended = True
        try:
            self.utf8.decode(b'', final=True)
        except UnicodeError:
            raise TextError('truncated_sse_utf8') from None
        if self.line or self.data:
            raise TextError('truncated_sse_frame')


class PairStager:
    """Decode closed objects, including braces inside escaped JSON strings.

    Staging is diagnostic RAM only. A later invalid root/item or refusal can
    invalidate the whole response, so these pairs are never public options.
    """
    def __init__(self, conversation, clock=time.monotonic):
        self.conversation = conversation
        self.clock = clock
        self.raw = ''
        self.staged = []
        self.seen = 0
        self.trace = []

    def feed(self, delta):
        if not isinstance(delta, str):
            raise TextError('invalid_text_delta')
        self.raw += delta
        if utf8_size(self.raw) > MAX_JSON_BYTES:
            raise TextError('output_json_too_large')
        # Parse from the root each time rather than regex matching braces.
        pos = 0
        def spaces():
            nonlocal pos
            while pos < len(self.raw) and self.raw[pos].isspace():
                pos += 1
        def literal(char):
            nonlocal pos
            spaces()
            if pos == len(self.raw):
                return False
            if self.raw[pos] != char:
                raise TextError('unexpected_json_structure')
            pos += 1
            return True
        if not literal('{'):
            return
        spaces()
        try:
            name, pos = DECODER.raw_decode(self.raw, pos)
        except json.JSONDecodeError:
            return
        if name != 'options':
            raise TextError('unexpected_json_root_key')
        if not literal(':') or not literal('['):
            return
        count = 0
        while True:
            spaces()
            if pos >= len(self.raw) or self.raw[pos] == ']':
                return
            try:
                pair, end = DECODER.raw_decode(self.raw, pos)
            except json.JSONDecodeError:
                return  # No closed object yet; never repair incomplete JSON.
            count += 1
            if count > 3:
                raise TextError('too_many_options')
            if count > self.seen:
                self.seen = count
                # Check the full pair with EXACT current production guards.
                try:
                    checked = validate_result(json.dumps({'options': [pair]}, ensure_ascii=False),
                                              'reply', True, self.conversation)
                except TextError:
                    self.trace.append({'stage': 'pair_rejected', 'at': self.clock(), 'index': count})
                else:
                    for option in checked['options']:
                        utf8_size(option['en']); utf8_size(option['ru'])
                    self.staged.append(checked['options'][0])
                    self.trace.append({'stage': 'closed_pair_locally_checked', 'at': self.clock(),
                                       'index': count, 'public': False})
            pos = end
            spaces()
            if pos >= len(self.raw) or self.raw[pos] == ']':
                return
            if self.raw[pos] != ',':
                raise TextError('invalid_array_delimiter')
            pos += 1

    def final(self):
        value = decode_json(self.raw)
        if not isinstance(value, dict) or set(value) != {'options'}:
            raise TextError('invalid_full_group_structure')
        result = validate_result(self.raw, 'reply', True, self.conversation)
        for pair in result['options']:
            utf8_size(pair['en']); utf8_size(pair['ru'])
        return result

    def discard(self):
        self.staged.clear()
        self.raw = ''


class StreamSession:
    """No publication until full success. Selection is always explicitly manual."""
    def __init__(self, conversation, selected_en='', clock=time.monotonic):
        self.conversation = reply_context.validate(conversation)
        self.revision = self.conversation['latest_interlocutor_utterance']['segment_revision']
        self.clock = clock
        self.parser = PairStager(self.conversation, clock)
        self.phase = 'waiting'
        self.response_id = None
        self.item_id = None
        self.sequence = -1
        self.text_done = False
        self.public_result = None
        self.selected_en = selected_en
        self.terminal_response = None
        self.transport_done = False
        self.trace = []

    def trace_stage(self, stage):
        self.trace.append({'stage': stage, 'at': self.clock()})

    def fail(self, reason):
        self.phase = 'rejected'
        self.public_result = None
        self.parser.discard()
        self.trace_stage(reason)
        raise TextError(reason)

    def cancel(self, reason='stopped'):
        self.phase = 'cancelled'
        self.public_result = None
        self.parser.discard()
        self.trace_stage(reason)

    def supersede(self, revision):
        if revision != self.revision:
            self.cancel('new_completed_segment')

    def accept(self, event):
        try:
            return self._accept(event)
        except Exception:
            self.phase = 'rejected'; self.public_result = None; self.parser.discard()
            raise TextError('stream_event_rejected') from None

    def _accept(self, event):
        if self.phase in ('cancelled', 'rejected'):
            return
        if event.get('type') == 'transport.done':
            if self.phase != 'completed' or self.transport_done:
                return self.fail('transport_done_is_not_response_success')
            self.transport_done = True
            return
        if self.phase == 'completed':
            return self.fail('event_after_terminal')
        seq = event.get('sequence_number')
        if not isinstance(seq, int) or isinstance(seq, bool) or seq <= self.sequence:
            return self.fail('invalid_event_sequence')
        self.sequence = seq
        kind = event['type']
        if kind in ('response.failed', 'response.incomplete', 'response.completed'):
            self.terminal_response = event.get('response')
        if kind in ('error', 'response.failed', 'response.incomplete') or kind.startswith('response.refusal.'):
            return self.fail('late_failure_or_refusal')
        if kind == 'response.created':
            r = event.get('response', {})
            if self.phase != 'waiting' or not isinstance(r.get('id'), str) or r.get('model') != MODEL:
                return self.fail('unexpected_response_identity')
            self.response_id = r['id']; self.phase = 'streaming'; self.trace_stage('response_created')
            return
        if self.phase != 'streaming':
            return self.fail('text_without_response_created')
        if kind in ('response.output_text.delta', 'response.output_text.done'):
            if event.get('output_index') != 0 or event.get('content_index') != 0 or not isinstance(event.get('item_id'), str):
                return self.fail('unsupported_multiple_output')
            if self.item_id is not None and self.item_id != event['item_id']:
                return self.fail('mixed_output_identity')
            self.item_id = event['item_id']
            if self.text_done:
                return self.fail('text_after_done')
            if kind.endswith('.delta'):
                self.parser.feed(event.get('delta'))
            else:
                if event.get('text') != self.parser.raw:
                    return self.fail('done_text_mismatch')
                self.parser.final(); self.text_done = True; self.trace_stage('whole_json_validated')
            return
        if kind == 'response.completed':
            r = event.get('response', {})
            if not self.text_done or r.get('id') != self.response_id or r.get('model') != MODEL or r.get('status') != 'completed' or r.get('error') or r.get('incomplete_details'):
                return self.fail('missing_successful_terminal')
            output = r.get('output', [])
            if len(output) != 1 or output[0].get('type') != 'message' or output[0].get('id') != self.item_id or output[0].get('status') != 'completed':
                return self.fail('invalid_terminal_output')
            parts = output[0].get('content', [])
            if len(parts) != 1 or parts[0].get('type') != 'output_text' or parts[0].get('text') != self.parser.raw:
                return self.fail('refusal_or_terminal_text_mismatch')
            self.public_result = self.parser.final()
            self.phase = 'completed'; self.trace_stage('first_publishable_pair_and_group')
            return
        # Explicit harmless lifecycle events; unknown/tool/audio outputs reject.
        if kind not in ('response.in_progress', 'response.output_item.added', 'response.content_part.added',
                        'response.content_part.done', 'response.output_item.done'):
            return self.fail('unsupported_stream_event')
        item = event.get('item')
        part = event.get('part')
        if isinstance(item, dict) and item.get('type') != 'message':
            return self.fail('unsupported_output_item')
        if isinstance(part, dict) and part.get('type') != 'output_text':
            return self.fail('unsupported_content_part')

    def end_of_stream(self):
        if self.phase not in ('completed', 'cancelled', 'rejected'):
            self.fail('disconnect_before_terminal')

    def select(self, index):
        if self.phase != 'completed' or self.public_result is None:
            raise TextError('no_publishable_manual_choice')
        self.selected_en = self.public_result['options'][index]['en']
        return self.selected_en


def stream_body(conversation):
    data = request_data('', conversation['latest_interlocutor_utterance']['text'], 'reply', conversation)
    provider_data = {**data, 'conversation': reply_context.for_provider(data['conversation']),
                     'reply_choice_contract': reply_choices.policy(data['conversation'])}
    item = {'type': 'object', 'properties': {'en': {'type': 'string'}, 'ru': {'type': 'string'},
            'kind': {'type': 'string', 'enum': list(reply_choices.KINDS)}},
            'required': ['en', 'ru', 'kind'], 'additionalProperties': False}
    schema = {'type': 'object', 'properties': {'options': {'type': 'array', 'items': item}},
              'required': ['options'], 'additionalProperties': False}
    return {'model': MODEL, 'instructions': mode_instructions('reply'),
            'input': json.dumps(provider_data, ensure_ascii=False), 'store': False, 'stream': True,
            'max_output_tokens': text_budget.MAX_OUTPUT_TOKENS, 'reasoning': {'effort': 'none'},
            'text': {'format': {'type': 'json_schema', 'name': 'spoken_translation', 'strict': True, 'schema': schema}}}


def post_sse(url, body, key, cancelled):
    """Same Responses endpoint only; no redirects, retry or credential discovery."""
    if url != ENDPOINT or body.get('model') != MODEL or body.get('stream') is not True:
        raise TextError('unexpected_stream_route')
    import certifi
    request = urllib.request.Request(url, data=text_budget.wire_bytes(body),
        headers={'Content-Type': 'application/json', 'Accept': 'text/event-stream', 'Authorization': 'Bearer '+key}, method='POST')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where())), NoRedirect())
    try:
        with opener.open(request, timeout=20) as response:
            if response.headers.get_content_type() != 'text/event-stream':
                raise TextError('unexpected_stream_content_type')
            deadline = time.monotonic()+20
            while not cancelled.is_set():
                if time.monotonic() > deadline:
                    raise TextError('stream_deadline')
                chunk = response.read1(4096)
                if not chunk:
                    return
                yield chunk
    except TextError:
        raise
    except Exception:
        raise TextError('sse_transport_failed_no_retry') from None


class DisabledPrototype:
    """Test injection can opt in. Production imports/flags/settings do not exist."""
    def __init__(self, adapter, enabled=False, transport=post_sse):
        self.adapter = adapter
        self.enabled = enabled
        self.transport = transport
        self.attempted = False

    def run(self, session, cancelled=None, on_usage=None):
        if not self.enabled:
            raise TextError('isolated_sse_prototype_disabled')
        if self.attempted:
            raise TextError('prototype_one_attempt_no_retry')
        consent = self.adapter.consent
        if consent is None or consent.provider != 'openai' or consent.model != MODEL or not consent.allow_selected_context or consent.reservation_policy != 'estimated_v1':
            raise TextError('prototype_requires_existing_exact_consent')
        cancelled = cancelled or threading.Event()
        if cancelled.is_set() or session.phase != 'waiting':
            raise TextError('cancelled_before_dispatch')
        if not self.adapter.busy.acquire(blocking=False):
            raise TextError('another_text_request_inflight')
        key = None; stream = None; decoder = SSEDecoder(); started = time.monotonic(); usage_reported = False
        try:
            self.attempted = True
            body = stream_body(session.conversation)
            reservation = self.adapter.reserve_request(consent, body)
            if cancelled.is_set() or session.phase != 'waiting':
                session.cancel(); return None
            key = self.adapter.store.load_for_application()  # Existing app IPC, never agent tooling.
            stream = self.transport(ENDPOINT, body, key, cancelled)
            for chunk in stream:
                if cancelled.is_set() or session.phase == 'cancelled':
                    session.cancel(); break
                for event in decoder.feed(chunk):
                    if cancelled.is_set() or session.phase == 'cancelled':
                        session.cancel(); break
                    # Account available terminal usage even if content is rejected.
                    r = event.get('response')
                    if event.get('type') in ('response.completed', 'response.failed', 'response.incomplete') and isinstance(r, dict) and not usage_reported:
                        metadata = usage_metadata(r, consent, started); metadata['reservation'] = reservation
                        if on_usage: on_usage(metadata)
                        usage_reported = True
                    if cancelled.is_set() or session.phase == 'cancelled':
                        session.cancel(); break
                    session.accept(event)
                if session.phase == 'cancelled': break
            if cancelled.is_set(): session.cancel()
            if session.phase != 'cancelled': decoder.finish()
            session.end_of_stream()
            return session.public_result
        except Exception:
            session.phase = 'rejected'; session.public_result = None; session.parser.discard()
            raise TextError('prototype_stream_rejected_no_retry') from None
        finally:
            if stream is not None and hasattr(stream, 'close'): stream.close()
            key = None
            self.adapter.busy.release()

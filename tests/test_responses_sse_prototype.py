"""Offline SSE experiment. No network/Keychain/capture; exact current guards."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/responses_sse'))
from prototype import (DisabledPrototype, StreamSession, PairStager, SSEDecoder, ENDPOINT,
                       MAX_JSON_BYTES, MAX_STREAM_BYTES, stream_body)
from text_provider import TextAdapter, TextConsent, Ledger, MODEL, TextError
import reply_context

CONVERSATION = reply_context.build('Вы меня слышите?')
OPTIONS = [
    {'en': 'Yes, I hear you clearly.', 'ru': 'Да, я вас хорошо слышу.', 'kind': 'positive'},
    {'en': 'The sound is breaking up.', 'ru': 'Звук прерывается.', 'kind': 'negative'},
    {'en': 'Could you repeat that?', 'ru': 'Можете повторить?', 'kind': 'clarify'},
]

def raw(options=OPTIONS, ascii=False):
    return json.dumps({'options': options}, ensure_ascii=ascii)

def created():
    return {'type': 'response.created', 'sequence_number': 0,
            'response': {'id': 'resp_PUBLIC_FIXTURE', 'model': MODEL, 'status': 'in_progress'}}

def output_event(kind, seq, **kwargs):
    return {'type': kind, 'sequence_number': seq, 'output_index': 0, 'content_index': 0,
            'item_id': 'msg_PUBLIC_FIXTURE', **kwargs}

def terminal(text, seq, status='completed'):
    return {'type': 'response.'+status, 'sequence_number': seq, 'response': {
        'id': 'resp_PUBLIC_FIXTURE', 'model': MODEL, 'status': status, 'error': None,
        'incomplete_details': None, 'usage': {'input_tokens': 100, 'output_tokens': 50},
        'output': [{'id': 'msg_PUBLIC_FIXTURE', 'type': 'message', 'status': 'completed',
                    'content': [{'type': 'output_text', 'text': text}]}]}}

def events(text=None, text_chunks=None):
    text = raw() if text is None else text
    chunks = [text] if text_chunks is None else text_chunks
    out = [created()]
    for i, part in enumerate(chunks, 1): out.append(output_event('response.output_text.delta', i, delta=part))
    out.append(output_event('response.output_text.done', len(chunks)+1, text=text))
    out.append(terminal(text, len(chunks)+2))
    return out

def frames(values, newline='\n', ascii=False):
    return ''.join('event: '+v['type']+newline+'data: '+json.dumps(v, ensure_ascii=ascii)+newline*2 for v in values).encode('utf-8')

class Store:
    provider = 'openai'
    def __init__(self): self.reads = 0
    def load_for_application(self): self.reads += 1; return 'DUMMY-NOT-A-CREDENTIAL'

class SSEDecodeTests(unittest.TestCase):
    def test_every_single_byte_boundary_utf8_crlf_and_fragmented_json_strings(self):
        options = [dict(OPTIONS[0], en='Yes, I hear you — clearly 😀.', ru='Да, я вас слышу — хорошо 😀.'), OPTIONS[1],
                   {'en':'Could you explain "next step" and the } symbol?',
                    'ru':'Можете объяснить «следующий шаг» и символ }?', 'kind':'clarify'}]
        text = raw(options); values = events(text, list(text)); wire = frames(values, '\r\n')
        parser = SSEDecoder(); session = StreamSession(CONVERSATION)
        for byte in wire:
            for event in parser.feed(bytes([byte])): session.accept(event)
        parser.finish(); session.end_of_stream()
        self.assertEqual(session.public_result['options'], options)
        self.assertEqual(session.selected_en, '')
        self.assertEqual(len(session.parser.staged), 3)

    def test_sse_multiline_data_comment_and_CR_split(self):
        p = SSEDecoder(); wire=b': public heartbeat\r\ndata: {"type":\r\ndata: "response.in_progress", "sequence_number": 1}\r\n\r\n'
        got=[]
        for b in wire: got.extend(p.feed(bytes([b])))
        p.finish(); self.assertEqual(got,[{'type':'response.in_progress','sequence_number':1}])

    def test_invalid_UTF8_and_truncated_UTF8_or_frame_reject(self):
        p=SSEDecoder()
        with self.assertRaises(TextError):p.feed(b'\xff')
        p=SSEDecoder();p.feed(b'\xe2')
        with self.assertRaises(TextError):p.finish()
        p=SSEDecoder();p.feed(b'data: {"type":"x"}\n')
        with self.assertRaises(TextError):p.finish()

    def test_size_limits_and_event_type_mismatch_reject(self):
        for wire in [b'x'*(MAX_JSON_BYTES+1), b':'*(MAX_STREAM_BYTES+1),
                     b'event: x\ndata: {"type":"y"}\n\n']:
            with self.assertRaises(TextError):SSEDecoder().feed(wire)

    def test_duplicate_SSE_json_keys_reject(self):
        with self.assertRaises(TextError):SSEDecoder().feed(b'data: {"type":"x","type":"y"}\n\n')

    def test_optional_transport_DONE_requires_successful_response_terminal(self):
        parser=SSEDecoder();s=StreamSession(CONVERSATION)
        for event in parser.feed(frames(events())+b'data: [DONE]\n\n'):s.accept(event)
        parser.finish();s.end_of_stream();self.assertEqual(s.public_result['options'],OPTIONS)
        parser=SSEDecoder();s=StreamSession(CONVERSATION)
        with self.assertRaises(TextError):
            for event in parser.feed(frames(events()[:2])+b'data: [DONE]\n\n'):s.accept(event)
        self.assertIsNone(s.public_result)

class PairAndLifecycleTests(unittest.TestCase):
    def session(self): return StreamSession(CONVERSATION, selected_en='Could you speak more slowly?')
    def test_first_closed_pair_is_staged_but_never_public_before_terminal(self):
        s=self.session();s.accept(created());text=raw();first_end=text.index('}')+1
        s.accept(output_event('response.output_text.delta',1,delta=text[:first_end]))
        self.assertEqual(s.parser.staged,[OPTIONS[0]]);self.assertIsNone(s.public_result)
        with self.assertRaises(TextError):s.select(0)
        s.accept(output_event('response.output_text.delta',2,delta=text[first_end:]))
        s.accept(output_event('response.output_text.done',3,text=text));self.assertIsNone(s.public_result)
        s.accept(terminal(text,4));s.end_of_stream();self.assertEqual(s.public_result['options'],OPTIONS)
        self.assertEqual(s.selected_en,'Could you speak more slowly?')
        self.assertEqual(s.select(1),'The sound is breaking up.')
        self.assertEqual(s.conversation['own_response_state']['spoken'],'unknown')

    def test_late_refusal_failed_incomplete_and_error_discard_staged_pairs_preserve_selection(self):
        for kind in ['response.refusal.delta','response.refusal.done','response.failed','response.incomplete','error']:
            with self.subTest(kind=kind):
                s=self.session();s.accept(created());s.accept(output_event('response.output_text.delta',1,delta=raw()))
                self.assertTrue(s.parser.staged)
                with self.assertRaises(TextError):s.accept({'type':kind,'sequence_number':2,'delta':'Public refusal fixture'})
                self.assertIsNone(s.public_result);self.assertEqual(s.parser.staged,[]);self.assertEqual(s.selected_en,'Could you speak more slowly?')

    def test_disconnect_after_full_pair_or_done_is_not_success(self):
        for done in [False,True]:
            s=self.session();s.accept(created());s.accept(output_event('response.output_text.delta',1,delta=raw()))
            if done:s.accept(output_event('response.output_text.done',2,text=raw()))
            with self.assertRaises(TextError):s.end_of_stream()
            self.assertIsNone(s.public_result);self.assertEqual(s.parser.staged,[])

    def test_Stop_and_new_completed_topic_never_publish_old_stream_or_overwrite_selection(self):
        for action in [lambda s:s.cancel(),lambda s:s.supersede(99)]:
            s=self.session();s.accept(created());s.accept(output_event('response.output_text.delta',1,delta=raw()))
            action(s);s.accept(output_event('response.output_text.done',2,text=raw()));s.accept(terminal(raw(),3));s.end_of_stream()
            self.assertEqual(s.phase,'cancelled');self.assertIsNone(s.public_result);self.assertEqual(s.selected_en,'Could you speak more slowly?')

    def test_new_terminal_group_does_not_change_manual_selection(self):
        s=self.session()
        for e in events():s.accept(e)
        chosen=s.select(1);new=StreamSession(CONVERSATION,chosen)
        for e in events(raw([OPTIONS[2]])):new.accept(e)
        self.assertEqual(new.selected_en,chosen);self.assertEqual(new.public_result['options'],[OPTIONS[2]])

    def test_whole_group_bad_second_option_rejects_even_after_valid_first_pair(self):
        text=raw([OPTIONS[0],{'en':'Second public fixture','ru':'Второй вариант'}]);s=self.session()
        s.accept(created());s.accept(output_event('response.output_text.delta',1,delta=text));self.assertEqual(s.parser.staged,[OPTIONS[0]])
        with self.assertRaises(TextError):s.accept(output_event('response.output_text.done',2,text=text))
        self.assertIsNone(s.public_result);self.assertEqual(s.parser.staged,[])

    def test_full_group_max_count_extra_root_and_duplicate_key_are_barriers(self):
        cases=[raw(OPTIONS+[OPTIONS[0]]),raw()[:-1]+',"extra":true}',
               raw()[:-1]+',"options":[]}',raw().replace('"en":','"en":"duplicate", "en":',1)]
        for text in cases:
            with self.subTest(text=text[:50]):
                s=self.session()
                with self.assertRaises(TextError):
                    for e in events(text):s.accept(e)
                self.assertIsNone(s.public_result);self.assertEqual(s.parser.staged,[])

    def test_prefix_fake_object_braces_and_unclosed_strings_never_stage(self):
        s=self.session();s.accept(created())
        s.accept(output_event('response.output_text.delta',1,delta='{"options":[{"en":"Could you explain \\"}'))
        self.assertEqual(s.parser.staged,[]);self.assertIsNone(s.public_result)

    def test_json_unicode_escapes_and_split_surrogate_pair(self):
        options=[dict(OPTIONS[0],en='Yes, I hear you 😀.',ru='Да, я вас слышу 😀.')];text=raw(options,True);s=self.session()
        for e in events(text,list(text)):s.accept(e)
        self.assertEqual(s.public_result['options'],options)

    def test_unpaired_surrogate_rejects_no_public_phrase(self):
        text=raw([dict(OPTIONS[0],en='Yes \ud800.')],True);s=self.session()
        with self.assertRaises(TextError):
            for e in events(text):s.accept(e)
        self.assertIsNone(s.public_result)

    def test_done_or_terminal_text_mismatch_identity_and_sequence_reject(self):
        cases=[output_event('response.output_text.done',2,text=raw()+' '),
               output_event('response.output_text.delta',1,delta=' '),
               output_event('response.output_text.delta',2,delta=' ',item_id='wrong'),
               output_event('response.output_text.delta',2,delta=' ',output_index=1),
               terminal(raw(),2)]
        for event in cases:
            s=self.session();s.accept(created());s.accept(output_event('response.output_text.delta',1,delta=raw()))
            with self.assertRaises(TextError):s.accept(event)
            self.assertIsNone(s.public_result)

    def test_terminal_refusal_content_or_wrong_model_rejects(self):
        for change in [lambda e:e['response']['output'][0]['content'].append({'type':'refusal','refusal':'No'}),
                       lambda e:e['response'].update(model='other'),
                       lambda e:e['response'].update(status='incomplete')]:
            s=self.session()
            for e in events()[:-1]:s.accept(e)
            e=terminal(raw(),3);change(e)
            with self.assertRaises(TextError):s.accept(e)
            self.assertIsNone(s.public_result)

    def test_current_unknown_fact_and_old_topic_guards_not_relaxed(self):
        c=reply_context.build('Цена пятнадцать или пятьдесят долларов?');s=StreamSession(c)
        with self.assertRaises(TextError):
            for e in events(raw([OPTIONS[0]])):s.accept(e)
        self.assertIsNone(s.public_result)

class PrototypeDispatchTests(unittest.TestCase):
    def adapter(self,d):
        store=Store();return TextAdapter(store,Ledger(Path(d)/'budget.json'),TextConsent('openai',MODEL,.1,True,'estimated_v1'))

    def test_disabled_default_has_no_dispatch_key_or_reservation(self):
        with tempfile.TemporaryDirectory() as d:
            a=self.adapter(d);p=DisabledPrototype(a,transport=lambda *x:self.fail('Dispatch'))
            with self.assertRaises(TextError):p.run(StreamSession(CONVERSATION))
            self.assertEqual(a.store.reads,0);self.assertFalse(a.ledger.path.exists())

    def test_exact_same_provider_model_schema_prompt_and_budget_reserves_before_key(self):
        bodies=[]
        with tempfile.TemporaryDirectory() as d:
            a=self.adapter(d)
            def normal(url,body,key):
                bodies.append(body);return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':raw()}]}]}
            a.transport=normal;a.generate('',CONVERSATION['latest_interlocutor_utterance']['text'],'reply',conversation=CONVERSATION)
            shadow=stream_body(CONVERSATION);self.assertEqual({**shadow,'stream':False},bodies[0])
            calls=[]
            def transport(url,body,key,cancel):
                calls.append(url);self.assertEqual(url,ENDPOINT);self.assertEqual(body,shadow)
                self.assertEqual(json.loads(a.ledger.path.read_text())['requests'],2);self.assertEqual(a.store.reads,2)
                yield frames(events())
            p=DisabledPrototype(a,True,transport);r=p.run(StreamSession(CONVERSATION))
            self.assertEqual(r['options'],OPTIONS);self.assertEqual(calls,[ENDPOINT]);self.assertFalse(a.busy.locked())
            with self.assertRaises(TextError):p.run(StreamSession(CONVERSATION))
            self.assertEqual(calls,[ENDPOINT]);self.assertEqual(json.loads(a.ledger.path.read_text())['requests'],2)

    def test_late_failure_no_retry_no_refund_and_generator_closed(self):
        with tempfile.TemporaryDirectory() as d:
            a=self.adapter(d);calls=[];closed=[]
            def transport(*args):
                calls.append(1)
                try:
                    yield frames(events()[:2]);yield frames([{'type':'error','sequence_number':2}])
                finally:closed.append(True)
            p=DisabledPrototype(a,True,transport);s=StreamSession(CONVERSATION,'Selected public draft')
            with self.assertRaises(TextError):p.run(s)
            held=a.ledger.path.read_text()
            with self.assertRaises(TextError):p.run(StreamSession(CONVERSATION))
            self.assertEqual(a.ledger.path.read_text(),held);self.assertEqual(calls,[1]);self.assertEqual(closed,[True]);self.assertEqual(s.selected_en,'Selected public draft');self.assertIsNone(s.public_result)

    def test_Stop_during_stream_closes_reader_preserves_selection_no_resend(self):
        with tempfile.TemporaryDirectory() as d:
            a=self.adapter(d);cancel=threading.Event();closed=[]
            def transport(*args):
                try:
                    yield frames(events()[:2]);cancel.set();yield frames(events()[2:])
                finally:closed.append(True)
            p=DisabledPrototype(a,True,transport);s=StreamSession(CONVERSATION,'Chosen phrase')
            self.assertIsNone(p.run(s,cancel));self.assertEqual(s.phase,'cancelled');self.assertEqual(s.selected_en,'Chosen phrase');self.assertEqual(closed,[True]);self.assertEqual(json.loads(a.ledger.path.read_text())['requests'],1)

    def test_usage_accounted_before_terminal_content_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            a=self.adapter(d);seen=[];ev=events();ev[-1]['response']['output'][0]['content'].append({'type':'refusal','refusal':'No'})
            p=DisabledPrototype(a,True,lambda *args:iter([frames(ev)]))
            with self.assertRaises(TextError):p.run(StreamSession(CONVERSATION),on_usage=seen.append)
            self.assertEqual(len(seen),1);self.assertEqual(seen[0]['output_tokens'],50);self.assertGreater(seen[0]['reservation']['reserved_usd'],0)

    def test_Stop_between_events_in_one_chunk_before_terminal_publication(self):
        with tempfile.TemporaryDirectory() as d:
            a=self.adapter(d);cancel=threading.Event();s=StreamSession(CONVERSATION,'Chosen phrase')
            p=DisabledPrototype(a,True,lambda *args:iter([frames(events())]))
            self.assertIsNone(p.run(s,cancel,on_usage=lambda metadata:cancel.set()))
            self.assertEqual(s.phase,'cancelled');self.assertEqual(s.selected_en,'Chosen phrase')
            self.assertEqual(json.loads(a.ledger.path.read_text())['requests'],1)

    def test_topic_change_between_events_before_terminal_publication(self):
        with tempfile.TemporaryDirectory() as d:
            a=self.adapter(d);s=StreamSession(CONVERSATION,'Chosen phrase')
            p=DisabledPrototype(a,True,lambda *args:iter([frames(events())]))
            self.assertIsNone(p.run(s,on_usage=lambda metadata:s.supersede(99)))
            self.assertEqual(s.phase,'cancelled');self.assertEqual(s.selected_en,'Chosen phrase')

    def test_insufficient_budget_or_pre_Stop_or_wrong_provider_blocks_before_key(self):
        for case in ['budget','Stop','provider']:
            with tempfile.TemporaryDirectory() as d:
                a=self.adapter(d);cancel=threading.Event()
                if case=='budget':a.ledger.path.write_text('{"reserved_usd":0.1,"requests":2}')
                if case=='Stop':cancel.set()
                if case=='provider':a.consent=TextConsent('omniroute',MODEL,.1,True,'estimated_v1')
                p=DisabledPrototype(a,True,lambda *args:self.fail('Dispatch'))
                with self.assertRaises(TextError):p.run(StreamSession(CONVERSATION),cancel)
                self.assertEqual(a.store.reads,0)

    def test_production_has_no_activation_route_import_or_flag(self):
        for name in ['backend_server.py','text_provider.py','main.swift']:
            text=(ROOT/'src'/name).read_text();self.assertNotIn('DisabledPrototype',text);self.assertNotIn('responses_sse',text)

if __name__ == '__main__':unittest.main()

"""Synthetic virtual-time tests: no capture, permission, Keychain, or provider."""
import unittest,tempfile,json,time,struct,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from capture_policy import cloud_consent,native_consent
from capture_runtime import PCMConsumer,CaptureConsent,CaptureError,CHUNK
from audio_integration import CaptureCloud
class NoStore:
 def load_for_application(self):raise AssertionError('No credentials in offline tests')
def approvals():
 n={'approved':True,'source':'zoom','schema_version':2,'approval_id':'offline-test-only','maximum_seconds':5400,'expires_unix':time.time()+7200,'capture_scope':'zoom_output','private_call_capture':True,'microphone':False}
 c={'approved':True,'source':'zoom','schema_version':2,'approval_id':n['approval_id'],'maximum_seconds':5400,'expires_unix':n['expires_unix'],'capture_scope':'zoom_output','private_call_upload':True,'persist_transcript':False,'provider':'openai','budget_usd':3.20}
 return n,c
class ReadinessTests(unittest.TestCase):
 def test_explicit_source_expiry_duration_budget_and_privacy(self):
  n,c=approvals();self.assertEqual(cloud_consent(n,c).maximum_seconds,5400)
  for field,value in [('approval_id','different'),('budget_usd',.15),('persist_transcript',True),('private_call_upload',False),('source','public_sample'),('expires_unix',0),('maximum_seconds',5401)]:
   with self.subTest(field=field):self.assertIsNone(cloud_consent(n,{**c,field:value}))
  self.assertIsNone(native_consent({**n,'microphone':True}))
 def test_stop_overrides_even_complete_future_consent(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);n,c=approvals()
   for name,value in [('CAPTURE-APPROVAL.json',n),('CAPTURE-CLOUD-APPROVAL.json',c),('AUDIO-DO-NOT-PLAY.json',{'blocked':True})]:(root/name).write_text(json.dumps(value))
   a=CaptureCloud(root,NoStore())
   with self.assertRaises(CaptureError):a.start()
   self.assertFalse((root/'CAPTURE-CLOUD-BUDGET.json').exists())
 def test_90_minutes_continuous_silence_bounded_queue_and_expiry(self):
  clock=[0.];c=PCMConsumer(CaptureConsent('zoom',5400,True,0,3.20),clock=lambda:clock[0]);c.start('zoom');pcm=bytes(CHUNK)
  for i in range(27000):
   clock[0]=i/5;c.touch();c.feed(pcm);frame=c.next_frame(.001);self.assertEqual(len(frame),CHUNK);c.mark_cloud_frame(len(frame))
  self.assertTrue(c.running);self.assertEqual(c.snapshot()['captured_seconds'],5400);self.assertEqual(c.snapshot()['queued_frames'],0)
  clock[0]=5400;c.touch();c.feed(pcm);self.assertEqual(c.reason,'duration_limit')
 def test_private_receipt_has_no_transcript_and_failed_attempt_cannot_repeat(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);n,c=approvals()
   for name,value in [('CAPTURE-APPROVAL.json',n),('CAPTURE-CLOUD-APPROVAL.json',c)]:(root/name).write_text(json.dumps(value))
   a=CaptureCloud(root,NoStore())
   with patch('audio_integration.NativeReceiver.start',side_effect=CaptureError('offline failure')):
    with self.assertRaises(CaptureError):a.start()
   a.events.append({'kind':'delta','text':'PRIVATE-SYNTHETIC-TEXT','run_id':a.current});a.save_receipt()
   self.assertNotIn('PRIVATE-SYNTHETIC-TEXT',next((root/'receipts').glob('*.json')).read_text())
   with self.assertRaises(CaptureError):a.start()
   self.assertEqual(json.loads((root/'CAPTURE-CLOUD-BUDGET.json').read_text())['reserve_usd'],3.20)
 def test_paging_and_history_capacity_preserve_existing_rows(self):
  with tempfile.TemporaryDirectory() as d:
   a=CaptureCloud(d,NoStore());a.consumer=PCMConsumer(CaptureConsent('zoom',5400,True,0,3.20));a.consumer.start('zoom')
   for i in range(1100):a.emit({'kind':'delta','text':str(i)})
   self.assertEqual(len(a.events_since(0)),500);self.assertEqual(a.events_since(500)[0]['seq'],501)
   first=a.events[0].copy();a.event_bytes=12*1024*1024;a.emit({'kind':'delta','text':'limit'})
   self.assertEqual(a.consumer.reason,'history_capacity');self.assertEqual(a.events[0],first)
import asyncio
from stream_adapter import translate_pcm
class VirtualSource(PCMConsumer):
 def __init__(self):
  self.virtual=0.;super().__init__(CaptureConsent('zoom',5400,True,0,3.20),clock=lambda:self.virtual);self.start('zoom')
 def next_frame(self,timeout=.5):
  if self.virtual>=5400:self.finish('duration_limit');return None
  self.virtual=round(self.virtual+.2,1);return bytes(CHUNK)
class CountingSocket:
 def __init__(self,early=False):self.init=iter(['session.created','session.updated']);self.count=0;self.closes=0;self.closed=asyncio.Event();self.early=early
 async def recv(self):return json.dumps({'type':next(self.init)})
 async def send(self,raw):
  kind=json.loads(raw)['type']
  if kind=='session.input_audio_buffer.append':self.count+=1
  if kind=='session.close':self.closes+=1;self.closed.set()
 def __aiter__(self):return self.receive()
 async def receive(self):
  if not self.early:await self.closed.wait()
  yield json.dumps({'type':'session.output_transcript.delta','delta':'synthetic tail'})
  yield json.dumps({'type':'session.closed'})
 async def __aenter__(self):return self
 async def __aexit__(self,*args):pass
class LongStreamTests(unittest.IsolatedAsyncioTestCase):
 async def test_90_minute_virtual_wire_one_connection_close_and_tail(self):
  source=VirtualSource();ws=CountingSocket();events=[];calls=[]
  def connect(*args,**kwargs):calls.append(1);return ws
  await translate_pcm(source,'DUMMY-OFFLINE',events.append,source.consent,connect,clock=lambda:source.virtual)
  self.assertEqual(calls,[1]);self.assertEqual(ws.count,27000);self.assertEqual(ws.closes,1)
  self.assertEqual(source.cloud_bytes,259200000);self.assertIn('synthetic tail',[e.get('text') for e in events]);self.assertFalse(source.running)
 async def test_provider_closed_stops_no_reconnection(self):
  source=VirtualSource();ws=CountingSocket(early=True);calls=[];events=[]
  def connect(*args,**kwargs):calls.append(1);return ws
  await translate_pcm(source,'DUMMY-OFFLINE',events.append,source.consent,connect,clock=lambda:source.virtual)
  self.assertEqual(calls,[1]);self.assertEqual(source.reason,'provider_closed');self.assertFalse(source.running)

class StopDuringReadTests(unittest.IsolatedAsyncioTestCase):
 async def test_stop_during_pending_read_never_appends_returned_frame(self):
  class StoppedSource(VirtualSource):
   def next_frame(self,timeout=.5):self.finish('manual_stop');return bytes(CHUNK)
  source=StoppedSource();ws=CountingSocket()
  await translate_pcm(source,'DUMMY-OFFLINE',lambda e:None,source.consent,lambda *a,**kw:ws)
  self.assertEqual(ws.count,0);self.assertEqual(ws.closes,1);self.assertEqual(source.reason,'manual_stop')

import sys,unittest,asyncio,json,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from capture_runtime import CaptureConsent,PCMConsumer,CHUNK
from stream_adapter import translate_pcm,StreamPolicyError
class Source(PCMConsumer):
 def next_frame(self,timeout=.5):
  frame=super().next_frame(.01)
  if frame is None:self.finish('mock_input_end')
  return frame
class Socket:
 def __init__(self):self.frames=[];self.closed=asyncio.Event();self.init=iter([{'type':'session.created'},{'type':'session.updated'}])
 async def recv(self):return json.dumps(next(self.init))
 async def send(self,raw):
  data=json.loads(raw);self.frames.append(data)
  if data['type']=='session.close':self.closed.set()
 def __aiter__(self):return self.events()
 async def events(self):
  yield json.dumps({'type':'session.output_transcript.delta','delta':'Спасибо.'})
  yield json.dumps({'type':'session.output_audio.delta','delta':'IGNORED-AUDIO'})
  await self.closed.wait()
  yield json.dumps({'type':'session.output_transcript.delta','delta':' Конец.'})
  yield json.dumps({'type':'session.closed'})
class Connection:
 def __init__(self,socket):self.socket=socket
 async def __aenter__(self):return self.socket
 async def __aexit__(self,*args):pass
class StreamTests(unittest.IsolatedAsyncioTestCase):
 async def test_no_cloud_consent_before_connection(self):
  c=Source(CaptureConsent('public_sample'));c.start('public_sample')
  with self.assertRaises(StreamPolicyError):await translate_pcm(c,'DUMMY',lambda e:None,c.consent,lambda *a,**kw:self.fail('network'))
 async def test_dynamic_frames_drain_and_audio_discard_mock_ws(self):
  consent=CaptureConsent('public_sample',150,True);c=Source(consent);c.start('public_sample');c.feed(struct.pack('<4800h',*([1000]*4800)))
  ws=Socket();events=[];calls=[]
  def connect(*args,**kwargs):calls.append(1);return Connection(ws)
  await translate_pcm(c,'DUMMY-NOT-REAL-KEY',events.append,consent,connect)
  self.assertEqual(len(calls),1)
  self.assertEqual([f['type'] for f in ws.frames],['session.update','session.input_audio_buffer.append','session.close'])
  self.assertEqual(''.join(e.get('text','') for e in events if e['kind']=='delta'),'Спасибо. Конец.')
  self.assertNotIn('IGNORED-AUDIO',str(events));self.assertNotIn('DUMMY',str(events));self.assertFalse(c.running)
 async def test_wrong_approved_source_cannot_connect(self):
  c=Source(CaptureConsent('zoom'));c.start('zoom')
  with self.assertRaises(StreamPolicyError):await translate_pcm(c,'DUMMY',lambda e:None,CaptureConsent('public_sample',150,True),lambda *a,**kw:self.fail('network'))
class FailureStreamTests(unittest.IsolatedAsyncioTestCase):
 async def test_connect_failure_stops_source_without_retry(self):
  consent=CaptureConsent('zoom',1800,True,0);source=Source(consent);source.start('zoom');calls=[]
  def connect(*args,**kwargs):calls.append(1);raise ConnectionError('offline injected disconnect')
  with self.assertRaises(ConnectionError):await translate_pcm(source,'DUMMY',lambda e:None,consent,connect)
  self.assertEqual(calls,[1]);self.assertFalse(source.running);self.assertTrue(source.stop.is_set())
 async def test_handshake_error_stops_source_before_audio_and_no_retry(self):
  class ErrorSocket(Socket):
   async def recv(self):return json.dumps({'type':'error','error':{'code':'injected_mock_error'}})
  consent=CaptureConsent('zoom',1800,True,0);source=Source(consent);source.start('zoom');ws=ErrorSocket();events=[]
  await translate_pcm(source,'DUMMY',events.append,consent,lambda *a,**kw:Connection(ws))
  self.assertFalse(source.running);self.assertEqual(ws.frames,[]);self.assertEqual(source.reason,'api_error')
 async def test_cancel_cleans_source_and_never_reconnects(self):
  class WaitingSocket(Socket):
   async def recv(self):await asyncio.Event().wait()
  consent=CaptureConsent('zoom',1800,True,0);source=Source(consent);source.start('zoom');ws=WaitingSocket();calls=[]
  def connect(*args,**kwargs):calls.append(1);return Connection(ws)
  task=asyncio.create_task(translate_pcm(source,'DUMMY',lambda e:None,consent,connect));await asyncio.sleep(.01);task.cancel()
  with self.assertRaises(asyncio.CancelledError):await task
  self.assertFalse(source.running);self.assertEqual(calls,[1]);self.assertEqual(ws.frames,[])

class StaleQueueStreamTests(unittest.IsolatedAsyncioTestCase):
 async def test_explicit_context_loss_without_replay_or_reconnect(self):
  now=[0.];consent=CaptureConsent('zoom',60,True,0,1,True);source=PCMConsumer(consent,lambda:now[0]);source.start('zoom');source.feed(b'\0'*CHUNK);now[0]=2.1
  ws=Socket();events=[];calls=[]
  def connect(*args,**kwargs):calls.append(1);return Connection(ws)
  await translate_pcm(source,'DUMMY',events.append,consent,connect)
  self.assertEqual(source.reason,'audio_backlog_stale');self.assertEqual(calls,[1]);self.assertEqual(source.cloud_bytes,0)
  self.assertFalse(any(f['type']=='session.input_audio_buffer.append' for f in ws.frames))
  self.assertTrue(any(e['kind']=='error' and 'устаревший звук' in e['text'] for e in events));self.assertEqual(source.discarded_frames,1)

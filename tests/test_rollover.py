import unittest,sys,asyncio,json,struct,base64
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from stream_adapter import translate_pcm
from capture_runtime import PCMConsumer,CaptureConsent,CHUNK
class VirtualSource(PCMConsumer):
 def __init__(self,frames=750,budget=1):
  self.virtual=0.;self.index=0;self.total=frames;super().__init__(CaptureConsent('zoom',budget/.034*60,True,0,budget,True),clock=lambda:self.virtual);self.start('zoom')
 def next_frame(self,timeout=.5):
  if self.index>=self.total:self.finish('mock_input_end');return None
  value=self.index;self.index+=1;self.virtual=round(self.virtual+.2,1);return struct.pack('<i',value)+bytes(CHUNK-4)
class Socket:
 def __init__(self,source,number,hang=False):self.source=source;self.number=number;self.init=0;self.ids=[];self.closed=asyncio.Event();self.disposed=False;self.hang=hang
 async def __aenter__(self):return self
 async def __aexit__(self,*args):self.disposed=True
 async def recv(self):
  if self.hang:await asyncio.Event().wait()
  self.init+=1;return json.dumps({'type':'session.created' if self.init==1 else 'session.updated','session':{'expires_at':1000+self.source.virtual+70}})
 async def send(self,raw):
  event=json.loads(raw)
  if event['type']=='session.input_audio_buffer.append':
   self.ids.append(struct.unpack('<i',base64.b64decode(event['audio'])[:4])[0])
   # Virtual frames advance 200 ms instantly. Give mock setup callbacks a
   # deterministic chance to run before advancing the clock again; no real sleep.
   for _ in range(4):await asyncio.sleep(0)
  if event['type']=='session.close':self.closed.set()
 def __aiter__(self):return self.events()
 async def events(self):
  await self.closed.wait()
  yield json.dumps({'type':'session.output_transcript.delta','event_id':'a','delta':'Один','elapsed_ms':200})
  yield json.dumps({'type':'session.output_transcript.delta','event_id':'a','delta':'Один','elapsed_ms':200})
  yield json.dumps({'type':'session.output_transcript.delta','event_id':'b','delta':' фрагмент.','elapsed_ms':200})
  yield json.dumps({'type':'session.closed','event_id':'close'})
class RolloverTests(unittest.IsolatedAsyncioTestCase):
 async def test_server_expiry_renews_with_contiguous_once_only_frames_and_drain(self):
  source=VirtualSource();sockets=[];events=[]
  def connect(*args,**kwargs):
   self.assertIn('/realtime/translations',args[0]);s=Socket(source,len(sockets)+1);sockets.append(s);return s
  await translate_pcm(source,'DUMMY',events.append,source.consent,connect,clock=lambda:source.virtual,epoch=lambda:1000+source.virtual)
  self.assertGreater(len(sockets),1);ids=[i for s in sockets for i in s.ids];self.assertEqual(ids,list(range(750)));self.assertEqual(source.cloud_bytes,750*CHUNK);self.assertTrue(all(s.disposed for s in sockets));self.assertEqual(sum(e['kind']=='ready' for e in events),1);self.assertGreater(sum(e['kind']=='boundary' for e in events),0)
  # elapsed_ms is NOT a unique ID; distinct fragments survive, duplicate event_id doesn't.
  self.assertEqual(sum(e['kind']=='delta' for e in events),2*sum(s.closed.is_set() for s in sockets))
 async def test_renewal_failure_stops_after_one_failed_setup_no_audio_replay(self):
  source=VirtualSource();sockets=[];calls=[];events=[]
  def connect(*args,**kwargs):
   calls.append(1)
   if len(calls)>1:raise ConnectionError('offline failure')
   s=Socket(source,1);sockets.append(s);return s
  await translate_pcm(source,'DUMMY',events.append,source.consent,connect,clock=lambda:source.virtual,epoch=lambda:1000+source.virtual)
  self.assertEqual(len(calls),2);self.assertEqual(source.reason,'renewal_failed');self.assertFalse(source.running);self.assertTrue(sockets[0].disposed);self.assertEqual(sockets[0].ids,list(range(len(sockets[0].ids))))
 async def test_slow_standby_is_cancelled_disposed_not_retried(self):
  source=VirtualSource();sockets=[]
  def connect(*args,**kwargs):s=Socket(source,len(sockets)+1,hang=bool(sockets));sockets.append(s);return s
  await translate_pcm(source,'DUMMY',lambda e:None,source.consent,connect,clock=lambda:source.virtual,epoch=lambda:1000+source.virtual)
  self.assertEqual(len(sockets),2);self.assertTrue(all(s.disposed for s in sockets));self.assertEqual(source.reason,'renewal_not_ready')
 async def test_budget_is_global_across_connections_silence_not_dropped(self):
  source=VirtualSource(frames=1000,budget=.05);sockets=[]
  def connect(*args,**kwargs):s=Socket(source,len(sockets)+1);sockets.append(s);return s
  await translate_pcm(source,'DUMMY',lambda e:None,source.consent,connect,clock=lambda:source.virtual,epoch=lambda:1000+source.virtual)
  self.assertEqual(source.reason,'spend_limit');self.assertLessEqual(source.cloud_bytes/48000/60*.034,.05);self.assertEqual([i for s in sockets for i in s.ids],list(range(441)));self.assertGreater(len(sockets),1)

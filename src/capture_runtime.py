"""Bounded local PCM consumer. No OS capture, permission request, audio disk or cloud call.
Native helper connects only after explicit approved capture Start. Tests use fake pipes.
"""
import threading,queue,time,math,struct,socket,os,json
from pathlib import Path
from dataclasses import dataclass
CHUNK=9600
class CaptureError(ValueError):pass
@dataclass(frozen=True)
class CaptureConsent:
 source:str
 maximum_seconds:float=150
 cloud_allowed:bool=False
 idle_seconds:float=60
 budget_usd:float=.15
 budget_limited:bool=False
 unlimited:bool=False
@dataclass(frozen=True)
class PCMFrame:
 data:bytes
 ready_at:float # Local receiver time, not a native capture or speech timestamp.
class PCMConsumer:
 def __init__(self,consent=None,clock=time.monotonic):
  self.consent=consent;self.clock=clock;self.lock=threading.RLock();self.frames=queue.Queue(maxsize=50 if consent and consent.budget_limited else 5)
  self.stop=threading.Event();self.running=False;self.pending=bytearray();self.samples=0;self.peak=0;self.rms=0
  self.max_frame_age=0;self.discarded_frames=0;self.stale_limit=2.0
  self.started=0;self.heartbeat=0;self.last_sound=0;self.reason=None;self.cloud_bytes=0
 def start(self,source):
  with self.lock:
   if self.running:raise CaptureError('Захват уже работает.')
   if self.consent is None or source!=self.consent.source or source not in ('public_sample','zoom'):raise CaptureError('Нет отдельного разрешения на этот источник.')
   if not 0<self.consent.maximum_seconds<=(21600 if self.consent.unlimited else 10/.034*60):raise CaptureError('Неверный ограничитель длительности.')
   self.started=self.clock();self.heartbeat=self.started;self.last_sound=self.started;self.stop.clear();self.running=True
 def touch(self):self.heartbeat=self.clock()
 def feed(self,data):
  with self.lock:
   if not self.running:return
   now=self.clock()
   age=self.oldest_age(now)
   if age>=self.stale_limit:return self.stop_stale(age)
   if now-self.heartbeat>5:return self.finish('ui_heartbeat_lost')
   if now-self.started>=self.consent.maximum_seconds:return self.finish('spend_limit' if self.consent.budget_limited else 'duration_limit')
   if len(data)>CHUNK*2:return self.finish('oversize_frame')
   self.pending.extend(data)
   while len(self.pending)>=CHUNK:
    pcm=bytes(self.pending[:CHUNK]);del self.pending[:CHUNK]
    samples=struct.unpack('<4800h',pcm);self.samples+=4800
    self.peak=max(abs(v) for v in samples);self.rms=math.sqrt(sum(v*v for v in samples)/4800)/32768
    if self.peak>100:self.last_sound=now
    if self.consent.idle_seconds and now-self.last_sound>=self.consent.idle_seconds:return self.finish('idle_limit')
    try:
     self.frames.put_nowait(PCMFrame(pcm,now))
    except queue.Full:return self.finish('backlog_gap_stopped')
 def mark_cloud_frame(self,byte_count):
  with self.lock:self.cloud_bytes+=byte_count
 def budget_allows_frame(self,byte_count):
  with self.lock:return self.consent.unlimited or (self.cloud_bytes+byte_count)/48000/60*.034<=self.consent.budget_usd+1e-9
 def oldest_age(self,now):
  with self.frames.mutex:
   return max(0,now-self.frames.queue[0].ready_at) if self.frames.queue else 0
 def snapshot(self):
  with self.lock:
   age=self.oldest_age(self.clock())
   return {'oldest_frame_age_seconds':round(age,3),'max_frame_age_seconds':round(self.max_frame_age,3),'lag_state':'stopped_stale' if self.reason=='audio_backlog_stale' else 'lagging' if age>=.6 else 'current','discarded_frames':self.discarded_frames,'running':self.running,'source':self.consent.source if self.consent else None,'cloud_allowed':bool(self.consent and self.consent.cloud_allowed),'sent_to_cloud':self.cloud_bytes>0,'captured_seconds':round(self.samples/24000,3),'rms':round(self.rms,5),'peak':self.peak,'reason':self.reason,'activity':'stopped' if not self.running else 'lagging' if age>=.6 else 'sound' if self.clock()-self.last_sound<.8 else 'pause','queued_frames':self.frames.qsize()}
 def finish(self,reason='manual_stop'):
  with self.lock:
   if self.stop.is_set() and self.reason:return
   self.running=False;self.reason=reason;self.stop.set();self.pending.clear()
 # Caller attaches a separately authorized real stream OR local monitor. No implicit uploader.
 def stop_stale(self,age):
  self.max_frame_age=max(self.max_frame_age,age)
  while True:
   try:self.frames.get_nowait();self.discarded_frames+=1
   except queue.Empty:break
  self.finish('audio_backlog_stale')
 def next_frame(self,timeout=.5):
  try:frame=self.frames.get(timeout=timeout)
  except queue.Empty:return None
  with self.lock:
   if self.stop.is_set():
    self.discarded_frames+=1;return None
   age=max(0,self.clock()-frame.ready_at);self.max_frame_age=max(self.max_frame_age,age)
   if age>=self.stale_limit:
    self.discarded_frames+=1;self.stop_stale(age);return None
   return frame.data
class NativeReceiver:
 def __init__(self,path,consumer):self.path=Path(path);self.consumer=consumer;self.listener=None;self.connection=None;self.thread=None;self.bound=False
 def start(self):
  if self.consumer.consent is None:raise CaptureError('Capture permission has not been approved.')
  if self.listener:raise CaptureError('Local receiver already started.')
  self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True);os.chmod(self.path.parent,0o700)
  if self.path.exists():raise CaptureError('Existing socket: do not remove a possibly active receiver.')
  self.listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
  try:
   self.listener.bind(str(self.path));self.bound=True;os.chmod(self.path,0o600);self.listener.listen(1);self.listener.settimeout(.5)
  except Exception:
   self.close_socket();raise CaptureError('Local receiver could not bind; no capture started.') from None
  self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
 def run(self):
  try:
   while not self.consumer.stop.is_set():
    if time.monotonic()-self.consumer.heartbeat>5:self.consumer.finish('ui_heartbeat_lost');break
    try:self.connection,_=self.listener.accept();break
    except socket.timeout:continue
   if not self.connection:return
   self.connection.settimeout(.5)
   # Metadata is bounded; source must match the separately approved mode.
   header=bytearray()
   while len(header)<256:
    byte=self.connection.recv(1)
    if not byte:raise CaptureError('Missing source header')
    if byte==b'\n':break
    header.extend(byte)
   metadata=json.loads(header)
   if metadata.get('rate')!=24000 or metadata.get('channels')!=1 or metadata.get('encoding')!='s16le':raise CaptureError('Invalid format')
   self.consumer.start(metadata.get('source'))
   while self.consumer.running:
    try:pcm=self.connection.recv(CHUNK)
    except socket.timeout:
     if time.monotonic()-self.consumer.heartbeat>5:self.consumer.finish('ui_heartbeat_lost')
     continue
    if not pcm:break
    self.consumer.feed(pcm)
   self.consumer.finish(self.consumer.reason or 'native_pipe_closed')
  except Exception:self.consumer.finish('invalid_source_or_local_pipe')
  finally:self.close_socket()
 def close_socket(self):
  if self.connection:
   try:self.connection.close()
   except OSError:pass
   self.connection=None
  if self.listener:
   self.listener.close();self.listener=None
   if self.bound:
    try:self.path.unlink()
    except FileNotFoundError:pass
    self.bound=False
 def stop(self):self.consumer.finish();self.close_socket()

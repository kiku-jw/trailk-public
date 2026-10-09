"""Explicit source-specific capture approval and bounded dedicated translation stream.
A public attempt reserves $0.15; Zoom requires its own bounded budget. No retries.
"""
import asyncio,json,threading,time,uuid
from pathlib import Path
from capture_runtime import PCMConsumer,CaptureConsent,NativeReceiver,CaptureError
from stream_adapter import translate_pcm
from capture_policy import cloud_consent
from session_policy import session_grant
class CaptureCloud:
 def __init__(self,root,store):self.root=Path(root);self.store=store;self.lock=threading.RLock();self.current=None;self.events=[];self.receiver=None;self.consumer=None;self.started=0;self.running=False;self.event_bytes=0;self.session=None
 def consent(self):
  if self.session:return cloud_consent(self.session['native'],self.session['cloud'])
  if (self.root/'AUDIO-DO-NOT-PLAY.json').exists():return None
  try:
   native=json.loads((self.root/'CAPTURE-APPROVAL.json').read_text());cloud=json.loads((self.root/'CAPTURE-CLOUD-APPROVAL.json').read_text())
   return cloud_consent(native,cloud)
  except Exception:pass
  return None
 def ledger_path(self):return self.root/'session-budgets'/(self.session['id']+'-audio.json') if self.session else self.root/'CAPTURE-CLOUD-BUDGET.json'
 def available(self):return self.consent() is not None and not self.ledger_path().exists()
 def native_session(self):
  if not self.running or not self.session:return None
  return {**self.session['native'],'socket_path':str(self.receiver.path)}
 def emit(self,event):
  with self.lock:
   value={**event,'seq':len(self.events)+1,'run_id':self.current}
   if value['kind']=='delta':value.update(input_position_seconds=self.consumer.cloud_bytes/48000,received_elapsed_seconds=round(time.monotonic()-self.started,3))
   size=len(json.dumps(value,ensure_ascii=False).encode('utf-8'))
   if len(self.events)>=99999 or self.event_bytes+size>12*1024*1024:
    if self.consumer:self.consumer.finish('history_capacity')
    if len(self.events)<100000:self.events.append({'kind':'error','seq':len(self.events)+1,'run_id':self.current,'text':'Достигнут предел истории. Поток остановлен, прочитанные строки сохранены.'})
    return
   self.event_bytes+=size;self.events.append(value)
 def events_since(self,after,limit=500):
  with self.lock:return list(self.events[max(0,after):max(0,after)+limit])
 def start(self,approval=None):
  with self.lock:
   if self.running:raise CaptureError('Capture translation already running.')
   if approval is not None:self.session=session_grant(approval)
   consent=self.consent()
   if consent is None:raise CaptureError('Источник/передача OpenAI не разрешены либо действует STOP. Нужны отдельные действующие согласия и бюджет.')
   if not self.available():raise CaptureError('Одна разрешённая capture-попытка уже зарезервирована; повтора нет.')
   self.current=str(uuid.uuid4());ledger={'run_id':self.current,'reserve_usd':None if consent.unlimited else consent.budget_usd,'spending_mode':'unlimited' if consent.unlimited else 'limited','maximum_seconds':consent.maximum_seconds,'source':consent.source,'actual_usage':'unknown','state':'reserved'}
   # Exclusive create: duplicate Start/server cannot spend this reservation twice.
   path=self.ledger_path();path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
   with path.open('x') as file:json.dump(ledger,file)
   self.consumer=PCMConsumer(consent);self.consumer.touch();self.receiver=NativeReceiver(self.root/'runtime'/('s-'+self.session['id'][:8]+'.sock') if self.session else self.root/'runtime/audio.sock',self.consumer)
   try:self.receiver.start()
   except Exception:
    self.consumer.finish('receiver_failed');self.emit({'kind':'error','text':'Локальный приёмник не подготовлен. Ключ/API не запрашивались.'});self.save_receipt();raise
   self.running=True;self.started=time.monotonic()
   threading.Thread(target=self.worker,args=(consent,),daemon=True).start()
 def worker(self,consent):
  key=None
  try:
   if self.consumer.stop.is_set() or self.consent()!=consent:
    self.consumer.finish('approval_changed_or_stop');return
   key=self.store.load_for_application() # only after distinct user capture/cloud approval and reservation
   asyncio.run(translate_pcm(self.consumer,key,self.emit,consent))
  except Exception:self.emit({'kind':'error','text':'Перевод не подключился или соединение прервалось. Ключ сохранён. Проверьте подключение и доступ к API; автоповтора нет.'})
  finally:
   key=None;self.receiver.stop()
   with self.lock:
    self.emit({'kind':'end','text':'Сессия завершена. История сохранена в окне. Новый запуск только вручную.'});self.running=False;self.save_receipt()
 def save_receipt(self):
  directory=self.root/'receipts';directory.mkdir(exist_ok=True)
  receipt={'run_id':self.current,'source':self.consumer.consent.source,'model':'gpt-realtime-translate','snapshot':self.consumer.snapshot(),'actual_usage':'unknown','events':[e for e in self.events if e.get('run_id')==self.current] if self.consumer.consent.source=='public_sample' else []}
  (directory/(self.current+'.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
 def stop(self):
  if self.consumer:self.consumer.finish('manual_stop')
  if self.receiver:self.receiver.stop()

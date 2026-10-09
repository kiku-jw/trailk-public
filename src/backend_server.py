"""App-owned local backend; no automatic provider or capture activation."""
import json,secrets,threading,sys,tempfile
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import text_budget
from personal_context import PersonalContext,PersonalContextError
from text_provider import TextAdapter,TextConsent,Ledger,TextError,MODEL
from capture_runtime import NativeReceiver,PCMConsumer,CaptureConsent,CaptureError
from audio_integration import CaptureCloud
from capture_policy import native_consent
from connection_settings import ConnectionSettings

from credential_store import KeychainStore
import os
ROOT=Path(os.environ['CALM_DATA_ROOT']);ASSETS=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]/'assets'));HOST='127.0.0.1:0';TOKEN=secrets.token_urlsafe(24)
receiver=None;monitor=None;lock=threading.RLock();INSTANCE=secrets.token_hex(10)
def text_consent():
 if audio.session:return audio.session['text'] if audio.running and audio.consumer and not audio.consumer.stop.is_set() and audio.consent() else None
 path=ROOT/'TEXT-APPROVAL.json'
 if not path.exists():return None
 try:
  value=json.loads(path.read_text())
  if value.get('approved') is not True or value.get('provider')!='openai' or value.get('model')!=MODEL or not 0<float(value.get('budget_usd',0))<=.10:return None
  return TextConsent('openai',MODEL,float(value['budget_usd']),value.get('allow_selected_context') is True,'estimated_v1')
 except Exception:return None
text_estimated=0
def text_reserved():
 try:return json.loads(adapter.ledger.path.read_text()).get('reserved_usd',0)
 except (OSError,ValueError):return 0
adapter=TextAdapter(KeychainStore(),Ledger(ROOT/'TEXT-BUDGET.json'));audio=CaptureCloud(ROOT,adapter.store);settings=ConnectionSettings(ROOT/'CONNECTION-SETTINGS.json')
personal_context=PersonalContext(ROOT/'PERSONAL-CONTEXT.json')
def capture_consent():
 if (ROOT/'AUDIO-DO-NOT-PLAY.json').exists():return None
 try:
  value=json.loads((ROOT/'CAPTURE-APPROVAL.json').read_text())
  return native_consent(value) # monitor never inherits cloud authorization
 except Exception:pass
 return None
class NoSecretMockStore:
 def load_for_application(self):return 'DUMMY-NOT-A-CREDENTIAL'
def mock_transport(url,body,key):
 request=json.loads(body['input']);suggest=request['mode']=='suggest'
 options=[{'en':'Could you say that again a little more slowly?','ru':'Повторите, пожалуйста, немного медленнее.'}]
 if suggest:options.append({'en':'Could you repeat that more slowly, please?','ru':'Повторите это медленнее, пожалуйста.'})
 return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'options':options})}]}]}
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def allowed(self):return self.headers.get('Host')==HOST and self.headers.get('Origin') in (None,'http://'+HOST)
 def send(self,status,data,kind='application/json'):
  raw=json.dumps(data,ensure_ascii=False).encode() if kind=='application/json' else data
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)))
  self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
  self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'")
  self.end_headers()
  try:self.wfile.write(raw)
  except (BrokenPipeError,ConnectionResetError):pass
 def do_GET(self):
  if not self.allowed():return self.send(403,{'error':'Local only'})
  if self.path=='/reply-readiness.js':return self.send(200,(ASSETS/'web/reply-readiness.js').read_bytes(),'text/javascript')
  if self.path=='/start-ux.js':return self.send(200,(ASSETS/'web/start-ux.js').read_bytes(),'text/javascript; charset=utf-8')
  if self.path=='/personal-context.js':return self.send(200,(ASSETS/'web/personal-context.js').read_bytes(),'text/javascript; charset=utf-8')
  if self.path=='/api/personal-context':return self.send(200,personal_context.read())
  if self.path=='/api/token':return self.send(200,{'token':TOKEN})
  if self.path.startswith('/api/state?after='):
   consent=text_consent();capture=capture_consent()
   try:after=max(0,int(self.path.split('=')[-1]))
   except ValueError:return self.send(400,{'error':'Invalid cursor'})
   if monitor:monitor.touch()
   if audio.consumer:audio.consumer.touch()
   return self.send(200,{'ready':audio.available(),'used':audio.ledger_path().exists(),'running':audio.running,'events':audio.events_since(after),'instance_id':INSTANCE,'text_ready':bool(os.environ.get('CALM_VERIFY_OFFLINE')!='1' and consent and (text_budget.price_known(consent.provider,consent.model) and adapter.ledger.available(consent.budget_limit,text_budget.policy(personal_context_enabled=bool(personal_context.read()['text']))['minimum_reservation_usd']))),'text_budget_exhausted':bool(consent and not (text_budget.price_known(consent.provider,consent.model) and adapter.ledger.available(consent.budget_limit,text_budget.policy(personal_context_enabled=bool(personal_context.read()['text']))['minimum_reservation_usd']))),'text_context_allowed':bool(consent and consent.allow_selected_context),'settings':settings.read(),'configured':settings.ready(),'text_busy':adapter.busy.locked(),'text_budget_policy':text_budget.policy(personal_context_enabled=bool(personal_context.read()['text'])),'text_reserved_usd':text_reserved(), 'estimated_text_usd':text_estimated,'estimated_audio_usd':round((audio.consumer.cloud_bytes if audio.consumer else 0)/48000/60*.034,4),'native_session':audio.native_session(),'capture_approved':bool(capture),'audio_blocked':(ROOT/'AUDIO-DO-NOT-PLAY.json').exists(),'capture_source':capture.source if capture else None,'capture':audio.consumer.snapshot() if audio.consumer else monitor.snapshot() if monitor else None})
  files={'/':ASSETS/'web/index.html','/app.js':ASSETS/'web/app.js','/t9.js':ASSETS/'web/t9.js','/segments.js':ASSETS/'web/segments.js','/focus-view.js':ASSETS/'web/focus-view.js','/budget-view.js':ASSETS/'web/budget-view.js','/state.js':ASSETS/'web/state.js','/session-control.js':ASSETS/'web/session-control.js','/text-adapter.js':ASSETS/'web/text-adapter.js','/integration.js':ASSETS/'web/integration.js','/style.css':ASSETS/'web/style.css','/replay.json':ASSETS/'replay.json'}
  file=files.get(self.path)
  if not file:return self.send(404,{'error':'Not found'})
  kind='text/html; charset=utf-8' if file.suffix=='.html' else 'text/javascript; charset=utf-8' if file.suffix=='.js' else 'text/css' if file.suffix=='.css' else 'application/json; charset=utf-8'
  return self.send(200,file.read_bytes(),kind)
 def do_POST(self):
  global receiver,monitor,text_estimated
  if not self.allowed() or self.headers.get('X-Pilot-Token')!=TOKEN:return self.send(403,{'error':'Local request required'})
  try:
   length=int(self.headers.get('Content-Length',0))
   if length>50000 or length<0:return self.send(413,{'error':'Request too large'})
   body=json.loads(self.rfile.read(length) or '{}')
   if self.path=='/api/personal-context':
    if set(body)!={'text'}:raise PersonalContextError('Неверные настройки контекста.')
    return self.send(200,personal_context.save(body['text']))
   if self.path=='/api/settings':
    if audio.running:raise CaptureError('Сначала остановите сессию для изменения подключения и бюджета.')
    return self.send(200,{'ok':True,'settings':settings.save(body)})
   if self.path=='/api/start':
    if os.environ.get('CALM_VERIFY_OFFLINE')=='1':raise CaptureError('Офлайн-проверка: звук и API выключены.')
    if receiver and receiver.listener:raise CaptureError('Сначала остановите локальную monitor-проверку.')
    approval=body.get('session_approval')
    if approval is None:approval=settings.grant()
    audio.start(approval)
    text_estimated=0
    if audio.session:
     adapter.ledger=Ledger(ROOT/'session-budgets'/(audio.session['id']+'-text.json'))
    return self.send(200,{'ok':True,'settings':settings.read(),'configured':settings.ready(),'text_busy':adapter.busy.locked(),'text_budget_policy':text_budget.policy(personal_context_enabled=bool(personal_context.read()['text'])),'text_reserved_usd':text_reserved(), 'estimated_text_usd':text_estimated,'estimated_audio_usd':round((audio.consumer.cloud_bytes if audio.consumer else 0)/48000/60*.034,4),'native_session':audio.native_session()})
   if self.path=='/api/stop':
    audio.stop();return self.send(200,{'ok':True})
   if self.path=='/api/text':
    if os.environ.get('CALM_VERIFY_OFFLINE')=='1':raise TextError('Офлайн-проверка: платный текстовый API выключен.')
    adapter.consent=text_consent()
    request_run=audio.current
    profile=personal_context.read() if body.get('mode')=='reply' else {'text':'','revision':0}
    def observe_usage(metadata):
     global text_estimated
     with lock:
      if request_run==audio.current:text_estimated+=metadata.get('estimated_text_usd') or 0
    result=adapter.generate(body.get('intent_ru'),body.get('selected_context',''),body.get('mode','translate'),on_usage=observe_usage,conversation=body.get('conversation'),personal_context=profile['text'])
    if body.get('mode')=='reply' and personal_context.read()['revision']!=profile['revision']:raise TextError('Контекст обо мне изменён. Прежняя подсказка не показана; автоматического повтора нет.')
    return self.send(200,result)
   if self.path=='/api/text-mock':
    if body.get('intent_ru')!='Повторите, пожалуйста, немного медленнее.':raise TextError('Mock принимает только явно показанную публичную фикстуру.')
    with tempfile.TemporaryDirectory() as d:
     fake=TextAdapter(NoSecretMockStore(),Ledger(Path(d)/'mock-budget.json'),TextConsent('openai',MODEL,.05),mock_transport)
     result=fake.generate(body['intent_ru'],'',body.get('mode','translate'));result.update(provider_result=False,mock=True)
    return self.send(200,result)
   if self.path=='/api/capture/prepare':
    with lock:
     consent=capture_consent()
     if consent is None:raise CaptureError('Отдельное capture-разрешение ещё не согласовано.')
     if audio.running:raise CaptureError('Capture translation уже работает.')
     if receiver and receiver.listener:raise CaptureError('Локальный приёмник уже ожидает helper.')
     monitor=PCMConsumer(consent);monitor.touch();receiver=NativeReceiver(ROOT/'runtime/audio.sock',monitor);receiver.start()
     def drain():
      # Discard audio in RAM after level measurement; no cloud, audio file or transcript.
      target=monitor
      while not target.stop.is_set():target.next_frame()
     threading.Thread(target=drain,daemon=True).start()
    return self.send(200,{'ok':True,'cloud':False,'source':consent.source})
   if self.path=='/api/capture/stop':
    if receiver:receiver.stop()
    audio.stop()
    return self.send(200,{'ok':True})
   raise TextError('Этот слой не запускает старый платный аудиопилот.')
  except (TextError,CaptureError,PersonalContextError) as error:return self.send(400,{'error':str(error)})
  except Exception:return self.send(400,{'error':'Локальное действие не завершилось. Секреты/сырой ответ не выводятся.'})
class Server(ThreadingHTTPServer):
 def handle_error(self,*args):pass

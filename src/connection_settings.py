"""Persist the user's configured source/provider consent and financial limits.
No credentials or auto-start. Unknown/new provider identity requires new opt-in.
"""
import json,math,threading
from pathlib import Path
from capture_runtime import CaptureError
from text_provider import MODEL
from session_policy import session_grant
from capture_policy import PRICE_PER_MINUTE
DEFAULTS={'version':1,'source':'zoom','provider':'openai','translation_model':'gpt-realtime-translate','text_model':MODEL,'capture_allowed':False,'cloud_allowed':False,'text_allowed':False,'auto_suggestions':True,'context_for_thought':False,'microphone':False,'audio_budget_usd':1.13,'text_budget_usd':.50,'budget_confirmed':False,'spending_mode':'limited','unlimited_spend_approved':False}
class ConnectionSettings:
 def __init__(self,path):self.path=Path(path);self.lock=threading.RLock()
 def read(self):
  try:
   data=json.loads(self.path.read_text())
   if any(data.get(k)!=DEFAULTS[k] for k in ('version','source','provider','translation_model','text_model')):return dict(DEFAULTS)
   return {**DEFAULTS,**data}
  except (OSError,ValueError,TypeError):return dict(DEFAULTS)
 def save(self,value):
  if not isinstance(value,dict):raise CaptureError('Неверные настройки подключения.')
  result={**DEFAULTS,**{k:value[k] for k in DEFAULTS if k in value}}
  if any(result[k]!=DEFAULTS[k] for k in ('version','source','provider','translation_model','text_model')):raise CaptureError('Смена источника или провайдера требует отдельного подключения.')
  for k in ('capture_allowed','cloud_allowed','text_allowed','auto_suggestions','context_for_thought','microphone','budget_confirmed','unlimited_spend_approved'):
   if not isinstance(result[k],bool):raise CaptureError('Неверное согласие.')
  if result['spending_mode'] not in ('limited','unlimited') or (result['spending_mode']=='unlimited' and not result['unlimited_spend_approved']):raise CaptureError('Режим без денежных пределов требует явного выбора пользователя.')
  if result['microphone']:raise CaptureError('Микрофон пока не реализован; разрешение не запрашивалось.')
  for k,maximum in (('audio_budget_usd',10),('text_budget_usd',2)):
   amount=result[k]
   if isinstance(amount,bool) or not isinstance(amount,(int,float)) or not math.isfinite(amount) or not .05<=amount<=maximum:raise CaptureError('Неверный предел расходов.')
  self.path.parent.mkdir(parents=True,exist_ok=True)
  with self.lock:
   tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False));tmp.chmod(0o600);tmp.replace(self.path)
  return result
 def ready(self):
  value=self.read();return all(value[k] is True for k in ('capture_allowed','cloud_allowed')) and (value['budget_confirmed'] is True or (value['spending_mode']=='unlimited' and value['unlimited_spend_approved'] is True))
 def grant(self):
  if not self.ready():raise CaptureError('Откройте настройки подключения и сохраните предел расходов. Выбор длительности не нужен.')
  value=self.read()
  return {'spending_mode':value['spending_mode'],'unlimited_spend_approved':value['unlimited_spend_approved'],'resume_audio':True,'capture_zoom_output':True,'upload_to_openai':True,'confirmed_budget':True,'microphone':False,'screen':False,'audio_budget_usd':value['audio_budget_usd'],'text_budget_usd':value['text_budget_usd'] if value['text_allowed'] else 0,'upload_typed_intent':value['text_allowed'],'allow_context':value['text_allowed'] and (value['auto_suggestions'] or value['context_for_thought']),'upload_context':value['text_allowed'] and (value['auto_suggestions'] or value['context_for_thought']),'until_stop':True}

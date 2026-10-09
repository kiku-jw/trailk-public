"""Only a deliberate in-app per-session confirmation can create an ephemeral grant.
No credentials, microphone, screen or automatic reconnection. No runtime approval files.
"""
import time,uuid,math
from capture_policy import cloud_consent,PRICE_PER_MINUTE,TECHNICAL_MAX_SECONDS
from capture_runtime import CaptureError
from text_provider import TextConsent,MODEL

def session_grant(value,now=None):
 now=time.time() if now is None else now
 unlimited=isinstance(value,dict) and value.get('spending_mode')=='unlimited' and value.get('unlimited_spend_approved') is True
 if not isinstance(value,dict) or any(value.get(k) is not True for k in ('resume_audio','capture_zoom_output','upload_to_openai')) or (not unlimited and value.get('confirmed_budget') is not True):raise CaptureError('Для этой сессии нужны отдельные согласия на звук Zoom, передачу OpenAI и бюджет.')
 if value.get('microphone') is not False or value.get('screen') is not False:raise CaptureError('Микрофон и экран не входят в этот режим.')
 minutes=value.get('minutes');budget=value.get('audio_budget_usd');text_budget=value.get('text_budget_usd',0)
 until_stop=value.get('until_stop') is True
 if until_stop and not unlimited:minutes=budget/PRICE_PER_MINUTE if isinstance(budget,(int,float)) and not isinstance(budget,bool) else None
 if unlimited:
  if not until_stop:raise CaptureError('Режим без денежных пределов требует явного Stop и технического завершения.')
  minutes=TECHNICAL_MAX_SECONDS/60;budget=0;text_budget=0 if value.get('upload_typed_intent') is not True else 1
 for number in (minutes,budget,text_budget):
  if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(number):raise CaptureError('Неверная длительность или бюджет.')
 if not unlimited and ((not until_stop and not 1<=minutes<=90) or not .05<=budget<=10 or not minutes*PRICE_PER_MINUTE<=budget+1e-9 or not 0<=text_budget<=2):raise CaptureError('Нужны допустимые денежные пределы; бесконечные расходы не разрешены.')
 if text_budget and (text_budget<.05 or value.get('upload_typed_intent') is not True):raise CaptureError('Перевод вашей мысли требует отдельного согласия и бюджета.')
 if value.get('allow_context') is True and (not text_budget or value.get('upload_context') is not True):raise CaptureError('Контекст нужно разрешить отдельно.')
 identifier=str(uuid.uuid4());expiry=now+minutes*60+120
 native={'approved':True,'source':'zoom','schema_version':4 if unlimited else 3 if until_stop else 2,'approval_id':identifier,'maximum_seconds':minutes*60,'expires_unix':expiry,'capture_scope':'zoom_output','private_call_capture':True,'microphone':False,'resume_audio':True,'until_stop':until_stop}
 cloud={'approved':True,'source':'zoom','schema_version':4 if unlimited else 3 if until_stop else 2,'approval_id':identifier,'maximum_seconds':minutes*60,'expires_unix':expiry,'capture_scope':'zoom_output','private_call_upload':True,'persist_transcript':False,'provider':'openai','budget_usd':budget}
 if unlimited:
  native['unlimited_spend_approved']=True;cloud.update(unlimited_spend_approved=True,budget_usd=None)
 consent=cloud_consent(native,cloud,now)
 if consent is None:raise CaptureError('Согласие на сессию не прошло проверку.')
 text=TextConsent('openai',MODEL,text_budget,value.get('allow_context') is True,'estimated_v1',unlimited) if text_budget else None
 return {'id':identifier,'native':native,'cloud':cloud,'consent':consent,'text':text,'resume_audio':True,'until_stop':until_stop}

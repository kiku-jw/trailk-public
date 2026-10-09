"""Future approval parser only: never creates approvals or removes the audio STOP."""
import math,time
from capture_runtime import CaptureConsent
TECHNICAL_MAX_SECONDS=21600 # Six-hour technical session lifecycle, never a monetary cap.
MAX_SECONDS=5400 # legacy approval only
PRICE_PER_MINUTE=.034  # Official model price checked 2026-10-03; estimate, not billing.
MAX_BUDGET_SECONDS=10/PRICE_PER_MINUTE*60
def native_consent(value,now=None):
 now=time.time() if now is None else now
 if value.get('approved') is not True:return None
 if value.get('source')=='public_sample':return CaptureConsent('public_sample',150,False)
 if value.get('source')!='zoom':return None
 duration=value.get('maximum_seconds');expiry=value.get('expires_unix')
 unlimited=value.get('schema_version')==4 and value.get('unlimited_spend_approved') is True and value.get('until_stop') is True
 if not isinstance(duration,(int,float)) or isinstance(duration,bool) or not math.isfinite(duration) or not 0<duration<=(TECHNICAL_MAX_SECONDS if unlimited else MAX_BUDGET_SECONDS if value.get('schema_version')==3 else MAX_SECONDS):return None
 if not isinstance(expiry,(int,float)) or not now<expiry<=now+86400:return None
 if value.get('schema_version') not in (2,3,4) or (value.get('schema_version')==4 and not unlimited) or not isinstance(value.get('approval_id'),str) or not value['approval_id'].strip():return None
 if value.get('capture_scope')!='zoom_output' or value.get('private_call_capture') is not True or value.get('microphone') is not False:return None
 return CaptureConsent('zoom',duration,False,0)
def cloud_consent(native,cloud,now=None):
 consent=native_consent(native,now)
 if not consent or cloud.get('approved') is not True or cloud.get('source')!=consent.source or cloud.get('provider')!='openai':return None
 if consent.source=='public_sample':return CaptureConsent('public_sample',150,True) if cloud.get('maximum_seconds')==150 else None
 budget=cloud.get('budget_usd');expiry=cloud.get('expires_unix');now=time.time() if now is None else now
 if cloud.get('schema_version')!=native.get('schema_version') or cloud.get('approval_id')!=native['approval_id'] or cloud.get('maximum_seconds')!=consent.maximum_seconds:return None
 if not isinstance(expiry,(int,float)) or not now<expiry<=native['expires_unix']:return None
 if cloud.get('private_call_upload') is not True or cloud.get('capture_scope')!='zoom_output' or cloud.get('persist_transcript') is not False:return None
 if native.get('schema_version')==4:
  if cloud.get('unlimited_spend_approved') is not True or budget is not None:return None
  return CaptureConsent('zoom',consent.maximum_seconds,True,0,0,False,True)
 if not isinstance(budget,(int,float)) or isinstance(budget,bool) or not math.isfinite(budget) or not (consent.maximum_seconds/60*PRICE_PER_MINUTE<=budget+1e-9 and budget<=10):return None
 if native.get('schema_version')==3 and (native.get('until_stop') is not True or abs(consent.maximum_seconds-budget/PRICE_PER_MINUTE*60)>.001):return None
 return CaptureConsent('zoom',consent.maximum_seconds,True,0,budget,native.get('schema_version')==3)

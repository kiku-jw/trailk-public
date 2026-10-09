"""Approved estimated reserve, never an invoice guarantee or exact token count."""
import json,math
from datetime import date
MODEL='gpt-5.4-mini-2026-03-17'
MAX_INPUT_BYTES=8192
MAX_PROFILE_INPUT_BYTES=16384
MAX_OUTPUT_TOKENS=512
FRAMING_PAD=512
MARGIN=1.25
INPUT_PER_MILLION=.75
OUTPUT_PER_MILLION=4.5
CHECKED_ON='2026-10-04'
VALID_THROUGH='2026-11-04'
def wire_bytes(body):return json.dumps(body,ensure_ascii=False,separators=(',',':')).encode('utf-8')
def reserve_for_size(size):
 return math.ceil(((size+FRAMING_PAD)*INPUT_PER_MILLION+MAX_OUTPUT_TOKENS*OUTPUT_PER_MILLION)/1000000*MARGIN*1000000)/1000000
def price_known(provider,model,today=None):
 day=today or date.today()
 return provider=='openai' and model==MODEL and date.fromisoformat(CHECKED_ON)<=day<=date.fromisoformat(VALID_THROUGH)
def policy(provider='openai',model=MODEL,today=None,personal_context_enabled=False):
 ceiling=MAX_PROFILE_INPUT_BYTES if personal_context_enabled else MAX_INPUT_BYTES
 return {'kind':'estimated_v1','price_known':price_known(provider,model,today),'model':model,'minimum_reservation_usd':reserve_for_size(0),'maximum_reservation_usd':reserve_for_size(ceiling),'maximum_input_bytes':ceiling,'maximum_output_tokens':MAX_OUTPUT_TOKENS,'framing_pad_tokens':FRAMING_PAD,'margin':MARGIN,'uncached_input_per_million_usd':INPUT_PER_MILLION,'output_per_million_usd':OUTPUT_PER_MILLION,'checked_on':CHECKED_ON,'valid_through':VALID_THROUGH,'actual_billing':'unknown','invoice_guarantee':False}
def forecast(body,provider,model,today=None):
 if not price_known(provider,model,today):raise ValueError('Цена модели не подтверждена; запрос не отправлен.')
 profile_enabled=False
 try:
  data=json.loads(body.get('input',''))
  profile_enabled=data.get('mode')=='reply' and bool(data.get('personal_context',{}).get('text'))
 except (ValueError,TypeError,AttributeError):pass
 size=len(wire_bytes(body))
 ceiling=MAX_PROFILE_INPUT_BYTES if profile_enabled else MAX_INPUT_BYTES
 if size>ceiling:raise ValueError('Полный запрос слишком большой для оценочного бюджета. Сократите мысль или контекст.')
 if body.get('max_output_tokens')!=MAX_OUTPUT_TOKENS:raise ValueError('Неизвестный предел ответа; запрос не отправлен.')
 details=policy(provider,model,today,profile_enabled);details.update({'input_wire_bytes':size,'input_token_proxy':size+FRAMING_PAD,'reserved_usd':reserve_for_size(size)})
 return details

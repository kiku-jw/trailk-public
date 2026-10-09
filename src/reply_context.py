"""Explicit reply target; local lexical guard supplements (never replaces) neutrality.
No model/credential calls. Latest is never tail-truncated. Prior is only reference data.
"""
import re
from reply_readiness import continuation_reason
OWN={'spoken':'unknown','selected_draft_is_speech':False}
class ReplyContextError(ValueError):pass
def segment(text,revision):
 return {'text':text,'segment_revision':revision,'source':'remote_translation','speaker':'unknown','finality':'app_segment_only'}
def build(context):
 lines=[re.sub(r'^Собеседники:\s*','',s).strip() for s in context.splitlines() if s.strip()]
 latest=segment(lines[-1],len(lines));prior=[];remaining=min(800,2400-len(lines[-1]))
 for i in range(len(lines)-2,max(-1,len(lines)-4),-1):
  if len(lines[i])>remaining:break
  prior.insert(0,segment(lines[i],i+1));remaining-=len(lines[i])
 return {'version':1,'latest_interlocutor_utterance':latest,'prior_context':prior,'own_response_state':dict(OWN)}
def validate(value):
 if not isinstance(value,dict) or set(value)!={'version','latest_interlocutor_utterance','prior_context','own_response_state'} or type(value['version']) is not int or value['version']!=1 or value['own_response_state']!=OWN:raise ReplyContextError('Неверная структура контекста; собственная речь неизвестна.')
 latest=value['latest_interlocutor_utterance'];prior=value['prior_context']
 if not isinstance(prior,list) or len(prior)>2:raise ReplyContextError('Слишком длинная предыстория.')
 for item in [latest,*prior]:
  if not isinstance(item,dict) or set(item)!={'text','segment_revision','source','speaker','finality'}:raise ReplyContextError('Неверная реплика.')
  if not isinstance(item['text'],str) or not item['text'].strip() or len(item['text'])>2400:raise ReplyContextError('Последняя реплика пуста или слишком длинна; она не обрезается.')
  if isinstance(item['segment_revision'],bool) or not isinstance(item['segment_revision'],int) or item['segment_revision']<1 or item['source']!='remote_translation' or item['speaker']!='unknown' or item['finality']!='app_segment_only':raise ReplyContextError('Нет надёжных данных о говорящем или завершённости.')
 if sum(len(i['text']) for i in prior)>800 or sum(len(i['text']) for i in [latest,*prior])>2400:raise ReplyContextError('Слишком длинный полный контекст.')
 if any(i['segment_revision']>=latest['segment_revision'] for i in prior):raise ReplyContextError('Предыстория не предшествует последней реплике.')
 return value

def for_provider(value):
 latest=value['latest_interlocutor_utterance']['text'];words=re.findall(r'\w+',latest)
 # Short elliptical follow-ups need an antecedent; a standalone full question does not.
 reference=len(words)<=3 or bool(re.match(r'^(а |и |нет[, ]|это |тогда |или )',latest.lower())) or bool(re.search(r'\b(это|этот|эту|эта|эти|его|её|ее|их|там|мне)\b|от меня|вам.*нужно|нужно.*вам',latest.lower()))
 return {**value,'prior_context':value['prior_context'][-1:] if reference else []}
STOP=set('я мы вы ты он она они мне нам вам тебе его ее им нас вас наш ваш это то ли же бы пожалуйста можете можно какой какая какое какие как что'.split())
def terms(text):
 text=text.lower().replace('ё','е');text=re.sub(r'во\s+сколько','когда',text)
 text=re.sub(r'^(?:пожалуйста[, ]+)?(?:можете\s+)?(?:уточните|подтвердите|поясните|скажите)[, ]+','',text)
 out=set()
 for token in re.findall(r'\d+(?:[.,]\d+)?|[а-яa-z]+',text):
  if token in STOP or token=='сюда':continue
  if token[0].isdigit():out.add(token.replace(',','.'));continue
  if token.startswith(('уезж','уех','отъез')):token='отъезд'
  if token.startswith(('улучш','лучш')):token='лучше'
  if token.startswith(('меньш','поменьш','небольш')):token='малый'
  out.add(token[:4] if len(token)>4 else token)
 if 'лучш' in out:out.discard('сдел') # 'make better' and 'improve' express the same question.
 return out

def resembles(a,b):
 left,right=terms(a),terms(b)
 return bool(left and right and len(left&right)/len(left|right)>=.7)
def reject_reason(pair,conversation,allow_position=False):
 latest=conversation['latest_interlocutor_utterance']['text']
 # A question can presuppose an unobserved fault despite satisfying neutral syntax.
 if not allow_position and re.search(r'пропада|обрыва|заика|помех',pair['ru'].lower()) and not re.search(r'если|в случае',pair['ru'].lower()):
  if not re.search(r'пропада|обрыва|заика|помех',latest.lower()):return 'unobserved_audio_fault'
 if resembles(pair['ru'],latest) and (not allow_position or (pair['en'].rstrip().endswith('?') and pair['ru'].rstrip().endswith('?'))):return 'echo_of_latest'
 for item in conversation['prior_context']:
  candidate,old,current=terms(pair['ru']),terms(item['text']),terms(latest)
  prior_only=bool(len(candidate)>=2 and len(candidate&old)/len(candidate)>=.8 and len(candidate&current)/len(candidate)<.25)
  if (resembles(pair['ru'],item['text']) or prior_only) and not resembles(item['text'],latest):return 'repeat_of_prior_topic'
 return None

def ordered(options):
 """Prefer explicit referent/detail clarification over bare provider order.
 Stable lexical preference only; no claims of semantic certainty or user selection.
 """
 def score(pair):
  text=pair['ru'].lower()
  if re.search(r'речь|имеете.*в виду|о каком|о какой|кака[яи].*именно|какой.*именно',text):return 3
  if re.search(r'повтор|объяс|пояс',text):return 2
  if re.search(r'требован|услови|огранич|критери|вариант|точн',text):return 1
  return 0
 return sorted(options,key=lambda pair:-score(pair))

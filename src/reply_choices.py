"""Version 2: explicit possible user positions, never an assertion by the app.
No automatic choice/speech. Conservative lexical fact boundaries are not semantic proof.
"""
import re
KINDS=('positive','negative','clarify','uncertain')
LABELS={'positive':'Да / подходит','negative':'Нет / не подходит','clarify':'Уточнить','uncertain':'Не знаю / проверить'}
def policy(conversation,supplied_profile=''):
 text=conversation['latest_interlocutor_utterance']['text'].lower()
 factual=bool(re.search(r'\d|цен|стоим|доллар|евро|рубл|сколько|номер|цифр|кто|чей|автор|дата|срок|когда|во сколько|где|адрес|родил|работал|жив[её]те|уже.*(отправ|сдела|оплат)|включена|включено|входит.*достав',text))
 # An offered action/subjective preference is a choice, not a guessed factual answer.
 proposal=bool(re.search(r'давайте|предлага|хотите|можем|соглас|подойд|лучше|перерыв|вам нравится|предпочитаете|меня.*слыш|слышите.*меня',text))
 financial=bool(re.search(r'оплат|заплат|купить|покуп|перевести.*деньг',text))
 category='unknown_fact' if (factual and not proposal) or financial else 'position_choice'
 return {'version':2,'manual_choice_only':True,'topic_policy':category,'allowed_kinds':['clarify','uncertain'] if category=='unknown_fact' and not supplied_profile else list(KINDS),'concrete_facts_must_not_be_invented':True}
def literal_supplied_fact(ru,profile):
 normalize=lambda s:' '.join(re.findall(r'[\w]+',s.lower()))
 claim=normalize(ru)
 return bool(profile and len(claim.split())>=3 and any(claim==normalize(s) for s in re.split(r'[.!?;\n]',profile) if s.strip()))
def reject_reason(pair,conversation,supplied_profile=''):
 kind=pair['kind'];en=pair['en'].lower();ru=pair['ru'].lower();latest=conversation['latest_interlocutor_utterance']['text']
 supplied=literal_supplied_fact(pair['ru'],supplied_profile)
 if kind in ('positive','negative') and not supplied:
  listener=re.search(r"\b(?:yes|no|sure|certainly|thanks|thank you|i|we|let['’]s)\b|(?:works?|fine|okay|good|suitable) for (?:me|us)|sounds (?:good|fine|great|nice|reasonable)|^(?:that (?:works|is fine|sounds|makes sense))",en)
  perception=re.search(r'слыш|звук|аудио',latest.lower()) and re.search(r'\b(?:sound|audio|hear)\b',en)
  if not listener and not perception:return 'factual_statement_without_listener_position'
  if re.search(r"\bi(?: am|['’]m) (?:an? |the )",en) and not re.search(r"\bi(?: am|['’]m) a (?:little|bit)\b",en):return 'unsupplied_personal_identity'
 if kind=='uncertain':
  uncertainty=r"(?:\bi (?:am |['’]m )?not sure|\bi (?:don['’]t|do not) know|\b(?:i |we |let me |let us )?(?:need to|have to|should|must) (?:check|confirm|think)|\bi (?:need|would like) (?:more|some|a little)|\b(?:let me|let us) (?:check|confirm|think|make sure)|\bi cannot (?:confirm|tell)|\bне (?:уверен|знаю|могу подтвердить)|(?:мне|нам|нужно|надо|дайте).*?(?:провер|уточн|подум|контекст))"
  if not re.search(uncertainty,en+' '+ru):return 'uncertainty_label_without_uncertainty'
 if kind=='clarify' and not (en.endswith('?') or ru.endswith('?') or re.search(r'^(?:please|could|can|would|will|let me)|^(?:пожалуйста|можете|дайте|уточните|скажите|объясните|поясните|повторите|пришлите)',en) or re.search(r'^(?:пожалуйста|можете|дайте|уточните|скажите|объясните|поясните|повторите|пришлите)',ru)):return 'clarification_label_without_request'
 if policy(conversation)['topic_policy']=='unknown_fact' and kind in ('positive','negative') and not supplied:return 'unknown_fact_cannot_be_chosen_by_model'
 if kind not in policy(conversation,supplied_profile)['allowed_kinds']:return 'unknown_fact_cannot_be_chosen_by_model'
 # No guessed concrete amounts, clocks, dates, biographical facts or payment promises.
 concrete=bool(re.search(r'\d|\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|dollars?|euros?|pounds?|at noon|at midnight)\b|\bat (?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|thirty|forty|fifty) (?:minutes?|hours?|years?|dollars?)\b|born|i live in|i work at|i used to work|i have worked|i graduated|родил|я живу|я работаю|я работал|я окончил',en+' '+ru))
 if concrete and not supplied and not (kind=='clarify' and en.rstrip().endswith('?')):return 'invented_concrete_fact'
 if re.search(r"\b(i will|i'll|i’m ready to|i am ready to)\s+(pay|send|finish|deliver|arrive)|я (оплачу|заплачу|переведу|обещаю)|готов.*(плат|оплат)",en+' '+ru):return 'invented_promise_or_payment'
 if supplied_profile and not supplied and re.search(r'\bi (believe|worship|pray)|my (faith|religion) (requires|forbids|teaches)|я (верю|поклоняюсь)|моя (вера|религия) (требует|запрещает|учит)',en+' '+ru):return 'unstated_specific_view'
 if kind=='clarify':
  source_numbers=set(re.findall(r'\d+(?:[.,]\d+)?',latest))
  candidate_numbers=set(re.findall(r'\d+(?:[.,]\d+)?',pair['ru']))
  if not {n.replace(',','.') for n in candidate_numbers}<={n.replace(',','.') for n in source_numbers}:return 'new_concrete_number'
 return None

def ordered(options):
 # The order presents distinct positions, it does not select a true one.
 order={'positive':0,'negative':1,'uncertain':2,'clarify':3}
 return sorted(options,key=lambda p:order[p['kind']])

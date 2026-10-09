"""Held-out crafted response fixtures verify guards/contracts, NOT model quality."""
import unittest,sys,json,tempfile,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
import reply_context as ctx
from text_provider import TextAdapter,TextConsent,Ledger,MODEL,TextError,validate_result
# Different domains and sentence forms; fixed BEFORE the new paid qualification.
HELD_OUT=[
 ('Где?','Когда уезжаем?','Где?','Какое место вы имеете в виду?'),
 ('Что вы имеете в виду?','Билет стоит 35?','Что вы имеете в виду?','Можете привести конкретный пример?'),
 ('Вы уже отправили файл?','Куда ехать?','Вы уже отправили файл?','О каком файле идёт речь?'),
 ('Можно перенести встречу?','Сколько стоит билет?','Можно перенести встречу?','На какую дату вы предлагаете её перенести?'),
 ('Пять или пятнадцать участников?','Когда уезжаем?','Пять или пятнадцать участников?','Сколько мест доступно в комнате?'),
 ('Почему экран пустой?','Вы готовы?','Почему экран пустой?','Какое приложение сейчас открыто?'),
 ('Вы согласны с решением?','Цена 3.5 или 35?','Вы согласны с решением?','Какие аргументы стоит учесть перед решением?'),
 ('Как долго это займёт?','Какое место?','Как долго это займёт?','Какие этапы входят в эту задачу?'),
 ('Это безопасно?','Выход рядом с лестницей.','Это безопасно?','Какой риск вас беспокоит?'),
 ('Во сколько нужно прийти?','Сколько страниц читать?','Когда нужно прийти?','Есть ли обязательное время регистрации?'),
 ('Какая сумма верная?','Когда нам уезжать?','Какая сумма верная?','Что включено в эту стоимость?'),
 ('Завтра?','Нет, когда нам уезжать?','Завтра?','Вы имеете в виду завтрашнее утро или вечер?'),
]
class Store:
 def __init__(self):self.reads=0
 def load_for_application(self):self.reads+=1;return 'DUMMY'
class ContextTests(unittest.TestCase):
 def test_held_out_echo_and_old_topic_removed_while_genuine_detail_survives(self):
  for latest,prior,echo,detail in HELD_OUT:
   with self.subTest(latest=latest):
    c=ctx.build('Собеседники: '+prior+'\nСобеседники: '+latest)
    value={'options':[{'en':'Could you clarify?','ru':echo},{'en':'What detail is needed?','ru':detail},{'en':'What was the previous topic?','ru':prior}]}
    value['options']=[{**p,'kind':'clarify'} for p in value['options']];result=validate_result(json.dumps(value),'reply',True,c)
    self.assertEqual([p['ru'] for p in result['options']],[detail])
 def test_exact_last_reply_is_not_lost_in_flat_history_or_selected_state(self):
  c=ctx.build('Собеседники: Когда нам уезжать?\nСобеседники: Нет, то есть, когда нам уезжать?\nСобеседники: Завтра?\nСобеседники: Билет стоит 3,5 или 35 долларов?')
  self.assertEqual(c['latest_interlocutor_utterance']['text'],'Билет стоит 3,5 или 35 долларов?')
  self.assertEqual(ctx.for_provider(c)['prior_context'],[])
  self.assertEqual(c['own_response_state'],ctx.OWN)
  bad={'en':'When are we leaving?','ru':'Когда мы уезжаем?'}
  self.assertEqual(ctx.reject_reason(bad,c),'repeat_of_prior_topic')
 def test_single_word_followup_has_reference_but_still_is_only_reply_target(self):
  c=ctx.build('Собеседники: Когда нам уезжать?\nСобеседники: Завтра?')
  self.assertEqual(ctx.for_provider(c)['latest_interlocutor_utterance']['text'],'Завтра?');self.assertEqual(len(ctx.for_provider(c)['prior_context']),1)
 def test_referential_full_question_keeps_only_immediate_antecedent(self):
  c=ctx.build('Билет стоит 35?\nСсылка не работает.\nЧто вам нужно от меня?')
  provider=ctx.for_provider(c);self.assertEqual([p['text'] for p in provider['prior_context']],['Ссылка не работает.'])
  self.assertNotIn('Билет',json.dumps(provider,ensure_ascii=False))
 def test_limits_no_latest_truncation_and_own_speech_cannot_be_invented(self):
  c=ctx.build('x'*2401)
  with self.assertRaises(ctx.ReplyContextError):ctx.validate(c)
  c=ctx.build('Где?');c['own_response_state']['spoken']='selected reply'
  with self.assertRaises(ctx.ReplyContextError):ctx.validate(c)
 def test_adapter_wire_separates_latest_and_prior_and_applies_filter_after_usage(self):
  with tempfile.TemporaryDirectory() as d:
   c=ctx.build('Когда нам уезжать?\nБилет стоит 3.5 или 35 долларов?');bodies=[];store=Store();seen=[]
   def transport(url,b,key):
    bodies.append(b);return {'status':'completed','usage':{'input_tokens':100,'output_tokens':50},'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'options':[{'en':'When are we leaving?','ru':'Когда мы уезжаем?','kind':'clarify'},{'en':'Does the price include taxes?','ru':'Включены ли налоги в цену?','kind':'clarify'}]})}]}]}
   a=TextAdapter(store,Ledger(Path(d)/'ledger'),TextConsent('openai',MODEL,.2,True,'estimated_v1'),transport)
   r=a.generate('',c['latest_interlocutor_utterance']['text'],'reply',on_usage=seen.append,conversation=c)
   wire=json.loads(bodies[0]['input']);self.assertEqual(wire['selected_context'],'Билет стоит 3.5 или 35 долларов?');self.assertEqual(wire['conversation']['prior_context'],[])
   self.assertEqual([p['en'] for p in r['options']],['Does the price include taxes?']);self.assertEqual(len(seen),1);self.assertEqual(r['metadata']['reply_context']['echo_or_prior_filtered'],1)
 def test_all_echo_rejection_keeps_spending_and_does_not_retry(self):
  with tempfile.TemporaryDirectory() as d:
   calls=[];store=Store();seen=[]
   def transport(*args):
    calls.append(1);return {'status':'completed','usage':{'input_tokens':100,'output_tokens':10},'output':[{'type':'message','content':[{'type':'output_text','text':'{"options":[{"en":"Where?","ru":"Где?","kind":"clarify"}]}'}]}]}
   a=TextAdapter(store,Ledger(Path(d)/'ledger'),TextConsent('openai',MODEL,.2,True,'estimated_v1'),transport)
   with self.assertRaises(TextError):a.generate('','Где?','reply',on_usage=seen.append)
   self.assertEqual(calls,[1]);self.assertEqual(len(seen),1);self.assertGreater(json.loads(a.ledger.path.read_text())['reserved_usd'],0)

class ClarificationOrderingTests(unittest.TestCase):
 def test_semantic_echo_wrappers_and_comparison_morphology(self):
  cases=[('Что небольшой формат сделал бы лучше?','Что бы улучшил меньший формат?'),('Включена ли сюда упаковка?','Уточните, включена ли упаковка.'),('Когда нам уезжать?','Подтвердите, во сколько мы уезжаем.')]
  for latest,echo in cases:
   with self.subTest(latest=latest):self.assertEqual(ctx.reject_reason({'en':'Clarify?','ru':echo},ctx.build(latest)),'echo_of_latest')
 def test_unobserved_audio_fault_not_inferred_from_quality_question(self):
  pair={'en':'Which part is dropping out?','ru':'Какая часть звука пропадает?'}
  self.assertEqual(ctx.reject_reason(pair,ctx.build('Звук хорошо слышен?')),'unobserved_audio_fault')
  self.assertIsNone(ctx.reject_reason(pair,ctx.build('У меня пропадает звук.')))
  self.assertIsNone(ctx.reject_reason({'en':'What if it drops out?','ru':'Что делать, если звук пропадает?'},ctx.build('Звук хорошо слышен?')))
 def test_preference_uses_other_domains_and_preserves_pairs_not_user_selection(self):
  options=[{'en':'Is there another choice?','ru':'Есть ли другой выбор?'},{'en':'Please explain the condition.','ru':'Пожалуйста, объясните условие.'},{'en':'Which application do you mean?','ru':'О каком приложении речь?'}]
  self.assertEqual(ctx.ordered(options),[options[2],options[1],options[0]])

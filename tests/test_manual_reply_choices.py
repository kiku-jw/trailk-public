"""Explicit product-contract fixtures fixed before new API qualification."""
import sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
import reply_context as ctx
import reply_choices as choices
from text_provider import validate_result,TextError

def pair(en,ru,kind):return {'en':en,'ru':ru,'kind':kind}
def result(latest,options):return validate_result(json.dumps({'options':options}),'reply',True,ctx.build(latest))
class ManualChoiceContractTests(unittest.TestCase):
 def test_diverse_hearing_proposal_condition_and_refusal_have_real_positions(self):
  cases=[
   ('Вы меня слышите?',pair('Yes, I can hear you clearly.','Да, я вас хорошо слышу.','positive'),pair('The sound is breaking up.','Звук прерывается.','negative'),pair('Could you repeat that?','Можете повторить?','clarify')),
   ('Давайте сделаем перерыв?',pair('A break sounds good.','Перерыв звучит хорошо.','positive'),pair('I would rather keep going.','Я бы предпочёл продолжить.','negative'),pair('How long a break do you mean?','Какой длительности перерыв вы имеете в виду?','clarify')),
   ('Тогда давайте перейдём в онлайн.',pair('Online works for me.','Онлайн мне подходит.','positive'),pair('I would prefer to meet in person.','Я бы предпочёл встретиться лично.','negative'),pair('Which platform would we use?','Какую платформу мы будем использовать?','clarify')),
   ('Хотите присоединиться к обсуждению?',pair('Yes, I would like to join.','Да, я хотел бы присоединиться.','positive'),pair('Thank you, but I would rather pass.','Спасибо, но я бы предпочёл отказаться.','negative'),pair('What will you be discussing?','Что вы будете обсуждать?','clarify')),
  ]
  for latest,*options in cases:
   with self.subTest(latest=latest):
    r=result(latest,options);self.assertEqual([p['kind'] for p in r['options']],['positive','negative','clarify']);self.assertFalse(r['auto_selected']);self.assertTrue(r['manual_choice_only'])
 def test_unknown_fact_and_number_are_uncertainty_not_guessed_values(self):
  for latest in ['Цена 3,5 или 35 долларов?','Кто автор этой статьи?','Во сколько отправляется поезд?','Вы уже отправили файл?']:
   with self.subTest(latest=latest):
    r=result(latest,[pair('I need to check first.','Мне нужно сначала проверить.','uncertain'),pair('Could you point me to the source?','Можете указать источник?','clarify')]);self.assertEqual(len(r['options']),2)
    with self.assertRaises(TextError):result(latest,[pair('Yes, that is correct.','Да, это верно.','positive')])
 def test_biography_specific_time_payment_and_amount_never_invented(self):
  for en,ru in [('I live in London.','Я живу в Лондоне.'),('I can arrive at five.','Я могу приехать в пять.'),('I will pay tomorrow.','Я заплачу завтра.'),('It costs thirty dollars.','Это стоит тридцать долларов.')]:
   with self.subTest(en=en),self.assertRaises(TextError):result('Вам подходит этот вариант?',[pair(en,ru,'positive')])
 def test_short_followup_preserved_with_unknown_speech_and_no_echo(self):
  c=ctx.build('Вы имеете в виду место встречи?\nГде?');r=validate_result(json.dumps({'options':[pair('I am not sure which place you mean.','Я не уверен, какое место вы имеете в виду.','uncertain'),pair('Which place are you referring to?','О каком месте речь?','clarify')]}),'reply',True,c)
  self.assertEqual(len(r['options']),2);self.assertEqual(c['own_response_state'],ctx.OWN)
  with self.assertRaises(TextError):result('Где?',[pair('Where?','Где?','clarify')])
 def test_type_contract_and_no_auto_actions(self):
  c=ctx.build('Вы меня слышите?')
  for p in [pair('Yes.','Да.','automatic'),{'en':'Yes.','ru':'Да.','kind':'positive','send':True},{'en':'Yes.','ru':'Да.'}]:
   with self.assertRaises(TextError):validate_result(json.dumps({'options':[p]}),'reply',True,c)

class NonGrammaticalNeutralityTests(unittest.TestCase):
 def test_position_can_end_with_a_question_without_old_grammar_ban(self):
  r=result('Давайте попробуем?', [pair('Sure, shall we try it?','Конечно, попробуем?','positive')]);self.assertEqual(r['options'][0]['kind'],'positive');self.assertFalse(r['auto_selected'])

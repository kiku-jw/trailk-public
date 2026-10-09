import unittest,sys,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from reply_readiness import continuation_reason
import reply_context
from text_provider import TextAdapter,TextConsent,Ledger,TextError,MODEL,validate_result
class ReadinessTests(unittest.TestCase):
 def test_same_surface_contract_for_open_and_complete_forms(self):
  for s in ['Те из нас, кто принимает факел,','Стоимость включает:','Я соглашусь, если','Давайте обсудим (следующий шаг','Предлагаю —','I would agree if','The next step is…']:
   with self.subTest(s=s):self.assertIsNotNone(continuation_reason(s))
  for s in ['Вы меня слышите?','Где?','Когда?','Завтра?','Давайте сделаем перерыв','Нужно уточнить детали плана','Это «важно».']:
   with self.subTest(s=s):self.assertIsNone(continuation_reason(s))
 def test_incomplete_context_fails_before_key_reserve_and_transport(self):
  class Store:
   def load_for_application(self):raise AssertionError('No key access')
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'budget.json';a=TextAdapter(Store(),Ledger(p),TextConsent('openai',MODEL,.2,True,'estimated_v1'),lambda *args:self.fail('No transport'))
   for s in ['The next step is:','Предлагаю, если','Я хочу сказать (важное']:
    with self.subTest(s=s),self.assertRaises(TextError):a.generate('',s,'reply')
   self.assertFalse(p.exists())
 def test_synthetic_fragment_never_triggers_reply_and_complete_variant_filters_bad_claim(self):
  # Self-contained public regression fixture; never read local call/test reports.
  c=reply_context.build('Те из нас, кто принимает факел,')
  opts=[{'en':'I am an architect.','ru':'Я архитектор.','kind':'positive'},
        {'en':'Could you explain the next step?','ru':'Можете объяснить следующий шаг?','kind':'clarify'}]
  with self.assertRaises(TextError):validate_result(json.dumps({'options':opts}),'reply',True,c)
  complete=json.loads(json.dumps(c));complete['latest_interlocutor_utterance']['text']+=' продолжат эту работу.'
  v=validate_result(json.dumps({'options':opts}),'reply',True,complete);self.assertEqual(v['options'],[opts[1]]);self.assertFalse(v['auto_selected'])
 def test_declarative_fact_cannot_be_disguised_by_choice_label_across_topics(self):
  cases=[('uncertain','The director signed the contract.','Директор подписал договор.'),('uncertain','The guide lives in another town.','Гид живёт в другом городе.'),('clarify','The train has arrived.','Поезд прибыл.'),('positive','The chairperson is an engineer.','Председатель — инженер.'),('negative','The customer owns that building.','Заказчик владеет этим зданием.'),('positive','I am a surgeon.','Я хирург.'),('positive',"I'm an architect.",'Я архитектор.'),('positive','I’m a pilot.','Я пилот.')]
  for kind,en,ru in cases:
   with self.subTest(kind=kind,en=en),self.assertRaises(TextError):validate_result(json.dumps({'options':[{'kind':kind,'en':en,'ru':ru}]}),'reply',True,reply_context.build('Вам подходит этот вариант?'))
 def test_uncertainty_and_specific_clarification_survive_without_entity_blacklist(self):
  opts=[{'kind':'uncertain','en':'Let me check the details first.','ru':'Дайте мне сначала проверить детали.'},{'kind':'clarify','en':'Which part of the contract needs changing?','ru':'Какую часть договора нужно изменить?'}]
  v=validate_result(json.dumps({'options':opts}),'reply',True,reply_context.build('Нужно изменить этот договор.'));self.assertEqual(len(v['options']),2)

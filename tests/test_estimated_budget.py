import unittest,tempfile,json,sys
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
import text_budget
from text_provider import TextAdapter,TextConsent,Ledger,MODEL,TextError
class Store:
 def __init__(self):self.reads=0;self.provider='openai'
 def load_for_application(self):self.reads+=1;return 'DUMMY-NOT-A-CREDENTIAL'
class EstimatedBudgetTests(unittest.TestCase):
 def adapter(self,d,transport,limit=.5):
  self.store=Store();return TextAdapter(self.store,Ledger(Path(d)/'ledger.json'),TextConsent('openai',MODEL,limit,True,'estimated_v1'),transport)
 def response(self):return {'status':'completed','usage':{'input_tokens':200,'output_tokens':40},'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'options':[{'en':'What preparation is needed?','ru':'Какая подготовка нужна?','kind':'clarify'},{'en':'Please explain the next step.','ru':'Объясните следующий шаг.','kind':'clarify'}]})}]}]}
 def test_complete_wire_includes_instructions_schema_and_utf8_with_output_and_margin(self):
  body={'model':MODEL,'instructions':'all instructions','input':'Русский контекст 😀','max_output_tokens':512,'text':{'format':{'type':'json_schema','schema':{'description':'complete schema'}}}}
  forecast=text_budget.forecast(body,'openai',MODEL,date(2026,10,4));self.assertEqual(forecast['input_wire_bytes'],len(text_budget.wire_bytes(body)));self.assertIn('complete schema',text_budget.wire_bytes(body).decode());self.assertEqual(forecast['input_token_proxy'],len(text_budget.wire_bytes(body))+512);self.assertFalse(forecast['invoice_guarantee']);self.assertEqual(forecast['margin'],1.25)
 def test_unknown_or_expired_price_blocks(self):
  body={'max_output_tokens':512}
  for provider,model,day in [('openai','unknown',date(2026,10,4)),('omniroute',MODEL,date(2026,10,4)),('openai',MODEL,date(2026,11,5))]:
   with self.assertRaises(ValueError):text_budget.forecast(body,provider,model,day)
 def test_wire_ceiling_and_output_cap_block(self):
  for body in [{'input':'x'*8192,'max_output_tokens':512},{'max_output_tokens':1024}]:
   with self.assertRaises(ValueError):text_budget.forecast(body,'openai',MODEL,date(2026,10,4))
 def test_historical_reserve_stays_and_new_reserve_precedes_key_and_dispatch(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'ledger.json';path.write_text(json.dumps({'reserved_usd':.10,'requests':2,'actual_usage':'unknown'}));before=None
   def transport(url,body,key):
    data=json.loads(path.read_text());self.assertGreater(data['reserved_usd'],.10);self.assertEqual(data['requests'],3);self.assertEqual(body['max_output_tokens'],512);return self.response()
   adapter=self.adapter(d,transport);result=adapter.generate('','Вы готовы?','reply');data=json.loads(path.read_text());amount=result['metadata']['reservation']['reserved_usd'];self.assertAlmostEqual(data['reserved_usd'],.1+amount);self.assertLess(amount,.05);self.assertEqual(len(data['reservation_entries']),1);self.assertNotIn('Вы готовы',json.dumps(data));self.assertEqual(self.store.reads,1)
 def test_errors_retain_estimate_no_retry_no_usage_refund(self):
  with tempfile.TemporaryDirectory() as d:
   calls=[]
   def transport(*args):calls.append(1);raise TextError('network failure')
   adapter=self.adapter(d,transport)
   with self.assertRaises(TextError):adapter.generate('','Какой путь безопаснее?','reply')
   data=json.loads(adapter.ledger.path.read_text());self.assertGreater(data['reserved_usd'],0);self.assertLess(data['reserved_usd'],.05);self.assertEqual(calls,[1]);self.assertEqual(data['requests'],1)
 def test_oversized_complete_request_blocks_before_key_or_reserve(self):
  with tempfile.TemporaryDirectory() as d:
   adapter=self.adapter(d,lambda *args:self.fail('dispatch'))
   with self.assertRaises(TextError):adapter.generate('😀'*2500,'','translate')
   self.assertEqual(self.store.reads,0);self.assertFalse(adapter.ledger.path.exists())
 def test_insufficient_remaining_estimate_blocks_before_key_without_historical_mutation(self):
  with tempfile.TemporaryDirectory() as d:
   adapter=self.adapter(d,lambda *args:self.fail('dispatch'),.1);original='{"reserved_usd":0.099,"requests":2,"actual_usage":"unknown"}';adapter.ledger.path.write_text(original)
   with self.assertRaises(TextError):adapter.generate('','Вы готовы?','reply')
   self.assertEqual(adapter.ledger.path.read_text(),original);self.assertEqual(self.store.reads,0)
 def test_policy_minimum_and_maximum_are_consistent_and_not_billing(self):
  p=text_budget.policy(today=date(2026,10,4));self.assertEqual(p['maximum_reservation_usd'],.01104);self.assertEqual(p['minimum_reservation_usd'],.00336);self.assertEqual(p['actual_billing'],'unknown');self.assertFalse(p['invoice_guarantee'])

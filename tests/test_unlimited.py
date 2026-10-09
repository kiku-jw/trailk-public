import unittest,tempfile,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from connection_settings import ConnectionSettings,DEFAULTS
from session_policy import session_grant
from capture_policy import cloud_consent,native_consent,TECHNICAL_MAX_SECONDS
from capture_runtime import PCMConsumer,CHUNK,CaptureError
from text_provider import TextAdapter,Ledger,TextError
class UnlimitedTests(unittest.TestCase):
 def settings(self):return {**DEFAULTS,'capture_allowed':True,'cloud_allowed':True,'text_allowed':True,'spending_mode':'unlimited','unlimited_spend_approved':True}
 def grant(self):
  with tempfile.TemporaryDirectory() as d:
   s=ConnectionSettings(Path(d)/'settings.json');s.save(self.settings());return s.grant()
 def test_default_limited_stays_blocked_and_unlimited_requires_exact_opt_in(self):
  with tempfile.TemporaryDirectory() as d:
   s=ConnectionSettings(Path(d)/'settings.json');self.assertEqual(s.read()['spending_mode'],'limited');self.assertFalse(s.ready())
   with self.assertRaises(CaptureError):s.save({**self.settings(),'unlimited_spend_approved':False})
   v=s.save(self.settings());self.assertFalse(v['budget_confirmed']);self.assertTrue(s.ready());s.save({**v,'spending_mode':'limited','unlimited_spend_approved':False});self.assertFalse(s.ready())
 def test_unlimited_grant_is_ephemeral_and_source_bound_without_numeric_infinity(self):
  g=session_grant(self.grant(),now=1000);self.assertTrue(g['consent'].unlimited);self.assertTrue(g['text'].unlimited);self.assertEqual(g['consent'].maximum_seconds,TECHNICAL_MAX_SECONDS);self.assertIsNone(g['cloud']['budget_usd']);self.assertFalse(g['consent'].budget_limited);self.assertNotIn('Infinity',json.dumps(g['cloud']));self.assertFalse(g['native']['microphone']);self.assertNotEqual(g['id'],session_grant(self.grant(),now=1000)['id'])
 def test_scope_and_forged_unlimited_fail_closed(self):
  for field,value in [('unlimited_spend_approved',False),('upload_to_openai',False),('capture_zoom_output',False),('until_stop',False),('microphone',True)]:
   with self.subTest(field=field),self.assertRaises(CaptureError):session_grant({**self.grant(),field:value,'confirmed_budget':False},now=1000)
  g=session_grant(self.grant(),now=1000);self.assertIsNone(cloud_consent(g['native'],{**g['cloud'],'unlimited_spend_approved':False},1000));self.assertIsNone(native_consent({**g['native'],'unlimited_spend_approved':False},1000))
 def test_audio_crosses_previous_money_cap_but_keeps_manual_stop_and_technical_bound(self):
  g=session_grant(self.grant(),now=1000);now=[0.];c=PCMConsumer(g['consent'],clock=lambda:now[0]);c.start('zoom');c.cloud_bytes=1000000000;self.assertTrue(c.budget_allows_frame(CHUNK));now[0]=20000;c.touch();c.feed(bytes(CHUNK));self.assertTrue(c.running);c.next_frame(.001);now[0]=TECHNICAL_MAX_SECONDS;c.touch();c.feed(bytes(CHUNK));self.assertEqual(c.reason,'duration_limit');c.finish('manual_stop');self.assertEqual(c.reason,'duration_limit')
 def test_text_crosses_old_budget_keeps_estimated_reserve_and_one_request(self):
  class Store:
   def load_for_application(self):return 'DUMMY-NOT-A-CREDENTIAL'
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ledger.json';p.write_text('{"reserved_usd":100,"requests":1000}');calls=[]
   def transport(url,body,key):
    calls.append(body);self.assertEqual(body['max_output_tokens'],512);return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'{"options":[{"en":"Please repeat.","ru":"Повторите."}]}'}]}]}
   consent=session_grant(self.grant(),now=1000)['text'];a=TextAdapter(Store(),Ledger(p),consent,transport);a.generate('Повторите.');self.assertEqual(len(calls),1);v=json.loads(p.read_text());self.assertGreater(v['reserved_usd'],100);self.assertEqual(v['requests'],1001)
   from dataclasses import replace
   a.consent=replace(consent,unlimited=False)
   with self.assertRaises(TextError):a.generate('Повторите.')
   self.assertEqual(len(calls),1)

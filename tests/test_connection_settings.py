import unittest,sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from connection_settings import ConnectionSettings,DEFAULTS
from session_policy import session_grant
from text_provider import TextError,TextAdapter,TextConsent,Ledger,MODEL
from capture_runtime import CaptureError
class NoStore:
 def load_for_application(self):raise AssertionError('No secrets in settings/budget tests')
class SettingsTests(unittest.TestCase):
 def test_settings_off_until_user_confirms_budget_preserve_source_and_no_duration_picker(self):
  with tempfile.TemporaryDirectory() as d:
   s=ConnectionSettings(Path(d)/'settings.json');self.assertFalse(s.ready())
   value={**DEFAULTS,'capture_allowed':True,'cloud_allowed':True,'text_allowed':True,'budget_confirmed':True,'audio_budget_usd':5}
   s.save(value);self.assertTrue(s.ready());self.assertNotIn('minutes',s.grant());g=session_grant(s.grant());self.assertGreater(g['consent'].maximum_seconds,5400);self.assertTrue(g['consent'].budget_limited);self.assertEqual(g['consent'].budget_usd,5)
   again=ConnectionSettings(s.path);self.assertTrue(again.ready());self.assertEqual(again.grant()['audio_budget_usd'],5)
 def test_provider_change_mic_and_invalid_budget_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   s=ConnectionSettings(Path(d)/'settings.json')
   for k,v in [('provider','other'),('source','all_apps'),('microphone',True),('audio_budget_usd',11),('text_budget_usd',float('inf')),('cloud_allowed','yes')]:
    with self.subTest(k=k),self.assertRaises(CaptureError):s.save({**DEFAULTS,k:v})
   self.assertFalse(s.path.exists())
 def test_auto_reply_budget_and_context_checked_before_key_no_fabricated_input(self):
  with tempfile.TemporaryDirectory() as d:
   ledger=Ledger(Path(d)/'budget.json');ledger.reserve(.05)
   a=TextAdapter(NoStore(),ledger,TextConsent('openai',MODEL,.05,True))
   with self.assertRaises(TextError):a.generate('','Собеседники: Поясните пожалуйста ваш вопрос.','reply')
   b=TextAdapter(NoStore(),Ledger(Path(d)/'b.json'),TextConsent('openai',MODEL,.05,False))
   with self.assertRaises(TextError):b.generate('','Собеседники: Важная реплика.','reply')
   self.assertFalse((Path(d)/'b.json').exists())

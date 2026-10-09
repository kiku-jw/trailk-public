import unittest,sys,tempfile,json,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from session_policy import session_grant
from capture_runtime import CaptureError,PCMConsumer,CaptureConsent,CHUNK
from audio_integration import CaptureCloud
class NoStore:
 def load_for_application(self):raise AssertionError('No credential reads in tests')
def request():return {'resume_audio':True,'capture_zoom_output':True,'upload_to_openai':True,'confirmed_budget':True,'microphone':False,'screen':False,'minutes':30,'audio_budget_usd':1.13,'text_budget_usd':.50,'upload_typed_intent':True,'allow_context':False}
class SessionTests(unittest.TestCase):
 def test_complete_new_grant_is_ephemeral_source_bound_and_text_separate(self):
  grant=session_grant(request(),now=1000);self.assertEqual(grant['consent'].source,'zoom');self.assertEqual(grant['consent'].maximum_seconds,1800);self.assertFalse(grant['native']['microphone']);self.assertEqual(grant['text'].budget_usd,.50);self.assertFalse(grant['text'].allow_selected_context)
  other=session_grant(request(),now=1000);self.assertNotEqual(grant['id'],other['id'])
 def test_every_missing_consent_and_scope_budget_mismatch_fails_closed(self):
  for field,value in [('resume_audio',False),('capture_zoom_output',False),('upload_to_openai',False),('confirmed_budget',False),('microphone',True),('screen',True),('minutes',91),('minutes',0),('audio_budget_usd',.15),('text_budget_usd',.5),('allow_context',True)]:
   body=request();body[field]=value
   if field=='text_budget_usd':body['upload_typed_intent']=False
   with self.subTest(field=field),self.assertRaises(CaptureError):session_grant(body)
  for value in (float('nan'),float('inf'),True,'30'):
   with self.assertRaises(CaptureError):session_grant({**request(),'minutes':value})
 def test_current_stop_and_old_ledgers_survive_user_approved_new_session(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);protected={'AUDIO-DO-NOT-PLAY.json':'{"blocked":true}','CAPTURE-CLOUD-BUDGET.json':'{"reserved":true}','TEXT-BUDGET.json':'{"reserved_usd":0.10}','CAPTURE-APPROVAL.json':'{"approved":false}'}
   for name,content in protected.items():(root/name).write_text(content)
   a=CaptureCloud(root,NoStore())
   with self.assertRaises(CaptureError):a.start()
   with patch('audio_integration.NativeReceiver.start',side_effect=CaptureError('offline bind failure')):
    with self.assertRaises(CaptureError):a.start(request())
   for name,content in protected.items():self.assertEqual((root/name).read_text(),content)
   self.assertEqual(len(list((root/'session-budgets').glob('*-audio.json'))),1)
   self.assertFalse(a.available())
   with self.assertRaises(CaptureError):a.start()
   self.assertFalse((root/'CAPTURE-CLOUD-APPROVAL.json').exists())
 def test_repeat_click_while_running_cannot_create_another_grant(self):
  with tempfile.TemporaryDirectory() as d:
   a=CaptureCloud(d,NoStore());a.running=True
   with self.assertRaises(CaptureError):a.start(request())
   self.assertIsNone(a.session);self.assertFalse((Path(d)/'session-budgets').exists())
 def test_sound_pause_sound_without_mute_or_silence_stop(self):
  now=[0.];c=PCMConsumer(CaptureConsent('zoom',1800,True,0),clock=lambda:now[0]);c.start('zoom')
  sound=(1000).to_bytes(2,'little',signed=True)*4800
  c.touch();c.feed(sound);c.next_frame(.001);self.assertEqual(c.snapshot()['activity'],'sound')
  now[0]=1.;c.touch();c.feed(bytes(CHUNK));c.next_frame(.001);self.assertEqual(c.snapshot()['activity'],'pause');self.assertTrue(c.running)
  now[0]=120.;c.touch();c.feed(bytes(CHUNK));c.next_frame(.001);self.assertTrue(c.running)
  now[0]=120.2;c.touch();c.feed(sound);c.next_frame(.001);self.assertEqual(c.snapshot()['activity'],'sound');c.finish();c.finish();self.assertEqual(c.reason,'manual_stop')

 def test_actual_zoom_session_text_grant_uses_estimate_before_transport(self):
  from text_provider import TextAdapter,Ledger
  class FakeStore:
   def load_for_application(self):return 'DUMMY-NOT-A-CREDENTIAL'
  with tempfile.TemporaryDirectory() as d:
   grant=session_grant({**request(),'allow_context':True,'upload_context':True},now=1000)
   self.assertEqual(grant['text'].reservation_policy,'estimated_v1')
   path=Path(d)/'text.json';path.write_text('{"reserved_usd":0.1,"requests":2,"actual_usage":"unknown"}')
   def transport(url,body,key):
    self.assertEqual(body['max_output_tokens'],512);held=json.loads(path.read_text());self.assertGreater(held['reserved_usd'],.1);self.assertLess(held['reserved_usd'],.15)
    return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'options':[{'en':'Which path is safer?','ru':'Какой путь безопаснее?','kind':'clarify'},{'en':'Please explain the route.','ru':'Объясните маршрут.','kind':'clarify'}]})}]}]}
   adapter=TextAdapter(FakeStore(),Ledger(path),grant['text'],transport);result=adapter.generate('','Какой путь безопаснее?','reply');self.assertEqual(result['metadata']['reservation']['kind'],'estimated_v1');self.assertEqual(json.loads(path.read_text())['requests'],3)

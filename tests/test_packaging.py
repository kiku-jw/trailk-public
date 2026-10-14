import unittest, tempfile, sys, os, json, threading, urllib.request, urllib.error, subprocess
from pathlib import Path
SRC=Path(__file__).resolve().parents[1]/'src'
ASSETS=SRC.parent/'assets'
sys.path.insert(0,str(SRC))
from backend_entry import prepare_data

class PackagingTests(unittest.TestCase):
 def test_seed_is_locked_and_existing_decisions_and_budget_never_reset(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);prepare_data(root,ASSETS)
   self.assertEqual(json.loads((root/'TEXT-BUDGET.json').read_text())['reserved_usd'],0.0)
   self.assertFalse(json.loads((root/'CAPTURE-APPROVAL.json').read_text())['approved'])
   self.assertTrue((root/'AUDIO-DO-NOT-PLAY.json').is_file())
   (root/'TEXT-BUDGET.json').write_text('{"reserved_usd":0.2,"requests":4}')
   prepare_data(root,ASSETS)
   self.assertEqual(json.loads((root/'TEXT-BUDGET.json').read_text())['reserved_usd'],.2)

 def test_ui_has_no_browser_or_microphone_or_audio_dependency(self):
  html=(ASSETS/'web/index.html').read_text();js=(ASSETS/'web/app.js').read_text()
  self.assertNotIn('8767',html);self.assertNotIn('<audio',html)
  self.assertNotIn('getUserMedia',js);self.assertNotIn('speechSynthesis',js)
  self.assertIn('settings?.postMessage(',js);self.assertNotIn('localStorage',js)

 def test_packaged_capture_uses_own_data_and_stop_before_any_playback(self):
  main=(SRC/'main.swift').read_text();capture=(SRC/'capture/main.swift').read_text()
  self.assertNotIn('/Users/',capture)
  self.assertIn('CALM_DATA_ROOT',capture);self.assertIn('CALM_MANAGED_CHILD',capture)
  self.assertLess(capture.index('AUDIO-DO-NOT-PLAY.json'),capture.index('player?.play()'))
  gate=main[main.index('func openCapture('):main.index('func stopCapture()')]
  self.assertLess(gate.index('AUDIO-DO-NOT-PLAY.json'),gate.index('process.run()'))
  self.assertIn('decision["resume_audio"] as? Bool==true',gate)
  self.assertIn('decision["approved"] as? Bool==true',gate)

 def test_child_http_lockdown_paid_and_capture_blocked_then_parent_eof_exits(self):
  with tempfile.TemporaryDirectory() as d:
   env=dict(os.environ,CALM_DATA_ROOT=d,CALM_KEYCHAIN_BRIDGE='/nonexistent-bridge-must-not-be-called')
   child=subprocess.Popen([sys.executable,str(SRC/'backend_entry.py')],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   try:
    ready=json.loads(child.stdout.readline());base='http://127.0.0.1:'+str(ready['port'])
    def call(path,body=None,token=None,host=None):
     headers={'Host':host or '127.0.0.1:'+str(ready['port'])}
     if token:headers['X-Pilot-Token']=token
     if body is not None:headers['Content-Type']='application/json'
     req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
     try:
      with urllib.request.urlopen(req,timeout=3) as r:return r.status,json.load(r) if r.headers.get_content_type()=='application/json' else r.read()
     except urllib.error.HTTPError as e:
      with e:return e.code,json.load(e)
    status,state=call('/api/state?after=0');self.assertEqual(status,200)
    self.assertTrue(state['audio_blocked']);self.assertFalse(state['text_ready']);self.assertFalse(state['text_budget_exhausted'])
    self.assertFalse(state['capture_approved']);self.assertFalse(state['ready'])
    _,token=call('/api/token');token=token['token']
    self.assertEqual(call('/api/text',{'intent_ru':'Да','mode':'translate'},token)[0],400)
    self.assertEqual(call('/api/start',{},token)[0],400)
    self.assertEqual(call('/api/capture/prepare',{},token)[0],400)
    self.assertEqual(call('/api/text-mock',{'intent_ru':'Повторите, пожалуйста, немного медленнее.','mode':'suggest'},token)[0],200)
    self.assertEqual(call('/api/state?after=0',host='evil.example')[0],403)
    self.assertEqual(call('/api/text-mock',{},'wrong-token')[0],403)
    for path in ('/karaoke.js','/karaoke-model.js','/latency.js'):
     self.assertEqual(call(path)[0],200)
    self.assertEqual(state['hint_queue']['capacity'],1)
    self.assertEqual(state['hint_queue']['request_ms']['samples'],0)
    child.stdin.close();child.wait(timeout=5);self.assertEqual(child.returncode,0)
    with self.assertRaises(urllib.error.URLError):urllib.request.urlopen(base+'/api/token',timeout=1)
   finally:
    if child.poll() is None:child.kill();child.wait()
    child.stdout.close();child.stderr.close()

if __name__=='__main__':unittest.main()

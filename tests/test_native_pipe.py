import unittest,tempfile,socket,json,struct,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from capture_runtime import *
class PipeTests(unittest.TestCase):
 def run_pipe(self,source):
  with tempfile.TemporaryDirectory(prefix='calm-pipe-') as d:
   path=Path(d)/'a.sock';consumer=PCMConsumer(CaptureConsent('public_sample'));consumer.touch();receiver=NativeReceiver(path,consumer);receiver.start()
   self.assertEqual(path.stat().st_mode&0o777,0o600)
   client=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);client.connect(str(path))
   header={'source':source,'rate':24000,'channels':1,'encoding':'s16le'}
   try:client.sendall(json.dumps(header).encode()+b'\n'+struct.pack('<4800h',*([1000]*4800)))
   except BrokenPipeError:
    if source=='public_sample':raise
   finally:client.close()
   receiver.thread.join(2)
   self.assertFalse(receiver.thread.is_alive());self.assertFalse(path.exists());self.assertFalse(consumer.running)
   return consumer.snapshot()
 def test_synthetic_public_pcm_measured_then_socket_destroyed(self):
  result=self.run_pipe('public_sample');self.assertEqual(result['captured_seconds'],.2);self.assertEqual(result['peak'],1000);self.assertFalse(result['sent_to_cloud'])
 def test_zoom_not_accepted_under_public_only_consent(self):
  result=self.run_pipe('zoom');self.assertEqual(result['captured_seconds'],0);self.assertEqual(result['reason'],'invalid_source_or_local_pipe')

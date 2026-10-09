import unittest,sys,tempfile,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from audio_integration import CaptureCloud
from capture_runtime import CaptureError
class Store:
 def load_for_application(self):raise AssertionError('Must not read secret before consent')
class AudioIntegrationTests(unittest.TestCase):
 def test_missing_cloud_and_private_source_block_before_store_socket_ledger(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);a=CaptureCloud(root,Store())
   with self.assertRaises(CaptureError):a.start()
   (root/'CAPTURE-APPROVAL.json').write_text(json.dumps({'approved':True,'source':'zoom'}))
   (root/'CAPTURE-CLOUD-APPROVAL.json').write_text(json.dumps({'approved':True,'source':'zoom','provider':'openai','maximum_seconds':150}))
   with self.assertRaises(CaptureError):a.start()
   self.assertFalse((root/'CAPTURE-CLOUD-BUDGET.json').exists())
 def test_reserved_attempt_cannot_repeat_and_receiver_failure_does_not_load_key(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'CAPTURE-APPROVAL.json').write_text(json.dumps({'approved':True,'source':'public_sample'}));(root/'CAPTURE-CLOUD-APPROVAL.json').write_text(json.dumps({'approved':True,'source':'public_sample','provider':'openai','maximum_seconds':150}))
   a=CaptureCloud(root,Store())
   with patch('audio_integration.NativeReceiver.start',side_effect=CaptureError('mock bind failure')):
    with self.assertRaises(CaptureError):a.start()
   self.assertTrue((root/'CAPTURE-CLOUD-BUDGET.json').exists());self.assertFalse(a.available())
   with self.assertRaises(CaptureError):a.start()
   self.assertEqual(len(list((root/'receipts').glob('*.json'))),1)

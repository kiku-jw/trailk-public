import unittest,sys,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from capture_runtime import *
class CaptureTests(unittest.TestCase):
 def test_no_consent_and_source_mismatch_fail_closed(self):
  with self.assertRaises(CaptureError):PCMConsumer().start('zoom')
  with self.assertRaises(CaptureError):PCMConsumer(CaptureConsent('public_sample')).start('zoom')
 def test_repeated_start_stop_and_only_monitor_metadata(self):
  c=PCMConsumer(CaptureConsent('public_sample'));c.start('public_sample')
  with self.assertRaises(CaptureError):c.start('public_sample')
  pcm=struct.pack('<4800h',*([1000]*4800));c.feed(pcm)
  self.assertEqual(c.snapshot()['captured_seconds'],.2);self.assertFalse(c.snapshot()['sent_to_cloud'])
  self.assertNotIn(pcm,str(c.snapshot()).encode());c.finish();c.finish();self.assertFalse(c.running)
 def test_backlog_is_bounded_and_stops_with_visible_gap(self):
  c=PCMConsumer(CaptureConsent('public_sample'));c.start('public_sample')
  for _ in range(10):c.feed(b'\0'*CHUNK)
  self.assertEqual(c.frames.qsize(),5);self.assertFalse(c.running);self.assertEqual(c.reason,'backlog_gap_stopped');self.assertEqual(len(c.pending),0)
 def test_heartbeat_stops_before_more_pcm(self):
  now=[0];c=PCMConsumer(CaptureConsent('public_sample'),lambda:now[0]);c.start('public_sample');now[0]=6;c.feed(b'\0'*CHUNK)
  self.assertFalse(c.running);self.assertEqual(c.samples,0);self.assertEqual(c.reason,'ui_heartbeat_lost')
 def test_no_artificial_silence_injection_and_partial_tail_bounded(self):
  c=PCMConsumer(CaptureConsent('public_sample'));c.start('public_sample');c.feed(b'\0'*100)
  self.assertEqual(c.samples,0);self.assertEqual(len(c.pending),100);c.finish();self.assertEqual(len(c.pending),0)
 def test_duration_cap(self):
  now=[0];c=PCMConsumer(CaptureConsent('public_sample'),lambda:now[0]);c.start('public_sample');now[0]=150;c.touch();c.feed(b'\0'*CHUNK)
  self.assertEqual(c.reason,'duration_limit')

class FrameAgeTests(unittest.TestCase):
 def test_stale_audio_stops_explicitly_and_is_never_replayed(self):
  now=[0.];c=PCMConsumer(CaptureConsent('zoom',60,True,0,1,True),lambda:now[0]);c.start('zoom')
  for n in range(10):now[0]=n*.2;c.touch();c.feed(bytes([n])*CHUNK)
  now[0]=2.1
  self.assertEqual(c.snapshot()['lag_state'],'lagging')
  self.assertIsNone(c.next_frame());self.assertEqual(c.reason,'audio_backlog_stale');self.assertEqual(c.discarded_frames,10)
  self.assertEqual(c.snapshot()['lag_state'],'stopped_stale');self.assertEqual(c.cloud_bytes,0)
  self.assertIsNone(c.next_frame(timeout=.001));c.feed(b'\0'*CHUNK);self.assertEqual(c.frames.qsize(),0)
 def test_fresh_frames_preserve_silence_and_order_without_hidden_resync(self):
  now=[0.];c=PCMConsumer(CaptureConsent('zoom',60,True,0,1,True),lambda:now[0]);c.start('zoom')
  for n in range(4):c.feed(bytes([n])*CHUNK)
  now[0]=.7;self.assertEqual(c.snapshot()['lag_state'],'lagging')
  self.assertEqual([c.next_frame() for _ in range(4)],[bytes([n])*CHUNK for n in range(4)])
  self.assertEqual(c.discarded_frames,0);self.assertTrue(c.running);self.assertEqual(c.snapshot()['lag_state'],'current')

class ContinuousLagTests(unittest.TestCase):
 def test_feed_detects_age_before_ten_second_capacity_is_reached(self):
  now=[0.];c=PCMConsumer(CaptureConsent('zoom',60,True,0,1,True),lambda:now[0]);c.start('zoom')
  for i in range(20):now[0]=i*.2;c.touch();c.feed(b'\0'*CHUNK)
  self.assertEqual(c.reason,'audio_backlog_stale');self.assertEqual(c.frames.qsize(),0);self.assertLessEqual(c.discarded_frames,11)

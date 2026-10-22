import threading
import time
import unittest


class CaptureTests(unittest.TestCase):
 def test_pause_then_continue_never_opens_overlapping_camera(self):
  from tools.voice_capture import CameraSupervisor
  entered=threading.Event();release=threading.Event();seen=[]
  def run(stop,ticket):
   seen.append((stop,ticket));entered.set();release.wait(2)
  manager=CameraSupervisor(run,ticket=lambda:7)
  try:
   self.assertTrue(manager('start'));self.assertTrue(entered.wait(1))
   self.assertTrue(manager('start'));self.assertEqual(len(seen),1)
   self.assertTrue(manager('pause'));self.assertTrue(seen[0][0].is_set())
   self.assertTrue(manager('start'))
   self.assertEqual(len(seen),1)
   self.assertTrue(manager('pause'))  # cancels the queued restart
   release.set();manager.close()
   self.assertFalse(manager('start'))
  finally:release.set();manager.close()
 def test_completion_allows_next_explicit_start_with_fresh_ticket(self):
  from tools.voice_capture import CameraSupervisor
  count=[]
  def run(stop,ticket):count.append(ticket)
  manager=CameraSupervisor(run,ticket=lambda:len(count)+1)
  try:
   self.assertTrue(manager('start'))
   for _ in range(50):
    if not manager.running:break
    time.sleep(.01)
   self.assertTrue(manager('start'))
   manager.close();self.assertEqual(count,[1,2])
  finally:manager.close()

class RestartTests(unittest.TestCase):
 def test_new_task_waits_for_old_camera_release_before_restart(self):
  from tools.voice_capture import CameraSupervisor
  entered=threading.Event();release=threading.Event();second=threading.Event();calls=[]
  def run(stop,ticket):
   calls.append(ticket)
   if len(calls)==1:entered.set();release.wait(2)
   else:second.set()
  manager=CameraSupervisor(run,ticket=lambda:len(calls)+1)
  try:
   self.assertTrue(manager('start'));self.assertTrue(entered.wait(1))
   manager('pause');self.assertTrue(manager('start'))
   self.assertEqual(calls,[1]);release.set()
   self.assertTrue(second.wait(1));self.assertEqual(calls,[1,2])
  finally:release.set();manager.close()

class StartupTests(unittest.TestCase):
 def test_capture_failure_is_returned_without_false_ready(self):
  from tools.voice_capture import CameraSupervisor
  def fail(stop,ticket,ready):raise OSError('camera unavailable')
  manager=CameraSupervisor(fail,ticket=lambda:3,track_ready=True)
  try:
   result=manager('start').result(timeout=1)
   self.assertEqual(result,{'ready':False,'generation':3})
  finally:manager.close()
 def test_ready_is_confirmed_by_first_frame_and_uses_current_generation(self):
  from tools.voice_capture import CameraSupervisor
  release=threading.Event()
  def run(stop,ticket,ready):ready();release.wait(1)
  manager=CameraSupervisor(run,ticket=lambda:4,track_ready=True)
  try:
   result=manager('start').result(timeout=1)
   self.assertEqual(result,{'ready':True,'generation':4})
   self.assertEqual(manager('start').result(timeout=1),result)
  finally:release.set();manager.close()

class ReadinessCancellationTests(unittest.TestCase):
 def test_cancel_during_readiness_commit_still_releases_queued_camera(self):
  from tools.voice_capture import CameraSupervisor
  entered=threading.Event();release=threading.Event();second=threading.Event();calls=[]
  def run(stop,ticket,ready):
   calls.append(ticket)
   if len(calls)==1:entered.set();release.wait(2)
   else:ready();second.set()
  manager=CameraSupervisor(run,ticket=lambda:len(calls)+1,track_ready=True)
  try:
   first=manager('start');self.assertTrue(entered.wait(1))
   manager('pause');queued=manager('start')
   original=first.set_result
   def cancel_before_commit(result):
    first.cancel();original(result)
   first.set_result=cancel_before_commit
   release.set();self.assertTrue(second.wait(.5))
   self.assertTrue(queued.result(timeout=1)['ready'])
  finally:release.set();manager.close()

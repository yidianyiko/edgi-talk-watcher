import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

class RelayTests(unittest.TestCase):
 def test_board_pause_cancels_inflight_relay_without_a_browser(self):
  from tools.pc_camera_relay import relay_frames
  import threading
  entered=threading.Event();released=threading.Event()
  class Client:
   polls=0
   def get(self,path,**kwargs):
    self.polls+=1
    if self.polls==1:return None
    return {'action':'pause'} if entered.wait(.05) else {}
   def post(self,path,body,**kwargs):
    if path=='/api/control':
     if body['action']=='start':return {'session_id':'one'}
     released.set();return {'ok':True}
    entered.set()
    if not released.wait(2):raise AssertionError('Board pause never reached server')
    raise OSError('stale observation')
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'a.jpg';p.write_bytes(b'a')
   report=relay_frames(Client(),iter([{'path':p,'time':1}]),seconds=10,max_calls=1,poll_controls=True)
   self.assertEqual(report['stop_reason'],'board_pause')

 def test_same_observation_api_budget_and_final_pause(self):
  from tools.pc_camera_relay import relay_frames
  with tempfile.TemporaryDirectory() as folder:
   image=Path(folder)/'a.jpg';image.write_bytes(b'jpeg')
   client=Mock();client.post.side_effect=[{'session_id':'one'},{'status':'preparing'},{'status':'event'},{'ok':True}]
   report=relay_frames(client,iter([{'path':image,'time':10},{'path':image,'time':20},{'path':image,'time':30}]),seconds=100,max_calls=1)
   self.assertEqual(report['observations'],2);self.assertEqual(report['stop_reason'],'call_limit')
   self.assertEqual(client.post.call_args_list[1].args[0],'/api/observe')
   self.assertEqual(client.post.call_args_list[-1].args,('/api/control',{'action':'pause','session_id':'one'}))
 def test_network_failure_stops_and_pauses_without_retry(self):
  from tools.pc_camera_relay import relay_frames
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'a.jpg';p.write_bytes(b'a');client=Mock()
   client.post.side_effect=[{'session_id':'one'},OSError('private detail'),{'ok':True}]
   report=relay_frames(client,iter([{'path':p,'time':1}]),seconds=10,max_calls=1)
   self.assertEqual(report['stop_reason'],'error');self.assertEqual(client.post.call_count,3)
   self.assertNotIn('private detail',str(report))
 def test_only_loopback_server_allowed(self):
  from tools.pc_camera_relay import ProductClient
  for url in ('http://example.com:8765','https://127.0.0.1:8765','http://127.0.0.1:8765/other'):
   with self.assertRaises(ValueError):ProductClient(url)

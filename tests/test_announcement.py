import json
from pathlib import Path
import tempfile
import unittest
from watcher.app import create_app
from watcher.board_link import FileBoardLink
from tests.test_web_store import PLAN
from tests.test_watcher import image_data

EVENT={'answers':{'watch':{'type':'choice','choice':'event','confidence':.95,'probabilities':{'event':.95,'no_event':.03,'uncertain':.02}}}}
class AnnouncementTests(unittest.TestCase):
 def test_only_new_committed_event_requests_announcement(self):
  with tempfile.TemporaryDirectory() as folder:
   states=[];app=create_app(judge=lambda _:EVENT,compiler=lambda _:PLAN,data_dir=folder,status_sink=states.append)
   c=app.test_client();h={'X-Watcher-Token':app.config['WATCHER_TOKEN']}
   c.post('/api/tasks',json={'task':'杯子消失时提醒我'},headers=h)
   sid=c.post('/api/control',json={'action':'start'},headers=h).json['session_id']
   for t in [1000,2000,3000]:
    r=c.post('/api/observe',json={'session_id':sid,'frame':{'image':image_data(),'time':t}},headers=h)
    self.assertEqual(r.status_code,200)
   alerts=[s['alert_id'] for s in states if s.get('alert_id')]
   self.assertEqual(len(alerts),1)
   self.assertRegex(alerts[0],r'^[0-9a-f]{32}$')
   c.delete('/api/events',headers=h)
   self.assertEqual(len([s for s in states if s.get('alert_id')]),1)
   reloaded=[];create_app(data_dir=folder,status_sink=reloaded.append)
   self.assertFalse(any(s.get('alert_id') for s in reloaded))
 def test_link_retains_notification_between_heartbeats_but_never_restores_history(self):
  with tempfile.TemporaryDirectory() as folder:
   link=FileBoardLink(folder);aid='b'*32
   link.publish({'status':'event','alert_id':aid});link.publish({'status':'watching'})
   self.assertEqual(json.loads(link.state_file.read_text())['alert_id'],aid)
   with self.assertRaises(ValueError):link.publish({'alert_id':'shell;bad'})
   link.close();fresh=FileBoardLink(folder)
   self.assertNotIn('alert_id',json.loads(fresh.state_file.read_text()));fresh.close()

 def test_busy_delivery_keeps_fifo_until_matching_ack(self):
  with tempfile.TemporaryDirectory() as folder:
   link=FileBoardLink(folder);first='a'*32;second='b'*32
   link.publish({'status':'event','alert_id':first});link.publish({'status':'event','alert_id':second})
   self.assertEqual(json.loads(link.state_file.read_text())['alert_ids'],[first,second])
   (Path(folder)/'board-alert-ack.json').write_text(json.dumps({'alert_id':first}))
   link.publish({'status':'watching'})
   self.assertEqual(json.loads(link.state_file.read_text())['alert_ids'],[second])
   (Path(folder)/'board-alert-ack.json').write_text(json.dumps({'alert_id':'f'*32}))
   link.publish({'status':'watching'})
   self.assertEqual(json.loads(link.state_file.read_text())['alert_ids'],[second])
   link.close()

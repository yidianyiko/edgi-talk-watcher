import tempfile
import unittest
from pathlib import Path
from watcher.store import WatchStore
from watcher.task_plan import compile_task_cached

PLAN = dict(supported=True,target='cup',transition='disappears',instruction='Alert when cup disappears.',reason='')

class PersistenceTests(unittest.TestCase):
    def test_compile_once_and_survive_new_service(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]
            first=compile_task_cached('杯子消失',cache_dir=Path(folder),translator=lambda task:(calls.append(task) or PLAN))
            again=compile_task_cached('杯子消失',cache_dir=Path(folder),translator=lambda task:self.fail('called again'))
            self.assertEqual(first,again)
            self.assertEqual(calls,['杯子消失'])

    def test_tasks_events_restart_prune_and_delete(self):
        with tempfile.TemporaryDirectory() as folder:
            store=WatchStore(folder)
            task=store.save_task('杯子消失',PLAN)
            for index in range(102):
                store.save_event(task['id'],b'before',b'after',index,.9)
            reopened=WatchStore(folder)
            self.assertEqual(reopened.active_task()['task'],'杯子消失')
            self.assertEqual(len(reopened.events()),100)
            event=reopened.events()[0]
            self.assertEqual(reopened.image(event['id'],'before'),b'before')
            reopened.delete_event(event['id'])
            self.assertIsNone(reopened.image(event['id'],'before'))
            reopened.clear_events()
            self.assertEqual(reopened.events(),[])

class WebPersistenceTests(unittest.TestCase):
    def test_compiled_task_and_event_recovered_without_camera_or_compiler(self):
        from watcher.app import create_app
        from tests.test_watcher import image_data
        with tempfile.TemporaryDirectory() as folder:
            calls=[]
            app=create_app(judge=lambda payload:self.fail('unexpected model'),compiler=lambda task:(calls.append(task) or PLAN),data_dir=folder)
            client=app.test_client();headers={'X-Watcher-Token':app.config['WATCHER_TOKEN']}
            saved=client.post('/api/tasks',json={'task':'杯子消失'},headers=headers)
            self.assertEqual(saved.status_code,200)
            task=saved.json['task']
            event=client.post('/api/events',json=dict(task_id=task['id'],before=image_data(),after=image_data(),time=123,confidence=.95),headers=headers)
            self.assertEqual(event.status_code,200)
            restored=create_app(judge=lambda payload:None,data_dir=folder).test_client().get('/api/state').json
            self.assertTrue(restored['paused']);self.assertEqual(restored['task']['task'],'杯子消失');self.assertEqual(len(restored['events']),1)
            event_id=event.json['event']['id']
            self.assertEqual(client.get(f'/api/events/{event_id}/before').status_code,200)
            self.assertEqual(client.get(f'/api/events/{event_id}/../../.env.local').status_code,404)
            self.assertEqual(client.delete(f'/api/events/{event_id}').status_code,403)
            self.assertEqual(client.delete(f'/api/events/{event_id}',headers=headers).status_code,200)
            self.assertEqual(client.get(f'/api/events/{event_id}/before').status_code,404)

    def test_compilation_failure_explicit_and_never_calls_judge(self):
        from watcher.app import create_app
        def reject(task):raise ValueError('Unsupported visual task: counting is not supported')
        with tempfile.TemporaryDirectory() as folder:
            app=create_app(judge=lambda payload:self.fail('model called'),compiler=reject,data_dir=folder)
            response=app.test_client().post('/api/tasks',json={'task':'count'},headers={'X-Watcher-Token':app.config['WATCHER_TOKEN']})
            self.assertEqual(response.status_code,422)
            self.assertIn('counting',response.json['message'])

class EngineWebTests(unittest.TestCase):
    def test_pausing_inflight_shared_engine_discards_event(self):
        import threading
        from watcher.app import create_app
        from tests.test_watcher import image_data
        entered=threading.Event();release=threading.Event();results=[]
        def judge(payload):
            entered.set();release.wait(3)
            return {'answers':{'watch':{'type':'choice','choice':'event','confidence':.95,'probabilities':{'event':.95,'no_event':.03,'uncertain':.02}}}}
        with tempfile.TemporaryDirectory() as folder:
            app=create_app(judge=judge,compiler=lambda task:PLAN,data_dir=folder)
            client=app.test_client();headers={'X-Watcher-Token':app.config['WATCHER_TOKEN']}
            client.post('/api/tasks',json={'task':'cup disappears'},headers=headers)
            sid=client.post('/api/control',json={'action':'start'},headers=headers).json['session_id']
            image=image_data()
            self.assertEqual(client.post('/api/observe',json=dict(session_id=sid,frame=dict(image=image,time=1000)),headers=headers).json['status'],'preparing')
            thread=threading.Thread(target=lambda:results.append(app.test_client().post('/api/observe',json=dict(session_id=sid,frame=dict(image=image,time=2000)),headers=headers)))
            thread.start();self.assertTrue(entered.wait(2))
            client.post('/api/control',json={'action':'pause'},headers=headers);release.set();thread.join(3)
            self.assertEqual(results[0].status_code,409)
            self.assertEqual(client.get('/api/state').json['events'],[])

    def test_malformed_bodies_and_invalid_event_metadata_are_rejected(self):
        from watcher.app import create_app
        from tests.test_watcher import image_data
        with tempfile.TemporaryDirectory() as folder:
            app=create_app(judge=lambda payload:None,compiler=lambda task:PLAN,data_dir=folder)
            client=app.test_client();headers={'X-Watcher-Token':app.config['WATCHER_TOKEN']}
            self.assertEqual(client.post('/api/tasks',json=[],headers=headers).status_code,400)
            task=client.post('/api/tasks',json={'task':'cup'},headers=headers).json['task']
            for timestamp,confidence in [(float('nan'),.9),(1,float('inf')),(1,2)]:
                response=client.post('/api/events',json=dict(task_id=task['id'],before=image_data(),after=image_data(),time=timestamp,confidence=confidence),headers=headers)
                self.assertEqual(response.status_code,400)

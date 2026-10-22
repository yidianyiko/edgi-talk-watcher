"""HTTP lifecycle boundaries, with blocked calls instead of model/network timing."""
import tempfile
import threading
import unittest
from watcher.app import create_app
from tests.test_web_store import PLAN
from tests.test_watcher import image_data

RESPONSE={'answers':{'watch':{'type':'choice','choice':'event','confidence':.95,'probabilities':{'event':.95,'no_event':.03,'uncertain':.02}}}}

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.states=[]
        self.app=create_app(judge=lambda payload:RESPONSE,compiler=lambda task:PLAN,data_dir=self.folder.name,status_sink=self.states.append)
        self.client=self.app.test_client();self.headers={'X-Watcher-Token':self.app.config['WATCHER_TOKEN']}
        self.client.post('/api/tasks',json={'task':'old task'},headers=self.headers)
        self.image=image_data()
    def post(self,path,body):return self.app.test_client().post(path,json=body,headers=self.headers)
    def start(self):return self.post('/api/control',{'action':'start'}).json['session_id']
    def observe(self,sid,time):return self.post('/api/observe',dict(session_id=sid,frame=dict(image=self.image,time=time)))
    def thread(self,fn):
        thread=threading.Thread(target=fn);thread.start();self.addCleanup(lambda:thread.join(3));return thread

    def test_pause_waits_for_event_commit_then_no_late_publish(self):
        sid=self.start();self.observe(sid,1000)
        entered=threading.Event();release=threading.Event();paused=threading.Event()
        original=self.app.config['WATCHER_STORE'].save_event
        def blocked(*args):
            entered.set();release.wait(3);return original(*args)
        self.app.config['WATCHER_STORE'].save_event=blocked
        observer=self.thread(lambda:self.observe(sid,2000));self.assertTrue(entered.wait(2))
        pauser=self.thread(lambda:(self.post('/api/control',{'action':'pause'}),paused.set()))
        try:self.assertFalse(paused.wait(.15),'pause returned before pending event commit')
        finally:release.set();observer.join(3);pauser.join(3)
        self.assertTrue(paused.is_set());self.assertEqual(self.states[-1]['status'],'paused')

    def test_new_task_commit_invalidates_session_started_during_compile(self):
        entered=threading.Event();release=threading.Event()
        # Inject a blocked compiler into a new app; old task was persisted already.
        def compiler(task):entered.set();release.wait(3);return PLAN
        app=create_app(judge=lambda payload:RESPONSE,compiler=compiler,data_dir=self.folder.name)
        self.app=app;self.headers={'X-Watcher-Token':app.config['WATCHER_TOKEN']}
        compiling=self.thread(lambda:self.post('/api/tasks',{'task':'new task'}));self.assertTrue(entered.wait(2))
        old_session=self.start();release.set();compiling.join(3)
        self.assertEqual(self.observe(old_session,1000).status_code,409)

    def test_stateless_legacy_judge_never_publishes_after_pause(self):
        entered=threading.Event();release=threading.Event()
        def judge(payload):entered.set();release.wait(3);return RESPONSE
        self.app=create_app(judge=judge,compiler=lambda task:PLAN,data_dir=self.folder.name,status_sink=self.states.append)
        self.headers={'X-Watcher-Token':self.app.config['WATCHER_TOKEN']}
        body=dict(task='legacy',frames=[dict(image=self.image,seconds_ago=1),dict(image=self.image,seconds_ago=0)])
        judging=self.thread(lambda:self.post('/api/judge',body));self.assertTrue(entered.wait(2))
        self.post('/api/control',{'action':'pause'});release.set();judging.join(3)
        self.assertEqual(self.states[-1]['status'],'paused')

    def test_history_delete_preserves_active_status(self):
        sid=self.start()
        for path in ('/api/events', '/api/events/999'):
            self.app.test_client().delete(path,headers=self.headers)
            self.assertEqual(self.states[-1]['status'],'watching')
        self.assertEqual(self.observe(sid,1000).status_code,200)

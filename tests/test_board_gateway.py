"""Board-to-host gateway tests: fake YUYV frames and injected model only."""
import io
import tempfile
import threading
import unittest
from unittest.mock import patch
from PIL import Image
from watcher.app import create_app
from watcher.board_gateway import convert_yuyv
from tests.test_web_store import PLAN
from tests.test_web_lifecycle import RESPONSE

RAW=bytes([128,128,128,128])*(320*240//2)

class BoardGatewayTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.calls=[];self.states=[]
        self.app=create_app(judge=lambda payload:(self.calls.append(payload) or RESPONSE),compiler=lambda task:PLAN,data_dir=self.folder.name,status_sink=self.states.append)
        self.client=self.app.test_client();self.web={'X-Watcher-Token':self.app.config['WATCHER_TOKEN']}
        self.task=self.client.post('/api/tasks',json={'task':'cup disappears'},headers=self.web).json['task']
        self.headers={'Authorization':'Bearer '+self.app.config['BOARD_GATEWAY_TOKEN'],'X-Watch-Task':str(self.task['id']),
            'X-Watch-Width':'320','X-Watch-Height':'240','X-Watch-Session':'boot1-run1','X-Watch-Reset':'1','X-Watch-Time':'1000'}
        self.addCleanup(lambda:self.app.config['BOARD_GATEWAY'].close())
    def post(self,**changes):
        headers={**self.headers,**changes};return self.app.test_client().post('/api/board/observe',data=RAW,headers=headers)
    def test_yuyv_neutral_gray_is_valid_model_size_jpeg(self):
        data=convert_yuyv(RAW,320,240)
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.format,'JPEG');self.assertEqual(image.size,(640,480));self.assertEqual(image.getpixel((10,10)),(128,128,128))
        with self.assertRaises(ValueError):convert_yuyv(RAW[:-1],320,240)
    def test_authentication_precedes_decode_and_cannot_bypass_web_token(self):
        with patch('watcher.board_gateway.convert_yuyv',side_effect=AssertionError('must not decode')):
            self.assertEqual(self.post(Authorization='Bearer invalid').status_code,403)
            self.assertEqual(self.client.post('/api/board/observe',data=RAW,headers=self.web).status_code,403)
        self.assertEqual(self.client.post('/api/tasks',json={'task':'bad'},headers={'Authorization':self.headers['Authorization']}).status_code,403)
        self.assertFalse(self.calls)
    def test_prime_then_event_dedup_persistence_and_bounded_frames(self):
        self.assertEqual(self.post().text,'watching 0\n');self.assertFalse(self.calls)
        self.assertEqual(self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'6000'}).text,'event 1\n')
        self.assertEqual(self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'11000'}).text,'event 1\n')
        self.assertEqual(len(self.calls),2);self.assertEqual(len(self.client.get('/api/state').json['events']),1)
        self.assertEqual(self.calls[0]['state']['task'],PLAN['instruction'])
        self.assertLessEqual(len(list(self.app.config['BOARD_GATEWAY'].folder.glob('*.jpg'))),2)
    def test_invalid_headers_payload_stale_clock_pause_until_new_session(self):
        self.assertEqual(self.post().status_code,200)
        self.assertEqual(self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'1000'}).status_code,400)
        self.assertEqual(self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'2000'}).status_code,409)
        self.assertEqual(self.post(**{'X-Watch-Session':'boot1-run2'}).status_code,200)
        self.assertEqual(self.post(**{'X-Watch-Session':'boot1-run3','X-Watch-Width':'640'}).status_code,400)
        self.assertFalse(self.calls)
    def test_model_failure_requires_new_reset_session_and_never_auto_retries(self):
        self.post()
        gateway=self.app.config['BOARD_GATEWAY'];gateway.judge=lambda payload:(_ for _ in ()).throw(OSError('secret'))
        result=self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'6000'})
        self.assertEqual(result.status_code,502);self.assertNotIn('secret',result.text)
        self.assertEqual(self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'7000'}).status_code,409)
        self.assertEqual(self.post().status_code,409)
        self.assertEqual(self.post(**{'X-Watch-Session':'boot1-run2'}).status_code,200)
    def test_call_budget_and_deadline_are_injectable(self):
        gateway=self.app.config['BOARD_GATEWAY'];now=[10];gateway.clock=lambda:now[0]
        self.app.config['BOARD_GATEWAY_MAX_CALLS']=1;self.app.config['BOARD_GATEWAY_SECONDS']=10
        self.post();self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'6000'})
        self.assertEqual(self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'11000'}).text,'paused 1\n');self.assertEqual(len(self.calls),1)
        self.post(**{'X-Watch-Session':'boot1-run2'});now[0]=21
        self.assertEqual(self.post(**{'X-Watch-Session':'boot1-run2','X-Watch-Reset':'0','X-Watch-Time':'6000'}).text,'paused 1\n');self.assertEqual(len(self.calls),1)
    def test_browser_pause_and_task_change_invalidate_gateway(self):
        self.post();self.client.post('/api/control',json={'action':'pause'},headers=self.web)
        self.assertEqual(self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'6000'}).status_code,409)
        self.post(**{'X-Watch-Session':'boot1-run2'});self.client.post('/api/tasks',json={'task':'new task'},headers=self.web)
        self.assertEqual(self.post(**{'X-Watch-Session':'boot1-run2','X-Watch-Reset':'0','X-Watch-Time':'6000'}).status_code,409)
    def test_gateway_start_invalidates_browser_and_browser_start_invalidates_gateway(self):
        sid=self.client.post('/api/control',json={'action':'start'},headers=self.web).json['session_id']
        self.post()
        from tests.test_watcher import image_data
        result=self.client.post('/api/observe',json={'session_id':sid,'frame':{'image':image_data(),'time':1000}},headers=self.web)
        self.assertEqual(result.status_code,409)
        self.client.post('/api/control',json={'action':'start'},headers=self.web)
        self.assertEqual(self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'6000'}).status_code,409)

    def test_reused_reset_fails_closed_for_current_session(self):
        self.post()
        self.assertEqual(self.post().status_code,409)
        self.assertEqual(self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'6000'}).status_code,409)
        self.assertFalse(self.calls)

    def test_inflight_gateway_result_cannot_persist_after_web_pause(self):
        self.post();entered=threading.Event();release=threading.Event();responses=[]
        def judge(payload):entered.set();release.wait(3);return RESPONSE
        self.app.config['BOARD_GATEWAY'].judge=judge
        thread=threading.Thread(target=lambda:responses.append(self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'6000'})))
        thread.start();self.assertTrue(entered.wait(2))
        try:self.client.post('/api/control',json={'action':'pause'},headers=self.web)
        finally:release.set();thread.join(3)
        self.assertEqual(responses[0].status_code,409);self.assertEqual(self.client.get('/api/state').json['events'],[])
        self.assertEqual(self.states[-1]['status'],'paused')

    def test_gateway_commit_finishes_before_pause_returns(self):
        self.post();entered=threading.Event();release=threading.Event();paused=threading.Event()
        store=self.app.config['WATCHER_STORE'];original=store.save_event
        def save(*args):entered.set();release.wait(3);return original(*args)
        store.save_event=save
        observer=threading.Thread(target=lambda:self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'6000'}));observer.start();self.assertTrue(entered.wait(2))
        pauser=threading.Thread(target=lambda:(self.app.test_client().post('/api/control',json={'action':'pause'},headers=self.web),paused.set()));pauser.start()
        try:self.assertFalse(paused.wait(.1))
        finally:release.set();observer.join(3);pauser.join(3)
        self.assertTrue(paused.is_set());self.assertEqual(self.states[-1]['status'],'paused')

    def test_short_payload_missing_headers_unknown_task_and_judge_busy_never_call_model(self):
        self.assertEqual(self.app.test_client().post('/api/board/observe',data=RAW[:-1],headers=self.headers).status_code,400)
        for changes in ({'X-Watch-Task':'999'}, {'X-Watch-Time':''}, {'X-Watch-Session':'../bad'}):
            self.assertIn(self.post(**changes).status_code,(400,409))
        self.app.config['JUDGE_LOCK'].acquire()
        try:self.assertEqual(self.post().status_code,429)
        finally:self.app.config['JUDGE_LOCK'].release()
        self.assertFalse(self.calls)

    def test_history_delete_preserves_gateway_display_status(self):
        self.post();self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'6000'})
        self.assertEqual(self.states[-1]['status'],'event')
        self.client.delete('/api/events',headers=self.web)
        self.assertEqual(self.states[-1]['status'],'event')
        self.assertEqual(self.states[-1]['event_count'],0)

    def test_browser_start_busy_preserves_active_gateway(self):
        self.post();entered=threading.Event();release=threading.Event()
        def judge(payload):entered.set();release.wait(3);return RESPONSE
        self.app.config['BOARD_GATEWAY'].judge=judge
        thread=threading.Thread(target=lambda:self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'6000'}));thread.start();self.assertTrue(entered.wait(2))
        try:
            response=self.client.post('/api/control',json={'action':'start'},headers=self.web)
            self.assertEqual(response.status_code,429)
            self.assertEqual(self.states[-1]['status'],'watching')
        finally:release.set();thread.join(3)

    def test_gateway_listener_exposes_only_authenticated_uploads_to_lan(self):
        self.app.config['BOARD_GATEWAY_LAN_ONLY']=True
        remote={'REMOTE_ADDR':'192.168.1.66'}
        for path in ('/','/api/state','/api/events/1/before','/static/app.js'):
            result=self.client.get(path,environ_overrides=remote)
            self.assertEqual(result.status_code,403,path)
            self.assertNotIn(self.app.config['WATCHER_TOKEN'],result.text)
        self.assertEqual(self.client.post('/api/tasks',json={'task':'hostile'},headers=self.web,environ_overrides=remote).status_code,403)
        self.assertEqual(self.client.post('/api/board/observe',data=RAW,headers=self.headers,environ_overrides=remote).status_code,200)
        self.assertEqual(self.client.get('/',environ_overrides={'REMOTE_ADDR':'::ffff:127.0.0.1'}).status_code,200)
        self.assertEqual(self.client.get('/',headers={'X-Forwarded-For':'127.0.0.1'},environ_overrides=remote).status_code,403)

    def test_stale_browser_pause_cannot_stop_new_gateway_owner(self):
        sid=self.client.post('/api/control',json={'action':'start'},headers=self.web).json['session_id']
        self.post()
        self.assertEqual(self.client.post('/api/control',json={'action':'pause','session_id':sid},headers=self.web).status_code,409)
        self.assertEqual(self.post(**{'X-Watch-Reset':'0','X-Watch-Time':'6000'}).status_code,200)

    def test_rejected_gateway_start_does_not_overwrite_active_browser_status(self):
        self.client.post('/api/control',json={'action':'start'},headers=self.web)
        self.app.config['JUDGE_LOCK'].acquire()
        try:self.assertEqual(self.post().status_code,429)
        finally:self.app.config['JUDGE_LOCK'].release()
        self.assertEqual(self.states[-1]['status'],'watching')

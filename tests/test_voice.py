import tempfile
import unittest
from watcher.app import create_app

PCM = b'\x00\x10' * 16000

class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.calls = []
        self.app = create_app(data_dir=self.folder.name, transcriber=lambda raw: '暂停看守')
        self.app.config.update(TESTING=True, BOARD_GATEWAY_TOKEN='board-secret', VOICE_CAPTURE=lambda action: self.calls.append(action) or True)
        self.client = self.app.test_client()
    def tearDown(self): self.folder.cleanup()
    def post(self, rid='request1', pcm=PCM, **kw):
        return self.client.post('/api/board/voice', data=pcm, headers={'Authorization':'Bearer board-secret','Content-Type':'application/octet-stream','X-Voice-Request':rid}, **kw)
    def test_pause_authenticated_idempotent(self):
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post().data, b'ok pause\n')
        self.assertEqual(self.calls, ['pause'])
        state = self.client.get('/api/voice/state',headers={'X-Watcher-Token':self.app.config['WATCHER_TOKEN']}).json
        self.assertEqual(state['text'], '暂停看守')
    def test_reject_auth_format_size_and_protect_state(self):
        self.assertEqual(self.client.post('/api/board/voice', data=PCM).status_code,403)
        self.assertEqual(self.post(pcm=b'\0'*10).status_code,400)
        self.assertEqual(self.post(rid='../unsafe').status_code,400)
        self.assertEqual(self.client.get('/api/voice/state').status_code,403)
        self.assertEqual(self.calls,[])
    def test_silence_never_executes_even_if_transcriber_hallucinates(self):
        self.assertEqual(self.post(pcm=b'\0'*32000).status_code,422)
        self.assertEqual(self.calls,[])
    def test_lan_voice_only(self):
        self.app.config['BOARD_GATEWAY_LAN_ONLY']=True
        remote={'REMOTE_ADDR':'192.168.7.253'}
        self.assertEqual(self.post(environ_base=remote).status_code,200)
        self.assertEqual(self.client.get('/api/voice/state',environ_base=remote).status_code,403)
    def test_pause_cancels_inflight_transcription(self):
        import threading
        entered, release = threading.Event(),threading.Event()
        def transcribe(raw):
            entered.set(); release.wait(3); return '继续看守'
        app=create_app(data_dir=self.folder.name, transcriber=transcribe)
        app.config.update(BOARD_GATEWAY_TOKEN='board-secret', VOICE_CAPTURE=lambda a: self.calls.append(a) or True)
        results=[]
        def upload():
            with app.test_client() as client:
                results.append(client.post('/api/board/voice',data=PCM,headers={'Authorization':'Bearer board-secret','Content-Type':'application/octet-stream','X-Voice-Request':'slow'}))
        thread=threading.Thread(target=upload); thread.start()
        self.assertTrue(entered.wait(2))
        app.test_client().post('/api/control',json={'action':'pause'},headers={'X-Watcher-Token':app.config['WATCHER_TOKEN']})
        release.set(); thread.join(3)
        self.assertEqual(results[0].status_code,409)
        self.assertEqual(self.calls,[])
    def test_task_uses_compiler_and_starts_capture(self):
        import json
        from pathlib import Path
        plan=json.loads(Path('testdata/plans/hand-disappears.json').read_text())
        compiled=[]
        app=create_app(data_dir=self.folder.name, transcriber=lambda _: '当手消失时提醒我', compiler=lambda text: compiled.append(text) or plan)
        app.config.update(BOARD_GATEWAY_TOKEN='board-secret',VOICE_CAPTURE=lambda a:self.calls.append(a) or True)
        response=app.test_client().post('/api/board/voice',data=PCM,headers={'Authorization':'Bearer board-secret','Content-Type':'application/octet-stream','X-Voice-Request':'task'})
        self.assertEqual(response.data,b'ok task\n')
        self.assertEqual(compiled,['当手消失时提醒我'])
        self.assertEqual(self.calls,['pause','start'])
        self.assertEqual(app.config['WATCHER_STORE'].active_task()['task'],'当手消失时提醒我')
    def test_unknown_command_and_asr_error_never_start(self):
        for transcript in ('帮我开门', None):
            def transcribe(_):
                if transcript is None: raise OSError('private error')
                return transcript
            def compiler(_): raise ValueError('Unsupported visual task: not visual')
            with tempfile.TemporaryDirectory() as folder:
                app=create_app(data_dir=folder,transcriber=transcribe,compiler=compiler)
                calls=[]
                app.config.update(BOARD_GATEWAY_TOKEN='board-secret',VOICE_CAPTURE=lambda a:calls.append(a) or True)
                response=app.test_client().post('/api/board/voice',data=PCM,headers={'Authorization':'Bearer board-secret','Content-Type':'application/octet-stream','X-Voice-Request':'unknown'})
                self.assertEqual(response.status_code,422)
                self.assertNotIn('start',calls)
                self.assertNotIn(b'private error',response.data)
    def test_timeout_cannot_execute_late_and_busy_is_bounded(self):
        import threading
        entered, release=threading.Event(),threading.Event()
        def transcribe(_):
            entered.set(); release.wait(2); return '暂停看守'
        app=create_app(data_dir=self.folder.name,transcriber=transcribe)
        app.config.update(BOARD_GATEWAY_TOKEN='board-secret',VOICE_TIMEOUT=.03,VOICE_CAPTURE=lambda a:self.calls.append(a) or True)
        client=app.test_client()
        headers={'Authorization':'Bearer board-secret','Content-Type':'application/octet-stream','X-Voice-Request':'slow'}
        self.assertEqual(client.post('/api/board/voice',data=PCM,headers=headers).status_code,504)
        headers['X-Voice-Request']='other'
        self.assertEqual(client.post('/api/board/voice',data=PCM,headers=headers).status_code,429)
        release.set()
        import time
        time.sleep(.05)
        self.assertEqual(self.calls,[])
    def test_idempotence_survives_app_restart(self):
        self.assertEqual(self.post().status_code,200)
        app=create_app(data_dir=self.folder.name,transcriber=lambda _:self.fail('must not transcribe replay'))
        app.config['BOARD_GATEWAY_TOKEN']='board-secret'
        response=app.test_client().post('/api/board/voice',data=PCM,headers={'Authorization':'Bearer board-secret','Content-Type':'application/octet-stream','X-Voice-Request':'request1'})
        self.assertEqual(response.data,b'ok pause\n')
        self.assertEqual(self.calls,['pause'])
    def test_continue_does_not_stop_already_running_camera(self):
        import json
        from pathlib import Path
        plan=json.loads(Path('testdata/plans/hand-disappears.json').read_text())
        app=create_app(data_dir=self.folder.name,transcriber=lambda _:'继续看守')
        app.config['WATCHER_STORE'].save_task('手消失',plan)
        app.config.update(BOARD_GATEWAY_TOKEN='board-secret',VOICE_CAPTURE=lambda a:self.calls.append(a) or True)
        client=app.test_client()
        for rid in ('resume1','resume2'):
            response=client.post('/api/board/voice',data=PCM,headers={'Authorization':'Bearer board-secret','Content-Type':'application/octet-stream','X-Voice-Request':rid})
            self.assertEqual(response.data,b'ok start\n')
        self.assertEqual(self.calls,['start','start'])
    def test_delayed_voice_capture_ticket_cannot_resume_after_pause(self):
        ticket=self.app.config['VOICE_GENERATION']()
        headers={'X-Watcher-Token':self.app.config['WATCHER_TOKEN']}
        self.client.post('/api/control',json={'action':'pause'},headers=headers)
        response=self.client.post('/api/control',json={'action':'start','voice_generation':ticket},headers=headers)
        self.assertEqual(response.status_code,409)
    def test_voice_pause_invalidates_previously_scheduled_camera_start(self):
        ticket=self.app.config['VOICE_GENERATION']()
        self.assertEqual(self.post().status_code,200)
        response=self.client.post('/api/control',json={'action':'start','voice_generation':ticket},headers={'X-Watcher-Token':self.app.config['WATCHER_TOKEN']})
        self.assertEqual(response.status_code,409)
    def test_continue_while_judge_active_preserves_camera(self):
        import json
        from pathlib import Path
        plan=json.loads(Path('testdata/plans/hand-disappears.json').read_text())
        app=create_app(data_dir=self.folder.name,transcriber=lambda _:'继续看守')
        app.config['WATCHER_STORE'].save_task('手消失',plan)
        app.config.update(BOARD_GATEWAY_TOKEN='board-secret',VOICE_CAPTURE=lambda a:self.calls.append(a) or True)
        app.config['JUDGE_LOCK'].acquire()
        try:
            response=app.test_client().post('/api/board/voice',data=PCM,headers={'Authorization':'Bearer board-secret','Content-Type':'application/octet-stream','X-Voice-Request':'judge-active'})
            self.assertEqual(response.data,b'ok start\n')
            self.assertEqual(self.calls,['start'])
        finally: app.config['JUDGE_LOCK'].release()
    def test_traditional_control_normalization(self):
        from watcher.voice import command
        self.assertEqual(command('暫停看守。'),'pause')
        self.assertEqual(command('繼續看守！'),'start')
        self.assertEqual(command('恢復看守'),'start')
    def test_start_busy_does_not_consume_generation_ticket(self):
        import json
        from pathlib import Path
        self.app.config['WATCHER_STORE'].save_task('手消失',json.loads(Path('testdata/plans/hand-disappears.json').read_text()))
        ticket=self.app.config['VOICE_GENERATION']()
        headers={'X-Watcher-Token':self.app.config['WATCHER_TOKEN']}
        self.app.config['JUDGE_LOCK'].acquire()
        try:
            response=self.client.post('/api/control',json={'action':'start','voice_generation':ticket},headers=headers)
            self.assertEqual(response.status_code,429)
            self.assertEqual(self.app.config['VOICE_GENERATION'](),ticket)
        finally: self.app.config['JUDGE_LOCK'].release()
        response=self.client.post('/api/control',json={'action':'start','voice_generation':ticket},headers=headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['generation'],ticket+1)
    def test_camera_readiness_future_blocks_success_until_first_frame(self):
        from concurrent.futures import Future
        import threading,json,time
        from pathlib import Path
        ready=Future();called=threading.Event();results=[]
        app=create_app(data_dir=self.folder.name,transcriber=lambda _:'继续看守')
        app.config['WATCHER_STORE'].save_task('手消失',json.loads(Path('testdata/plans/hand-disappears.json').read_text()))
        def capture(action):
            if action=='start': called.set();return ready
            return True
        app.config.update(BOARD_GATEWAY_TOKEN='board-secret',VOICE_CAPTURE=capture)
        def upload():
            results.append(app.test_client().post('/api/board/voice',data=PCM,headers={'Authorization':'Bearer board-secret','Content-Type':'application/octet-stream','X-Voice-Request':'ready'}))
        thread=threading.Thread(target=upload);thread.start()
        self.assertTrue(called.wait(2));time.sleep(.02)
        self.assertEqual(results,[])
        ready.set_result({'ready':True,'generation':app.config['VOICE_GENERATION']()})
        thread.join(2)
        self.assertEqual(results[0].data,b'ok start\n')
    def test_camera_not_ready_or_cancelled_never_reports_success(self):
        from concurrent.futures import Future
        import json
        from pathlib import Path
        plan=json.loads(Path('testdata/plans/hand-disappears.json').read_text())
        for outcome,expected in (({'ready':False,'generation':0},503),({'ready':True,'generation':999},409),(None,504)):
            with tempfile.TemporaryDirectory() as folder:
                app=create_app(data_dir=folder,transcriber=lambda _:'继续看守')
                app.config['WATCHER_STORE'].save_task('手消失',plan)
                ready=Future()
                if outcome is not None: ready.set_result(outcome)
                app.config.update(BOARD_GATEWAY_TOKEN='board-secret',VOICE_START_TIMEOUT=.01,VOICE_CAPTURE=lambda _:ready)
                response=app.test_client().post('/api/board/voice',data=PCM,headers={'Authorization':'Bearer board-secret','Content-Type':'application/octet-stream','X-Voice-Request':'not-ready'})
                self.assertEqual(response.status_code,expected)
                if outcome is None: self.assertTrue(ready.cancelled())
    def test_outer_timeout_cancels_startup_even_after_start_admission(self):
        from concurrent.futures import Future
        import json,time
        from pathlib import Path
        ready=Future()
        app=create_app(data_dir=self.folder.name,transcriber=lambda _:'继续看守')
        app.config['WATCHER_STORE'].save_task('手消失',json.loads(Path('testdata/plans/hand-disappears.json').read_text()))
        def capture(action):
            if action=='start':
                # Simulate the supervisor already admitting /api/control start.
                with app.test_client() as client:
                    response=client.post('/api/control',json={'action':'start'},headers={'X-Watcher-Token':app.config['WATCHER_TOKEN']})
                    self.assertEqual(response.status_code,200)
                return ready
            return True
        app.config.update(BOARD_GATEWAY_TOKEN='board-secret',VOICE_TIMEOUT=.03,VOICE_START_TIMEOUT=1,VOICE_CAPTURE=capture)
        response=app.test_client().post('/api/board/voice',data=PCM,headers={'Authorization':'Bearer board-secret','Content-Type':'application/octet-stream','X-Voice-Request':'outer-timeout'})
        self.assertEqual(response.status_code,504)
        self.assertTrue(ready.cancelled())
        time.sleep(.03)
        state=app.test_client().get('/api/voice/state',headers={'X-Watcher-Token':app.config['WATCHER_TOKEN']}).json
        self.assertNotEqual(state['status'],'done')

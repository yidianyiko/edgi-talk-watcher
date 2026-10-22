"""Bounded local PCM speech recognition and explicit watcher commands."""
import array
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
import math
import os
from pathlib import Path
import re
import secrets
import sys
import threading
import wave
from flask import Response, jsonify, request

REQUEST_ID = re.compile(r'[A-Za-z0-9_-]{1,64}\Z')

class LocalTranscriber:
    def __init__(self):
        self.model = None
    def __call__(self, pcm):
        import numpy as np
        from faster_whisper import WhisperModel
        samples = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768
        if float(np.sqrt(np.mean(samples * samples))) < .003:
            raise ValueError('No speech')
        if self.model is None:
            path = os.environ.get('WATCHER_ASR_MODEL', str(Path(__file__).resolve().parents[1] / 'var/models/whisper-base'))
            self.model = WhisperModel(path, device='cpu', compute_type='int8', local_files_only=True)
        segments, _ = self.model.transcribe(samples, language='zh', beam_size=5, vad_filter=True, condition_on_previous_text=False, initial_prompt='普通话看守设备命令：暂停看守。继续看守。')
        accepted = [s.text for s in segments if s.no_speech_prob < .6 and s.avg_logprob > -1]
        text = ''.join(accepted).strip()
        if not text:
            raise ValueError('No confident speech')
        return text


def command(text):
    normalized = re.sub(r'[\s，。！？,.!?]', '', text).translate(str.maketrans('暫繼續開復', '暂继续开复'))
    if normalized in ('暂停', '暂停看守', '停止看守', '停止'):
        return 'pause'
    if normalized in ('继续', '继续看守', '开始看守', '开始', '恢复看守'):
        return 'start'
    # Free-form text always passes the existing task compiler; no tool execution.
    return 'task'


def attach_voice(app, directory, transcriber, lifecycle_lock, invalidate, generation, stop_session, publish, store, compiler):
    transcriber = transcriber or LocalTranscriber()
    busy = threading.Lock()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='watcher-voice')
    recent = {'status':'idle', 'text':'', 'action':None}
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS voice_requests (id TEXT PRIMARY KEY, body TEXT NOT NULL, code INTEGER NOT NULL)')
    archive = directory / 'voice'

    def reply(body, code=200):
        return Response(body + '\n', status=code, mimetype='text/plain')

    def capture(action):
        callback = app.config.get('VOICE_CAPTURE')
        try:
            return callback(action) if callback else False
        except Exception:
            return False

    @app.get('/api/voice/state')
    def voice_state():
        if not secrets.compare_digest(request.headers.get('X-Watcher-Token',''), app.config['WATCHER_TOKEN']):
            return jsonify(message='Forbidden'), 403
        with lifecycle_lock:
            return jsonify(recent)

    @app.post('/api/board/voice')
    def voice_upload():
        expected = app.config.get('BOARD_GATEWAY_TOKEN', '')
        supplied = request.headers.get('Authorization', '')
        if not expected or not secrets.compare_digest(supplied.encode(), ('Bearer ' + expected).encode()):
            return reply('error auth', 403)
        rid = request.headers.get('X-Voice-Request', '')
        if not REQUEST_ID.fullmatch(rid) or request.mimetype != 'application/octet-stream':
            return reply('error format', 400)
        if request.content_length is None or not 16000 <= request.content_length <= 256000 or request.content_length % 2:
            return reply('error size', 400)
        cancelled = threading.Event()
        owned_startup = [None]
        pcm = request.get_data()
        if len(pcm) != request.content_length:
            return reply('error size', 400)
        with lifecycle_lock:
            with store.connect() as db:
                cached = db.execute('SELECT body,code FROM voice_requests WHERE id=?', (rid,)).fetchone()
            if cached:
                return reply(cached['body'], cached['code'])
            if not busy.acquire(blocking=False):
                return reply('error busy', 429)
            with store.connect() as db:
                db.execute('INSERT INTO voice_requests VALUES(?,?,?)', (rid, 'error interrupted', 409))
            own_generation = generation()
            recent.update(status='recognizing', text='', action=None)

        def work():
            nonlocal own_generation
            text = ''
            transitioned = False
            try:
                archive.mkdir(parents=True, exist_ok=True)
                # IDs are safe ASCII; opaque filename keeps paths independent of content.
                with wave.open(str(archive / (secrets.token_hex(16) + '.wav')), 'wb') as wav:
                    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(pcm)
                samples = array.array('h', pcm)
                if sys.byteorder != 'little':
                    samples.byteswap()
                if math.sqrt(sum(value * value for value in samples) / len(samples)) < 100:
                    raise ValueError('Silence')
                text = transcriber(pcm)
                if not isinstance(text, str) or not text.strip() or len(text) > 1000:
                    raise ValueError('No speech')
                text = text.strip()
                action = command(text)
                with lifecycle_lock:
                    if cancelled.is_set() or generation() != own_generation:
                        recent.update(status='cancelled', text=text, action=None)
                        return 'error cancelled', 409
                    if action != 'start':
                        invalidate()
                        own_generation = generation()
                        transitioned = True
                        stop_session()
                        capture('pause')
                        publish('paused', task=store.active_task())
                plan = None
                startup = None
                if action == 'task':
                    existing = store.find_task(text)
                    plan = existing['plan'] if existing else compiler(text)
                with lifecycle_lock:
                    if cancelled.is_set() or generation() != own_generation:
                        recent.update(status='cancelled', text=text, action=None)
                        return 'error cancelled', 409
                    if action == 'task':
                        store.save_task(text, plan)
                    if action != 'pause':
                        if not store.active_task():
                            raise ValueError('No task')
                        transitioned = True
                        startup = capture('start')
                        owned_startup[0] = startup
                        if not startup:
                            raise ValueError('Capture unavailable')
                # The supervisor acknowledges only after the first frame entered
                # the shared engine. Never wait for camera startup under the lock.
                if isinstance(startup, Future):
                    try:
                        ready = startup.result(timeout=app.config.get('VOICE_START_TIMEOUT', 40))
                    except TimeoutError:
                        startup.cancel()  # Producer must stop its own cancelled worker.
                        with lifecycle_lock:
                            recent.update(status='failed', text=text, action=None)
                        return 'error capture timeout', 504
                    with lifecycle_lock:
                        if cancelled.is_set():
                            return 'error cancelled', 409
                        if not isinstance(ready, dict) or not ready.get('ready'):
                            recent.update(status='failed', text=text, action=None)
                            return 'error capture', 503
                        if type(ready.get('generation')) is not int or generation() != ready['generation']:
                            recent.update(status='cancelled', text=text, action=None)
                            return 'error cancelled', 409
                        own_generation = ready['generation']
                with lifecycle_lock:
                    if cancelled.is_set() or generation() != own_generation:
                        recent.update(status='cancelled', text=text, action=None)
                        return 'error cancelled', 409
                    recent.update(status='done', text=text, action=action)
                    return 'ok ' + action, 200
            except Exception:
                with lifecycle_lock:
                    if generation() == own_generation:
                        if transitioned:
                            stop_session()
                            capture('pause')
                            publish('paused', task=store.active_task())
                        recent.update(status='failed', text=text, action=None)
                return 'error recognition', 422
            finally:
                busy.release()

        future = executor.submit(work)
        try:
            body, code = future.result(timeout=app.config.get('VOICE_TIMEOUT', 115))
        except TimeoutError:
            cancelled.set()
            with lifecycle_lock:
                startup = owned_startup[0]
                if isinstance(startup, Future):
                    startup.cancel()
                recent.update(status='failed', text='', action=None)
                if generation() == own_generation:
                    invalidate()
                    recent.update(status='failed', text='', action=None)
            body, code = 'error timeout', 504
        with lifecycle_lock:
            with store.connect() as db:
                db.execute('UPDATE voice_requests SET body=?,code=? WHERE id=?', (body,code,rid))
        return reply(body, code)

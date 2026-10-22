"""Authenticated board YUYV transport to the host's existing watcher engine.

This is a LAN inference gateway: model credentials and model calls stay on the host.
A fresh session/reset primes one frame. Failure requires an explicit new session.
"""
from pathlib import Path
import re
import secrets
import tempfile
import time
import io
import json
import hashlib

from flask import Response, request
from PIL import Image
from research.jev_probe import build_request, read_decision
from watcher.engine import WatchEngine

WIDTH, HEIGHT = 320, 240
FRAME_BYTES = WIDTH * HEIGHT * 2
SESSION = re.compile(r'[A-Za-z0-9_-]{1,64}\Z')
INTEGER = re.compile(r'[0-9]{1,16}\Z')


def convert_yuyv(raw, width, height):
    """Expand YUYV422 to Pillow YCbCr444, then meet the model's 280px minimum."""
    if (width, height) != (WIDTH, HEIGHT) or len(raw) != FRAME_BYTES:
        raise ValueError('Expected one 320x240 YUYV frame')
    expanded = bytearray(WIDTH * HEIGHT * 3)
    expanded[0::3] = raw[0::2]
    expanded[1::6] = expanded[4::6] = raw[1::4]
    expanded[2::6] = expanded[5::6] = raw[3::4]
    image = Image.frombytes('YCbCr', (WIDTH, HEIGHT), bytes(expanded)).convert('RGB')
    image = image.resize((640, 480))
    output = io.BytesIO()
    image.save(output, 'JPEG', quality=90)
    return output.getvalue()


class BoardGateway:
    def __init__(self, app, store, judge, lifecycle_lock, on_start, status_sink=None,
                 clock=time.monotonic):
        self.app, self.store, self.judge = app, store, judge
        self.lock, self.on_start, self.status_sink = lifecycle_lock, on_start, status_sink
        self.clock = clock
        self.engine = self.task = self.session_id = None
        self._temporary = None
        self.folder = None
        self.seen_sessions = set()
        self.expected_seed = None

    def authorized(self):
        expected = self.app.config['BOARD_GATEWAY_TOKEN']
        supplied = request.headers.get('Authorization', '')
        return bool(expected) and secrets.compare_digest(supplied.encode(), ('Bearer ' + expected).encode())

    def reply(self, status='paused', code=200, *, authorized=True):
        count = len(self.store.events()) if authorized else 0
        return Response(f'{status} {count}\n', status=code, mimetype='text/plain')

    def publish(self, status, **extra):
        if self.status_sink:
            try:
                self.status_sink(dict(status=status, task=self.task, event_count=len(self.store.events()), **extra))
            except (OSError, ValueError):
                self.app.logger.warning('Board gateway status unavailable')

    def pause(self):
        # Caller holds the shared lifecycle lock; no files are removed in-flight.
        if self.engine:
            self.engine.pause()

    def reject(self, code):
        # A rejected upload has not acquired ownership from the browser. Only
        # the gateway's own active session may change the shared display here.
        owned = self.engine is not None and not self.engine.paused
        self.pause()
        if owned:
            self.publish('paused')
        return self.reply(code=code)

    def close(self):
        with self.lock:
            self.pause()
            if self._temporary:
                self._temporary.cleanup()
                self._temporary = None
                self.folder = None

    def observe(self):
        # Also checked at the CSRF boundary. Keep authentication here so this
        # transport cannot accidentally be mounted without the same boundary.
        if not self.authorized():
            return self.reply(code=403, authorized=False)
        acquired = False
        engine = None
        try:
            with self.lock:
                task_id = request.headers.get('X-Watch-Task', '')
                stamp = request.headers.get('X-Watch-Time', '')
                session = request.headers.get('X-Watch-Session', '')
                reset = request.headers.get('X-Watch-Reset', '')
                if (request.headers.get('X-Watch-Width') != '320' or request.headers.get('X-Watch-Height') != '240'
                        or not INTEGER.fullmatch(task_id) or not INTEGER.fullmatch(stamp)
                        or int(stamp) > 2**53 or not SESSION.fullmatch(session) or reset not in ('0', '1')
                        or request.content_length != FRAME_BYTES):
                    return self.reject(400)
                if self.app.config.get('BOARD_CAMERA_MANAGED') and (
                        not self.expected_seed or session != self.expected_seed + '_1'):
                    return self.reply(code=409)
                task = self.store.active_task()
                if not task or task['id'] != int(task_id):
                    return self.reject(409)
                if reset == '1':
                    if session in self.seen_sessions or len(self.seen_sessions) >= 1024:
                        if session == self.session_id:
                            return self.reject(409)
                        return self.reply(code=409)
                elif (session != self.session_id or not self.engine or self.engine.paused):
                    return self.reply(code=409)
                if reset == '0' and self.engine.last_frame and int(stamp) / 1000 <= self.engine.last_frame['time']:
                    return self.reject(400)
                if not self.app.config['JUDGE_LOCK'].acquire(blocking=False):
                    return self.reject(429)
                acquired = True
                if reset == '1':
                    self.pause()
                    self.on_start()
                    if self._temporary:
                        self._temporary.cleanup()
                    self._temporary = tempfile.TemporaryDirectory(prefix='watcher-board-')
                    self.folder = Path(self._temporary.name)
                    self.session_id, self.task = session, task
                    self.seen_sessions.add(session)
                    self.engine = WatchEngine(task['plan'], max_calls=self.app.config['BOARD_GATEWAY_MAX_CALLS'],
                        deadline=self.clock() + self.app.config['BOARD_GATEWAY_SECONDS'], clock=self.clock)
                engine, folder = self.engine, self.folder
            # Decoding and paid-model work are outside the lifecycle lock. The
            # shared judge lock prevents concurrent model requests/file cleanup.
            raw = request.get_data(cache=False)
            image = convert_yuyv(raw, WIDTH, HEIGHT)
            path = folder / (secrets.token_hex(12) + '.jpg')
            path.write_bytes(image)
            recording_root = self.app.config.get('BOARD_RECORDING_ROOT')
            if recording_root:
                archive = Path(recording_root) / session
                archive.mkdir(parents=True, exist_ok=True)
                name = stamp.zfill(16)
                (archive / (name + '.yuyv')).write_bytes(raw)
                (archive / (name + '.jpg')).write_bytes(image)
                metadata = dict(time_ms=int(stamp), raw=name+'.yuyv', image=name+'.jpg',
                                sha256=hashlib.sha256(raw).hexdigest(),
                                source='board-uvc-yuyv-320x240', task_id=int(task_id))
                with (archive / 'frames.jsonl').open('a') as stream:
                    stream.write(json.dumps(metadata)+'\n')
            captured = dict(path=str(path), time=int(stamp) / 1000)
            def evaluate(plan, before, after):
                payload = build_request(dict(task=plan['instruction'], frames=[
                    dict(path=before['path'], seconds_ago=after['time']-before['time']),
                    dict(path=after['path'], seconds_ago=0)]), Path('/'), 'jev-1.14.0')
                return read_decision(self.judge(payload))
            decision = engine.observe(captured, evaluate)
            with self.lock:
                if engine is not self.engine or engine.paused or decision.get('discarded'):
                    if engine is self.engine and not engine.paused:
                        self.pause()
                        self.publish('paused')
                    return self.reply(code=409)
                status = {'preparing':'watching', 'no_event':'watching', 'event':'event', 'uncertain':'uncertain'}.get(decision['status'])
                if status is None:
                    self.pause()
                    self.publish('paused')
                    return self.reply()
                alert = {}
                if decision.get('alert'):
                    self.store.save_event(self.task['id'], Path(decision['before']['path']).read_bytes(),
                                          image, time.time() * 1000, decision['confidence'])
                    alert['alert_id'] = secrets.token_hex(16)
                keep = {frame['path'] for frame in (engine.reference,engine.last_frame) if frame}
                for old in folder.glob('*.jpg'):
                    if str(old) not in keep:
                        old.unlink(missing_ok=True)
                self.publish(status, **alert)
                if reset == '1' and self.app.config.get('BOARD_FRAME_READY'):
                    self.app.config['BOARD_FRAME_READY'](session)
                return self.reply(status)
        except Exception:
            with self.lock:
                if engine is self.engine or engine is None:
                    self.pause()
                    self.publish('paused')
                return self.reply(code=502)
        finally:
            if acquired:
                self.app.config['JUDGE_LOCK'].release()


def attach_gateway(app, store, judge, lifecycle_lock, on_start, status_sink=None):
    app.config.setdefault('BOARD_GATEWAY_TOKEN', secrets.token_urlsafe(32))
    app.config.setdefault('BOARD_GATEWAY_MAX_CALLS', 60)
    app.config.setdefault('BOARD_GATEWAY_SECONDS', 300)
    gateway = BoardGateway(app, store, judge, lifecycle_lock, on_start, status_sink)
    app.config['BOARD_GATEWAY'] = gateway
    app.add_url_rule('/api/board/observe', 'board_observe', gateway.observe, methods=['POST'])
    return gateway

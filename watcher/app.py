"""Local-only HTTP boundary for the browser camera watcher."""
import base64
import binascii
import json
import ipaddress
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time
import urllib.error
import urllib.request

from flask import Flask, jsonify, render_template, request, Response
from watcher.board_gateway import attach_gateway
from watcher.voice import attach_voice
from watcher.engine import WatchEngine
from watcher.store import WatchStore
from watcher.task_plan import compile_task_cached
from research.jev_probe import build_request, read_decision, ENDPOINT

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'jev-1.14.0'


def load_key():
    for name in ('JEV_TOKEN', 'TYPESAFE_API_KEY'):
        if os.environ.get(name, '').strip():
            return os.environ[name].strip()
    path = ROOT / '.env.local'
    if path.exists():
        for line in path.read_text().splitlines():
            name, sep, value = line.strip().removeprefix('export ').partition('=')
            if sep and name.strip() in ('JEV_TOKEN', 'TYPESAFE_API_KEY'):
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                if value:
                    return value
    return ''


def call_jev(payload, *, timeout=20):
    key = load_key()
    if not key:
        raise ValueError('Missing key')
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(), headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
        'TypeSafe-Danger-Zone-Images': 'true'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def camera_payload(body):
    if not isinstance(body, dict):
        raise ValueError('请求需要包含任务和两帧图片。')
    task = body.get('task')
    if not isinstance(task, str) or not 1 <= len(task.strip()) <= 1000:
        raise ValueError('请输入 1–1000 字的看守任务。')
    frames = body.get('frames')
    if not isinstance(frames, list) or len(frames) != 2:
        raise ValueError('需要前后两帧画面。')
    with tempfile.TemporaryDirectory(prefix='watcher-') as folder:
        refs = []
        for i, frame in enumerate(frames):
            if not isinstance(frame, dict) or not isinstance(frame.get('image'), str):
                raise ValueError('图片格式无效。')
            prefix, sep, encoded = frame['image'].partition(',')
            if not sep or prefix not in ('data:image/jpeg;base64', 'data:image/png;base64'):
                raise ValueError('只支持 JPEG 或 PNG 图片。')
            try:
                raw = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError('图片编码无效。') from exc
            name = f'{i}.image'
            (Path(folder) / name).write_bytes(raw)
            refs.append({'path': name, 'seconds_ago': frame.get('seconds_ago')})
        return build_request({'task': task.strip(), 'frames': refs}, Path(folder), MODEL)


def create_app(judge=None, *, compiler=None, data_dir=None, status_sink=None, transcriber=None):
    app = Flask(__name__, template_folder='templates')
    app.config.update(MAX_CONTENT_LENGTH=4 * 1024 * 1024,
                      WATCHER_TOKEN=secrets.token_urlsafe(32), JUDGE_LOCK=threading.Lock(),
                      BOARD_GATEWAY_LAN_ONLY=False)
    injected_judge = judge is not None
    judge = judge or call_jev
    directory = Path(data_dir or os.environ.get('WATCHER_DATA_DIR', ROOT / 'var' / 'watcher'))
    store = WatchStore(directory)
    app.config['WATCHER_STORE'] = store
    compiler = compiler or (lambda task: compile_task_cached(task, cache_dir=directory / 'plans'))
    gateway = None
    lifecycle_lock = threading.RLock()
    current = {'engine': None, 'session_id': None, 'folder': None, 'task': None}
    display = {'status': 'paused'}
    lifecycle_generation = [0]

    def invalidate():
        lifecycle_generation[0] += 1

    def voice_generation():
        with lifecycle_lock:
            return lifecycle_generation[0]

    app.config['VOICE_GENERATION'] = voice_generation

    def publish(status, **extra):
        display['status'] = status
        if status_sink:
            try:
                status_sink(dict(status=status, event_count=len(store.events()), **extra))
            except (OSError, ValueError):
                app.logger.warning('Board status unavailable')

    def json_body():
        body = request.get_json(silent=True)
        return body if isinstance(body, dict) else {}

    @app.before_request
    def restrict_gateway_listener():
        if not app.config['BOARD_GATEWAY_LAN_ONLY']:
            return None
        try:
            remote = ipaddress.ip_address(request.remote_addr or '')
            loopback = remote.is_loopback or (isinstance(remote, ipaddress.IPv6Address)
                and remote.ipv4_mapped is not None and remote.ipv4_mapped.is_loopback)
        except ValueError:
            loopback = False
        if not loopback and not (request.path in ('/api/board/observe', '/api/board/voice') and request.method == 'POST'):
            return Response('Forbidden\n', status=403, mimetype='text/plain')

    @app.before_request
    def protect_mutations():
        if request.path == '/api/board/voice' and request.method == 'POST':
            return None  # Dedicated bearer authentication inside the voice boundary.
        if request.path == '/api/board/observe' and request.method == 'POST' and gateway:
            if gateway.authorized():
                return None
            return gateway.reply(code=403, authorized=False)
        if request.method in ('POST', 'DELETE', 'PUT', 'PATCH') and not secrets.compare_digest(
                request.headers.get('X-Watcher-Token', ''), app.config['WATCHER_TOKEN']):
            return jsonify(status='error', message='页面已失效，请刷新重试。'), 403

    @app.get('/api/state')
    def state():
        return jsonify(task=store.active_task(), events=store.events(), paused=True)

    @app.post('/api/tasks')
    def task_create():
        body = json_body()
        task = body.get('task')
        if not isinstance(task, str) or not 1 <= len(task.strip()) <= 1000:
            return jsonify(message='请输入 1–1000 字的看守任务。'), 400
        try:
            with lifecycle_lock:
                invalidate()
                stop_session()
                publish('paused', task=store.active_task())
            existing = store.find_task(task.strip())
            plan = existing['plan'] if existing else compiler(task.strip())
            with lifecycle_lock:
                # Compilation is deliberately outside the lock. Invalidate sessions
                # started meanwhile before the new task becomes the active task.
                invalidate()
                stop_session()
                task = store.save_task(task.strip(), plan)
                publish('paused', task=task)
        except ValueError as exc:
            reason = str(exc)
            message = ('当前仅支持单目标出现或消失：' + reason.split(':', 1)[-1]) if reason.startswith('Unsupported visual task:') else '任务编译失败，请稍后手动重试。'
            return jsonify(message=message), 422
        return jsonify(task=task)

    def stop_browser():
        if current['engine']:
            current['engine'].pause()
        # Any later browser notification belongs to the previous owner.
        current['session_id'] = None

    def stop_session():
        stop_browser()
        if gateway:
            gateway.pause()
            gateway.expected_seed = None

    def admit_board_camera(generation, seed):
        with lifecycle_lock:
            if generation != lifecycle_generation[0] or app.config['JUDGE_LOCK'].locked():
                raise ValueError('Camera start was superseded or the judge is busy')
            task = store.active_task()
            if not task:
                raise ValueError('Create a task before starting the camera')
            import re
            if not isinstance(seed, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', seed):
                raise ValueError('Invalid board camera session seed')
            invalidate()
            stop_session()
            gateway.expected_seed = seed
            publish('idle', task=task)
            return dict(generation=lifecycle_generation[0], task=task)

    def stop_board_camera(generation):
        with lifecycle_lock:
            if generation == lifecycle_generation[0]:
                invalidate()
                stop_session()
                publish('paused', task=store.active_task())

    app.config['BOARD_CAMERA_ADMIT'] = admit_board_camera
    app.config['BOARD_CAMERA_STOP'] = stop_board_camera

    @app.post('/api/observe')
    def observe():
        body = json_body()
        # Lifecycle transitions and event commits share this short lock. Never
        # hold it while calling the compiler or remote image model.
        with lifecycle_lock:
            engine = current['engine']
            if not engine or body.get('session_id') != current['session_id'] or engine.paused:
                return jsonify(message='看守已暂停，请重新开始。'), 409
            if not app.config['JUDGE_LOCK'].acquire(blocking=False):
                return jsonify(message='上一次判断尚未结束。'), 429
            folder = current['folder'].name
        try:
            frame = body.get('frame') or {}
            camera_payload(dict(task='validate', frames=[dict(image=frame.get('image'),seconds_ago=1),dict(image=frame.get('image'),seconds_ago=0)]))
            path = Path(folder) / (secrets.token_hex(12) + '.jpg')
            path.write_bytes(base64.b64decode(frame['image'].split(',',1)[1]))
            captured = dict(path=str(path), time=float(frame['time']) / 1000)
            started = time.monotonic()
            def evaluate_pair(plan, before, after):
                payload = build_request(dict(task=plan['instruction'],frames=[
                    dict(path=before['path'],seconds_ago=after['time']-before['time']),
                    dict(path=after['path'],seconds_ago=0)]), Path('/'), MODEL)
                return read_decision(judge(payload))
            decision = engine.observe(captured, evaluate_pair)
            with lifecycle_lock:
                if engine is not current['engine'] or engine.paused or decision.get('discarded'):
                    return jsonify(message='看守已暂停，已忽略旧判断。'), 409
                event = None
                if decision.get('alert'):
                    event_id = store.save_event(current['task']['id'],Path(decision['before']['path']).read_bytes(),
                        path.read_bytes(),float(frame['time']),decision['confidence'])
                    event = next(e for e in store.events() if e['id'] == event_id)
                keep = {f['path'] for f in (engine.reference,engine.last_frame) if f}
                for old in path.parent.glob('*.jpg'):
                    if str(old) not in keep: old.unlink(missing_ok=True)
                status = decision['status']
                publish({'preparing':'watching','no_event':'watching','event':'event','uncertain':'uncertain'}.get(status,'paused'),
                        **({'alert_id':secrets.token_hex(16)} if event is not None else {}))
                return jsonify(status=status,confidence=decision.get('confidence',0),alert=decision.get('alert',False),
                               event=event,latency_seconds=round(time.monotonic()-started,3))
        except Exception:
            with lifecycle_lock:
                engine.pause()
                if engine is current['engine']:
                    publish('paused')
            return jsonify(message='图片无效或模型连接失败，看守已暂停，请手动重试。'), 502
        finally:
            app.config['JUDGE_LOCK'].release()

    @app.post('/api/control')
    def control():
        body = json_body()
        action = body.get('action')
        with lifecycle_lock:
            if action == 'start' and 'voice_generation' in body and (
                    type(body['voice_generation']) is not int or body['voice_generation'] != lifecycle_generation[0]):
                return jsonify(message='旧语音操作已忽略。'), 409
            if action == 'pause' and body.get('session_id') and body['session_id'] != current['session_id']:
                return jsonify(message='旧看守操作已忽略。'), 409
            if action not in ('start', 'pause'):
                return jsonify(message='无效操作。'), 400
            if action == 'start':
                task = store.active_task()
                if not task:
                    return jsonify(message='请先建立任务。'), 400
                if app.config['JUDGE_LOCK'].locked():
                    return jsonify(message='上一次判断尚未结束，请稍后手动重试。'), 429
            invalidate()
            stop_session()
            if action == 'start':
                if current['folder']:
                    current['folder'].cleanup()
                current.update(engine=WatchEngine(task['plan']),session_id=secrets.token_urlsafe(24),
                               folder=tempfile.TemporaryDirectory(prefix='watcher-session-'),task=task)
            publish('watching' if action == 'start' else 'paused', task=store.active_task())
            return jsonify(ok=True,session_id=current['session_id'],generation=lifecycle_generation[0])

    @app.get('/api/board/control')
    def board_control():
        if not secrets.compare_digest(request.headers.get('X-Watcher-Token', ''), app.config['WATCHER_TOKEN']):
            return jsonify(message='页面已失效。'), 403
        source = app.config.get('BOARD_CONTROL_SOURCE')
        return jsonify(source() if source else {})

    @app.post('/api/events')
    def event_create():
        body = json_body()
        try:
            # Reuse the image validation boundary before persisting caller bytes.
            camera_payload(dict(task='event evidence', frames=[dict(image=body.get('before'), seconds_ago=1), dict(image=body.get('after'), seconds_ago=0)]))
            with lifecycle_lock:
                event_id = store.save_event(int(body['task_id']), base64.b64decode(body['before'].split(',',1)[1]),
                    base64.b64decode(body['after'].split(',',1)[1]), float(body['time']), float(body['confidence']))
                publish(display['status'])
        except (KeyError, ValueError, TypeError, OSError):
            return jsonify(message='事件或图片无效。'), 400
        return jsonify(event=next(e for e in store.events() if e['id'] == event_id))

    @app.delete('/api/events')
    def events_clear():
        with lifecycle_lock:
            store.clear_events()
            publish(display['status'])
        return jsonify(ok=True)

    @app.delete('/api/events/<int:event_id>')
    def event_delete(event_id):
        with lifecycle_lock:
            store.delete_event(event_id)
            publish(display['status'])
        return jsonify(ok=True)

    @app.get('/api/events/<int:event_id>/<which>')
    def event_image(event_id, which):
        raw = store.image(event_id, which)
        return Response(raw, mimetype='image/png' if raw and raw.startswith(b'\x89PNG') else 'image/jpeg') if raw is not None else ('', 404)


    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; media-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
        return response

    @app.get('/')
    def home():
        return render_template('index.html', token=app.config['WATCHER_TOKEN'], ready=bool(load_key()))

    @app.errorhandler(413)
    def too_large(error):
        return jsonify(status='error', message='图片请求过大，请降低采集分辨率。'), 413

    @app.post('/api/judge')
    def evaluate():
        if not secrets.compare_digest(request.headers.get('X-Watcher-Token', ''), app.config['WATCHER_TOKEN']):
            return jsonify(status='error', message='页面已失效，请刷新重试。'), 403
        if not request.is_json:
            return jsonify(status='error', message='请求格式无效。'), 400
        if not app.config['JUDGE_LOCK'].acquire(blocking=False):
            return jsonify(status='error', message='上一次判断尚未结束，请稍候。'), 429
        try:
            try:
                body = request.get_json(silent=True)
                if isinstance(body, dict):
                    if body.get('task_id') is not None:
                        if type(body['task_id']) is not int:
                            raise ValueError('Invalid task id')
                        saved = store.task(body['task_id'])
                        if not saved:
                            raise ValueError('Unknown task')
                        body = dict(body, task=saved['plan']['instruction'])
                    elif not injected_judge:
                        plan = compiler(body.get('task'))
                        body = dict(body, task=plan['instruction'])
                payload = camera_payload(body)
            except (ValueError, TypeError, OSError, KeyError):
                return jsonify(status='error', message='任务或图片无效；每张图片宽高需为 280–1568 像素。'), 400
            started = time.monotonic()
            try:
                decision = read_decision(judge(payload))
            except urllib.error.HTTPError as exc:
                return jsonify(status='error', message=f'模型服务返回 HTTP {exc.code}，看守已暂停。'), 502
            except (ValueError, TypeError, OSError, KeyError):
                return jsonify(status='error', message='模型暂时无法判断或连接失败，看守已暂停。'), 502
            decision['latency_seconds'] = round(time.monotonic() - started, 3)
            return jsonify(decision)
        finally:
            app.config['JUDGE_LOCK'].release()

    def publish_gateway(value):
        # Display status is shared by the current owner, while both capture
        # engines keep their own references, generations and session IDs.
        display['status'] = value['status']
        if status_sink:
            status_sink(value)

    gateway = attach_gateway(app, store, judge, lifecycle_lock, stop_browser, publish_gateway)
    attach_voice(app, directory, transcriber, lifecycle_lock, invalidate,
                 lambda: lifecycle_generation[0], stop_session, publish, store, compiler)
    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=8765, debug=False, threaded=True)

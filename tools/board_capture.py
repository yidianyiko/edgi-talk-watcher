"""Bounded board-camera sessions over the existing single-owner UART bridge."""
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
import uuid

from tools.continuous_watch import windows_path


def board_capture_runner(app, link, host, port, token_file, output_root, *,
                         seconds=300, interval=5, max_calls=60,
                         startup_timeout=38, stop_timeout=12, poll_interval=.1):
    if not (1 <= seconds <= 86400 and 5 <= interval <= 3600 and 1 <= max_calls <= 1000):
        raise ValueError('Invalid bounded board capture budget')
    active = [None]
    active_lock = threading.Lock()

    def frame_ready(session):
        # Called under the app lifecycle lock; never wait or call back into it.
        with active_lock:
            pending = active[0]
            if pending and session == pending[0]+'_1':
                pending[1].set()
    app.config['BOARD_FRAME_READY'] = frame_ready

    def run(stop, generation, on_ready):
        seed = uuid.uuid4().hex
        prime = threading.Event()
        request = admitted = None
        outcome = 'cancelled'
        folder = Path(output_root)/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-'+seed[:8])
        folder.mkdir(parents=True, exist_ok=False)
        try:
            if stop.is_set():
                return
            reservation = app.config['BOARD_CAMERA_ADMIT'](generation, seed)
            admitted = reservation['generation']
            task = reservation['task']
            with active_lock:
                active[0] = (seed, prime)
            request = link.camera_command('start', host=host, port=port,
                token_file=windows_path(Path(token_file)), session_seed=seed,
                task_id=task['id'], task_label='camera', seconds=seconds,
                interval=interval, max_calls=max_calls)
            deadline = time.monotonic()+startup_timeout
            ready = False
            while not stop.wait(poll_interval):
                current_generation = app.config.get('VOICE_GENERATION')
                if current_generation and current_generation() != admitted:
                    outcome = 'superseded'
                    break
                reply = link.camera_reply(request)
                if reply and reply.get('status') in {'failed', 'stopped'}:
                    outcome = reply.get('status')
                    break
                if not ready and prime.is_set():
                    ready = True
                    outcome = 'running'
                    on_ready(admitted)
                if not ready and time.monotonic() >= deadline:
                    outcome = 'startup_timeout'
                    break
                if ready and time.monotonic() >= deadline+seconds:
                    outcome = 'host_deadline'
                    break
        finally:
            if stop.is_set() and outcome == 'running':
                outcome = 'paused'
            with active_lock:
                active[0] = None
            if admitted is not None:
                # Invalidate HTTP admission before requesting UART cancellation.
                app.config['BOARD_CAMERA_STOP'](admitted)
            if request is not None:
                pause = link.camera_command('pause')
                deadline = time.monotonic()+stop_timeout
                while time.monotonic() < deadline:
                    reply = link.camera_reply(pause)
                    if reply and reply.get('status') in {'stopped', 'failed'}:
                        break
                    time.sleep(poll_interval)
                else:
                    outcome = 'stop_timeout'
            (folder/'summary.json').write_text(json.dumps({
                'source': 'board-camera', 'session_seed': seed,
                'generation': admitted, 'outcome': outcome,
                'seconds': seconds, 'interval': interval, 'max_uploads': max_calls,
            }, indent=2)+'\n')
    return run

"""One bounded PC camera session owned by explicit board voice commands."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import threading
import time
import urllib.error
from concurrent.futures import Future, InvalidStateError

from tools.pc_camera_relay import ProductClient, live_frames, relay_frames
from tools.continuous_watch import windows_path
from tools.replay_session import load_recording, sample_frames
from watcher.app import ROOT


class CameraSupervisor:
    def __init__(self, run, *, ticket, track_ready=False):
        self.run, self.ticket = run, ticket
        self.lock = threading.Lock()
        self.worker = None
        self.stop = None
        self.closed = False
        self.pending = None
        self.track_ready = track_ready
        self.ready = None

    def _begin(self, ticket, readiness=None):
        self.stop = threading.Event()
        self.ready = readiness or Future()
        own_ready = self.ready
        own_stop = self.stop
        own_ready.add_done_callback(lambda future: own_stop.set() if future.cancelled() else None)
        def signal_ready(stop, success, admitted=None):
            try:
                own_ready.set_result({'ready': success and not stop.is_set(), 'generation': ticket if admitted is None else admitted})
            except InvalidStateError:
                # Timeout cancellation may race this commit; cleanup must still run.
                pass
        def invoke(stop, generation):
            try:
                if self.track_ready:
                    self.run(stop, generation, lambda admitted=None: signal_ready(stop, True, admitted))
                else:
                    self.run(stop, generation)
            except Exception:
                # A failed worker is observable through its startup future.
                pass
            finally:
                signal_ready(stop, False)
                with self.lock:
                    if self.pending is not None and not self.closed:
                        (next_ticket, next_ready), self.pending = self.pending, None
                        self._begin(next_ticket, next_ready)
        self.worker = threading.Thread(target=invoke, args=(self.stop, ticket),
                                       name='voice-pc-camera', daemon=True)
        self.worker.start()

    @property
    def running(self):
        with self.lock:
            return bool(self.worker and self.worker.is_alive())

    def __call__(self, action):
        with self.lock:
            if action == 'pause':
                if self.pending and not self.pending[1].done():
                    self.pending[1].set_result({'ready':False, 'generation':self.ticket()})
                self.pending = None
                if self.stop:
                    self.stop.set()
                return True
            if action != 'start' or self.closed:
                return False
            if self.worker and self.worker.is_alive():
                if self.stop.is_set():
                    queued = Future()
                    self.pending = (self.ticket(), queued)
                    return queued if self.track_ready else True
                return self.ready if self.track_ready else True
            self._begin(self.ticket())
            return self.ready if self.track_ready else True

    def close(self):
        with self.lock:
            self.closed = True
            if self.pending and not self.pending[1].done():
                self.pending[1].set_result({'ready':False, 'generation':-1})
            self.pending = None
            if self.stop:
                self.stop.set()
            worker = self.worker
        if worker:
            worker.join(timeout=40)


class VoiceClient(ProductClient):
    def __init__(self, url, ticket, stop, on_ready=None):
        super().__init__(url)
        self.ticket, self.stop = ticket, stop
        self.on_ready = on_ready
        self.admitted_generation = None

    def post(self, path, body, **kwargs):
        if path == '/api/control' and body.get('action') == 'start':
            body = dict(body, voice_generation=self.ticket)
            deadline = time.monotonic() + 30
            while not self.stop.is_set():
                try:
                    result = super().post(path, body, **kwargs)
                    self.admitted_generation = result['generation']
                    return result
                except urllib.error.HTTPError as exc:
                    # Wait only for the previous visual call to release its lock.
                    # This does not retry model requests or override stale tickets.
                    if exc.code != 429 or time.monotonic() >= deadline:
                        raise
                    self.stop.wait(.2)
            raise OSError('Capture cancelled before start')
        result = super().post(path, body, **kwargs)
        if path == '/api/observe' and self.on_ready:
            ready, self.on_ready = self.on_ready, None
            ready(self.admitted_generation)
        return result


def capture_runner(url, directory, *, recording=None, seconds=300, max_calls=60):
    def run(stop, ticket, on_ready=None):
        output = Path(directory) / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        output.mkdir(parents=True, exist_ok=False)
        camera = log = None
        report = {'stop_reason': 'startup_error'}
        try:
            if stop.is_set():
                return
            client = VoiceClient(url, ticket, stop, on_ready)
            deadline = time.monotonic() + seconds
            if recording:
                frames = sample_frames(load_recording(recording), 10)
            else:
                python_windows = Path('/mnt/c/Users/YDYK/AppData/Local/Python/pythoncore-3.12-64/python.exe')
                ffmpeg = (ROOT / 'artifacts/physical-camera/ffmpeg-path.txt').read_text().strip()
                log = (output / 'camera-host.log').open('w')
                camera = subprocess.Popen([str(python_windows), windows_path(ROOT / 'tools/windows_camera_stream.py'),
                    '--output', windows_path(output), '--ffmpeg', ffmpeg, '--seconds', str(seconds + 5)],
                    stdout=log, stderr=subprocess.STDOUT)
                frames = live_frames(output, camera, deadline, 5, stop)
            report = relay_frames(client, frames, seconds=seconds, max_calls=max_calls,
                                  poll_controls=True, stop=stop)
            if stop.is_set():
                report['stop_reason'] = 'paused'
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            report['error_type'] = type(exc).__name__
        finally:
            if camera:
                (output / 'camera.stop').touch()
                try:
                    camera.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    camera.terminate()
                    camera.wait(timeout=5)
                    report['forced_stop'] = True
                report['camera_exit'] = camera.returncode
            if log:
                log.close()
            report['source'] = 'recording' if recording else 'PC USB 2.0 Camera'
            (output / 'summary.json').write_text(json.dumps(report, indent=2))
    return run

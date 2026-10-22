import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from watcher.board_link import FileBoardLink


class BoardCameraBoundaryTests(unittest.TestCase):
    def test_private_commands_and_correlated_replies(self):
        with tempfile.TemporaryDirectory() as folder:
            link = FileBoardLink(folder)
            identity = link.camera_command('pause')
            command = json.loads(link.camera_file.read_text())
            self.assertEqual(command, {'request_id': identity, 'action': 'pause'})
            self.assertEqual(link.camera_file.stat().st_mode & 0o777, 0o600)
            link.camera_ack_file.write_text(json.dumps({'request_id': 'old', 'status': 'stopped'}))
            self.assertIsNone(link.camera_reply(identity))
            link.camera_ack_file.write_text(json.dumps({'request_id': identity, 'status': 'stopped'}))
            self.assertEqual(link.camera_reply(identity)['status'], 'stopped')
            link.close()

    def test_runner_waits_for_actual_matching_prime_and_stops(self):
        from tools.board_capture import board_capture_runner
        with tempfile.TemporaryDirectory() as folder:
            link = FileBoardLink(folder)
            app = SimpleNamespace(config={})
            stopped = []
            app.config['BOARD_CAMERA_ADMIT'] = lambda generation, seed: {'generation': 7, 'task': {'id': 1, 'plan': {'target': 'hand'}}}
            app.config['BOARD_CAMERA_STOP'] = stopped.append
            stop = threading.Event()
            ready = []
            with patch('tools.board_capture.windows_path', side_effect=str):
                runner = board_capture_runner(app, link, '192.168.1.2', 8766, Path(folder)/'token', Path(folder)/'recordings', poll_interval=.005)
                worker = threading.Thread(target=runner, args=(stop, 6, ready.append))
                worker.start()
                self.wait(lambda: link.camera_file.exists())
                command = json.loads(link.camera_file.read_text())
                self.assertEqual(command['task_id'], 1)
                link.camera_ack_file.write_text(json.dumps({'request_id': command['request_id'], 'status': 'running'}))
                app.config['BOARD_FRAME_READY']('wrong_1')
                time.sleep(.02)
                self.assertEqual(ready, [])
                app.config['BOARD_FRAME_READY'](command['session_seed']+'_1')
                self.wait(lambda: ready == [7])
                stop.set()
                self.wait(lambda: json.loads(link.camera_file.read_text())['action'] == 'pause')
                pause = json.loads(link.camera_file.read_text())
                link.camera_ack_file.write_text(json.dumps({'request_id': pause['request_id'], 'status': 'stopped'}))
                worker.join(1)
                self.assertFalse(worker.is_alive())
                self.assertEqual(stopped, [7])
                self.assertEqual(len(list((Path(folder)/'recordings').glob('*/summary.json'))), 1)
            link.close()

    def test_failed_start_never_reports_ready_and_invalidates_before_stop(self):
        from tools.board_capture import board_capture_runner
        class Bridge:
            def __init__(self):
                self.commands = []
            def camera_command(self, action, **fields):
                self.commands.append(action)
                return action
            def camera_reply(self, identity):
                return {'status': 'failed' if identity == 'start' else 'stopped'}
        with tempfile.TemporaryDirectory() as folder:
            bridge = Bridge()
            app = SimpleNamespace(config={})
            app.config['BOARD_CAMERA_ADMIT'] = lambda generation, seed: {'generation': 4, 'task': {'id': 1}}
            app.config['BOARD_CAMERA_STOP'] = lambda generation: self.assertEqual(bridge.commands, ['start'])
            ready = []
            with patch('tools.board_capture.windows_path', side_effect=str):
                run = board_capture_runner(app, bridge, '192.168.1.2', 8766, Path(folder)/'token', folder, poll_interval=.001)
                run(threading.Event(), 3, ready.append)
            self.assertEqual(ready, [])
            self.assertEqual(bridge.commands, ['start', 'pause'])
            report = json.loads(next(Path(folder).glob('*/summary.json')).read_text())
            self.assertEqual(report['outcome'], 'failed')

    def test_superseded_generation_stops_before_waiting_for_another_frame(self):
        from tools.board_capture import board_capture_runner
        class Bridge:
            def __init__(self):
                self.commands = []
            def camera_command(self, action, **fields):
                self.commands.append(action)
                return action
            def camera_reply(self, identity):
                return {'status': 'stopped'} if identity == 'pause' else None
        with tempfile.TemporaryDirectory() as folder:
            bridge = Bridge()
            app = SimpleNamespace(config={
                'BOARD_CAMERA_ADMIT': lambda generation, seed: {'generation': 8, 'task': {'id': 1}},
                'BOARD_CAMERA_STOP': lambda generation: None,
                'VOICE_GENERATION': lambda: 9,
            })
            with patch('tools.board_capture.windows_path', side_effect=str):
                run = board_capture_runner(app, bridge, '192.168.1.2', 8766, Path(folder)/'token', folder, poll_interval=.001)
                run(threading.Event(), 7, lambda value: self.fail('Stale session reported ready'))
            self.assertEqual(bridge.commands, ['start', 'pause'])
            self.assertEqual(json.loads(next(Path(folder).glob('*/summary.json')).read_text())['outcome'], 'superseded')

    @staticmethod
    def wait(predicate):
        limit = time.monotonic()+1
        while not predicate():
            if time.monotonic() > limit:
                raise AssertionError('Boundary did not reach expected state')
            time.sleep(.005)

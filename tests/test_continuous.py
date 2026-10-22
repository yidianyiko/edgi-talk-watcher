import tempfile
import unittest
import subprocess
from unittest.mock import Mock
from pathlib import Path
from tools.continuous_watch import run_session
from tools.windows_camera_stream import stop_camera


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now
    def sleep(self, n): self.now += n


class ContinuousTests(unittest.TestCase):
    def test_uncertain_reference_expires_after_thirty_seconds(self):
        clock = Clock()
        pairs = []
        def capture(): return {'path': str(clock()), 'time': clock()}
        def judge(task, before, after):
            pairs.append((before['path'], after['path']))
            return {'status': 'uncertain'}
        with tempfile.TemporaryDirectory() as folder:
            run_session('arrival', 36, 5, 60, capture, judge,
                lambda status: None, Path(folder), clock=clock, wait=clock.sleep)
        self.assertEqual(pairs[-2], ('0', '30'))
        self.assertEqual(pairs[-1], ('30', '35'))

    def test_uncertain_frame_keeps_clear_reference_for_next_arrival(self):
        clock = Clock()
        frames = iter(['empty', 'arm', 'person'])
        pairs, alerts = [], []
        def capture(): return {'path': next(frames), 'time': clock()}
        def judge(task, before, after):
            pair = (before['path'], after['path'])
            pairs.append(pair)
            # Saved real-frame replay: empty->person is confident; arm->person is not.
            return {'status': 'event' if pair == ('empty', 'person') else 'uncertain'}
        with tempfile.TemporaryDirectory() as folder:
            report = run_session('arrival', 11, 5, 60, capture, judge,
                lambda status: None, Path(folder), clock=clock, wait=clock.sleep, alert=alerts.append)
        self.assertEqual(pairs, [('empty', 'arm'), ('empty', 'person')])
        self.assertEqual(report['events'], 1)
        self.assertEqual(len(alerts), 1)

    def test_stop_drains_camera_pipe_without_publishing_more_frames(self):
        from tools.windows_camera_stream import camera_chunks
        stream = Mock()
        stream.read.side_effect = [b'active', b'buffered', b'final', b'']
        stopping = Mock(side_effect=[False, True, True])
        self.assertEqual(list(camera_chunks(stream, stopping)), [b'active'])
        self.assertEqual(stream.read.call_count, 4)

    def test_deadline_timeout_is_duration_but_early_timeout_is_error(self):
        for seconds, expected in [(5, 'duration'), (2, 'error')]:
            clock = Clock()
            def judge(*args):
                clock.sleep(seconds)
                raise TimeoutError('request budget')
            with tempfile.TemporaryDirectory() as folder:
                report = run_session('watch', 10, 5, 60,
                    lambda: {'path': 'frame.jpg', 'time': clock()}, judge,
                    lambda status: None, Path(folder), clock=clock, wait=clock.sleep)
            self.assertEqual(report['stop_reason'], expected)

    def test_frozen_camera_escalates_to_kill_and_waits(self):
        proc = Mock()
        proc.wait.side_effect = [subprocess.TimeoutExpired('ffmpeg', 3), 0]
        stop_camera(proc)
        proc.stdin.write.assert_called_once_with(b'q\n')
        proc.kill.assert_called_once()
        self.assertEqual(proc.wait.call_count, 2)

    def test_capture_crossing_deadline_does_not_call_model(self):
        clock = Clock()
        calls = []
        def capture():
            if clock() > 0: clock.sleep(6)
            return {'path': 'frame.jpg', 'time': clock()}
        with tempfile.TemporaryDirectory() as folder:
            report = run_session('watch', 10, 5, 60, capture,
                lambda *args: calls.append(args), lambda status: None,
                Path(folder), clock=clock, wait=clock.sleep)
        self.assertFalse(calls)
        self.assertEqual(report['decision_attempts'], 0)

    def run_case(self, choices, duration=40, judge_override=None):
        clock = Clock()
        states, alerts = [], []
        def capture(): return {'path': 'frame.jpg', 'time': clock()}
        def judge(*args): return {'status': choices.pop(0)}
        with tempfile.TemporaryDirectory() as folder:
            report = run_session('watch', duration, 5, 60, capture, judge_override or judge,
                states.append, Path(folder), clock=clock, wait=clock.sleep, alert=alerts.append)
        return report, states, alerts

    def test_sequential_duration_and_event_latch(self):
        report, states, alerts = self.run_case(['event','event','uncertain','event','no_event','event','uncertain'])
        self.assertEqual(report['elapsed_seconds'], 40)
        self.assertEqual(report['decision_attempts'], 7)
        self.assertEqual(len(alerts), 2)
        self.assertEqual(states[-1], 'paused')
        self.assertEqual(report['stop_reason'], 'duration')

    def test_model_error_pauses_instead_of_no_event(self):
        def fail(*args): raise OSError('network')
        report, states, alerts = self.run_case([], judge_override=fail)
        self.assertEqual(report['stop_reason'], 'error')
        self.assertEqual(report['decision_attempts'], 1)
        self.assertNotIn('watching', states)
        self.assertEqual(states[-1], 'paused')
        self.assertFalse(alerts)

    def test_result_after_deadline_cannot_alert_or_publish_event(self):
        clock = Clock()
        states, alerts = [], []
        def judge(*args):
            clock.sleep(8)
            return {'status': 'event'}
        with tempfile.TemporaryDirectory() as folder:
            report = run_session('watch', 10, 5, 60,
                lambda: {'path': 'frame.jpg', 'time': clock()}, judge,
                states.append, Path(folder), clock=clock, wait=clock.sleep, alert=alerts.append)
        self.assertEqual(report['discarded_late_results'], 1)
        self.assertFalse(alerts)
        self.assertNotIn('event', states)
        self.assertEqual(states[-1], 'paused')

    def test_stale_camera_stops_before_any_model_call(self):
        clock = Clock()
        states = []
        def judge(*args): self.fail('Stale frames must not reach model')
        with tempfile.TemporaryDirectory() as folder:
            report = run_session('watch', 10, 5, 60,
                lambda: {'path': 'frame.jpg', 'time': 0}, judge,
                states.append, Path(folder), clock=clock, wait=clock.sleep)
        self.assertEqual(report['stop_reason'], 'error')
        self.assertEqual(report['decision_attempts'], 0)
        self.assertEqual(states[-1], 'paused')

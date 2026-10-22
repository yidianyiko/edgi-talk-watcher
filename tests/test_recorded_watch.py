import json
from pathlib import Path
import tempfile
import unittest

from watcher.task_plan import validate_plan, compile_task
from tools.replay_watch import evaluate_cases


class TaskPlanTests(unittest.TestCase):
    def test_translation_preserves_original_and_rejects_invalid_plan(self):
        translated = {'supported': True, 'target': 'hand', 'transition': 'disappears',
                      'instruction': 'Alert me when the hand visible in the earlier image is absent in the latest image. If a hand is still visible, there is no event. An obstructed view is uncertain.',
                      'reason': ''}
        plan = compile_task('手离开时提醒我', translator=lambda text: translated)
        self.assertEqual(plan['original_task'], '手离开时提醒我')
        self.assertEqual(plan['transition'], 'disappears')
        with self.assertRaises(ValueError):
            validate_plan({**translated, 'transition': 'guess'})
        with self.assertRaises(ValueError):
            compile_task('   ', translator=lambda text: translated)

    def test_unsupported_task_cannot_be_sent_to_model(self):
        with self.assertRaises(ValueError):
            compile_task('预测明天股票涨跌', translator=lambda text: {
                'supported': False, 'target': '', 'transition': 'unsupported',
                'instruction': '', 'reason': 'Not observable from images'})


class ReplayTests(unittest.TestCase):
    def test_offline_never_calls_model_and_live_stops_on_error(self):
        cases = [{'id': 'leave', 'expected': 'event', 'frames': [
            {'path': 'a.jpg', 'seconds_ago': 3}, {'path': 'b.jpg', 'seconds_ago': 0}]}]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            from PIL import Image
            for name in ('a.jpg', 'b.jpg'):
                Image.new('RGB', (320, 320)).save(root/name)
            plan = compile_task('手离开', translator=lambda _: {
                'supported': True, 'target': 'hand', 'transition': 'disappears',
                'instruction': 'Alert when a previously visible hand leaves.', 'reason': ''})
            calls = []
            def judge(payload):
                calls.append(payload)
                raise OSError('transport')
            report = evaluate_cases(cases, root, plan, judge=None)
            self.assertEqual(report['model_calls'], 0)
            self.assertIsNone(report['passed'])
            self.assertEqual(report['cases'][0]['status'], 'not_evaluated')
            report = evaluate_cases(cases*2, root, plan, judge=judge)
            self.assertEqual(len(calls), 1)
            self.assertFalse(report['complete'])
            self.assertFalse(report['passed'])
            self.assertEqual(report['cases'][0]['status'], 'error')

    def test_occlusion_false_alert_is_reported_separately(self):
        from tools.replay_watch import summarize
        result = summarize([{'expected': 'uncertain', 'status': 'event'},
                            {'expected': 'event', 'status': 'uncertain'},
                            {'expected': 'no_event', 'status': 'no_event'}])
        self.assertEqual(result, {'exact_matches': 1, 'false_alerts': 1, 'missed_events': 1, 'evaluated': 3})

class ArchiveTests(unittest.TestCase):
    def test_missing_recording_is_not_a_valid_archive(self):
        from tools.archive_recordings import verify
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'index.json').write_text(json.dumps([{'id': 'missing', 'frames': 1, 'preview_sha256': 'x'}]))
            # An unrelated valid recording must not hide loss of the indexed one.
            other = root/'other'
            other.mkdir()
            import hashlib
            sha = hashlib.sha256(b'video').hexdigest()
            (other/'preview.mp4').write_bytes(b'video')
            (other/'image.jpg').write_bytes(b'frame')
            (other/'image.json').write_bytes(b'metadata')
            (other/'recording.json').write_text(json.dumps({'frames': [{'path': 'image.jpg',
                'sha256': hashlib.sha256(b'frame').hexdigest(),
                'metadata_sha256': hashlib.sha256(b'metadata').hexdigest()}], 'preview_sha256': sha}))
            with self.assertRaises(ValueError):
                verify(root)

if __name__ == '__main__':
    unittest.main()

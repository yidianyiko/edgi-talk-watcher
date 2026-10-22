import json
from pathlib import Path
import tempfile
import unittest
from tools.replay_session import load_recording, sample_frames, replay_session, CachedJudge

PLAN = json.loads(Path('testdata/plans/person-appears.json').read_text())

class ReplayTests(unittest.TestCase):
    def test_original_timestamps_and_tail(self):
        frames = [{'path':str(t), 'time':t} for t in (0,3,9,11,18,23)]
        self.assertEqual([f['time'] for f in sample_frames(frames,10)], [0,11,23])
        self.assertEqual(sample_frames(frames,100)[-1]['time'],23)

    def test_limit_reports_uncovered_tail(self):
        frames = [{'path':str(t), 'time':t} for t in (0,10,20,23)]
        report = replay_session(frames,PLAN,lambda *a:{'status':'no_event'},max_calls=1)
        self.assertFalse(report['complete'])
        self.assertEqual(report['covered_until'],10)
        self.assertEqual(report['stop_reason'],'call_limit')

    def test_cached_replay_is_exact_and_rejects_wrong_pair(self):
        frames = [{'path':str(t), 'time':t} for t in (0,10,20)]
        original = replay_session(frames,PLAN,lambda *a:{'status':'event'})
        replay = replay_session(frames,PLAN,CachedJudge(original['rounds']))
        self.assertEqual(original['rounds'],replay['rounds'])
        with self.assertRaises(ValueError): CachedJudge(original['rounds'])(PLAN,frames[1],frames[0])

    def test_cached_log_is_bound_to_task_plan(self):
        frames = [{'path':str(t), 'time':t} for t in (0,10)]
        report = replay_session(frames,PLAN,lambda *a:{'status':'no_event'})
        wrong = {**PLAN, 'target':'another target', 'instruction':'Another target appears'}
        with self.assertRaises(ValueError): CachedJudge(report['rounds'])(wrong,frames[0],frames[1])

    def test_all_archive_bytes_validated_before_billing(self):
        frames = load_recording(Path('testdata/recordings/hand-removal'))
        self.assertEqual(len(frames),76)
        self.assertLess(frames[0]['time'],frames[-1]['time'])

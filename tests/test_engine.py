import unittest
from watcher.engine import WatchEngine

PLAN = {'supported': True, 'target': 'object', 'transition': 'appears', 'instruction': 'Object appears', 'reason': ''}
def frame(t): return {'path': str(t)+'.jpg', 'time': t}

class EngineTests(unittest.TestCase):
    def test_reference_latch_and_uncertain(self):
        engine = WatchEngine(PLAN)
        pairs = []
        states = iter(['uncertain', 'event', 'uncertain', 'event', 'no_event', 'event'])
        def judge(plan, before, after):
            pairs.append((before['time'], after['time']))
            return {'status': next(states)}
        results = [engine.observe(frame(t), judge) for t in range(0, 31, 5)]
        self.assertEqual(pairs[:2], [(0,5), (0,10)])
        self.assertEqual([x['after']['time'] for x in results if x['alert']], [10,30])

    def test_late_and_paused_results_are_discarded(self):
        for pause in (False, True):
            now = [0]
            engine = WatchEngine(PLAN, deadline=10, clock=lambda: now[0])
            engine.observe(frame(0), None)
            def judge(*args):
                if pause: engine.pause()
                else: now[0] = 10
                return {'status': 'event'}
            self.assertTrue(engine.observe(frame(5), judge)['discarded'])
            self.assertFalse(engine.latched)

    def test_error_pauses_and_limit_blocks_calls(self):
        engine = WatchEngine(PLAN, max_calls=1)
        engine.observe(frame(0), None)
        def fail(*args): raise OSError('secret must not appear')
        with self.assertRaises(OSError): engine.observe(frame(5), fail)
        self.assertTrue(engine.paused)
        self.assertEqual(engine.calls, 1)
        self.assertEqual(engine.observe(frame(10), fail)['status'], 'paused')

    def test_old_request_error_cannot_pause_reset_task(self):
        engine = WatchEngine(PLAN)
        new_plan = {**PLAN, 'target': 'new object', 'instruction': 'New object appears'}
        engine.observe(frame(0), None)
        def stale_failure(*args):
            engine.reset(new_plan)
            raise OSError('Previous request failed after new task started')
        result = engine.observe(frame(5), stale_failure)
        self.assertEqual(result['status'], 'discarded')
        self.assertTrue(result['discarded'])
        self.assertFalse(result['alert'])
        self.assertFalse(engine.paused)
        self.assertEqual(engine.plan, new_plan)
        self.assertEqual(engine.calls, 0)
        self.assertIsNone(engine.reference)
        self.assertEqual(engine.observe(frame(10), None)['status'], 'preparing')
        decision = engine.observe(frame(15), lambda *a: {'status': 'event'})
        self.assertTrue(decision['alert'])

    def test_expiry_and_stale_input(self):
        engine = WatchEngine(PLAN)
        pairs=[]
        def judge(p,b,a):
            pairs.append((b['time'],a['time']))
            return {'status':'uncertain'}
        for t in (0,15,30,35): engine.observe(frame(t),judge)
        self.assertEqual(pairs[-1], (30,35))
        with self.assertRaises(ValueError): engine.observe(frame(35),judge)

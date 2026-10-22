"""Sequential watcher policy shared by recorded and physical-camera sessions."""
import math
import time
from watcher.task_plan import FIELDS, validate_plan


class WatchEngine:
    def __init__(self, plan, *, reference_seconds=30, max_calls=None, deadline=None,
                 clock=time.monotonic):
        self.plan = validate_plan({k: plan[k] for k in FIELDS})
        self.reference_seconds = reference_seconds
        self.max_calls, self.deadline, self.clock = max_calls, deadline, clock
        self.generation = 0
        self.reset()

    def reset(self, plan=None):
        if plan is not None:
            self.plan = validate_plan({k: plan[k] for k in FIELDS})
        self.generation += 1
        self.reference = self.last_frame = None
        self.latched = self.paused = False
        self.calls = 0

    def pause(self):
        self.paused = True
        self.generation += 1

    def observe(self, frame, judge):
        result = {'status': 'preparing', 'alert': False, 'before': self.reference,
                  'after': dict(frame), 'discarded': False}
        if self.paused:
            return {**result, 'status': 'paused'}
        if self.deadline is not None and self.clock() >= self.deadline:
            return {**result, 'status': 'deadline', 'discarded': True}
        stamp = frame['time']
        if isinstance(stamp, bool) or not isinstance(stamp, (float,int)) or not math.isfinite(stamp):
            raise ValueError('Frame time must be finite')
        if self.last_frame is not None and stamp <= self.last_frame['time']:
            raise ValueError('Camera did not provide a fresh frame')
        if self.reference is None:
            self.reference = self.last_frame = dict(frame)
            return result
        if self.max_calls is not None and self.calls >= self.max_calls:
            return {**result, 'status': 'call_limit'}
        if stamp-self.reference['time'] > self.reference_seconds:
            self.reference = self.last_frame
        before = dict(self.reference)
        generation = self.generation
        self.calls += 1
        try:
            decision = judge(self.plan, before, frame)
            if generation != self.generation or (self.deadline is not None and self.clock() >= self.deadline):
                return {**result, 'before': before, 'status': 'discarded', 'discarded': True}
            if decision['status'] not in ('event','no_event','uncertain'):
                raise ValueError('Invalid decision status')
        except Exception:
            if generation != self.generation:
                return {**result, 'before': before, 'status': 'discarded', 'discarded': True}
            self.pause()
            raise
        status = decision['status']
        alert = status == 'event' and not self.latched
        if status == 'event': self.latched = True
        if status == 'no_event': self.latched = False
        if status != 'uncertain': self.reference = dict(frame)
        self.last_frame = dict(frame)
        return {**decision, 'alert': alert, 'before': before, 'after': dict(frame),
                'discarded': False, 'generation': generation}

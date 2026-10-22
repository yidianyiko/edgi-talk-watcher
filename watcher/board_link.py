"""File boundary between local product runtime and leased Windows serial bridge."""
import hashlib
import json
from pathlib import Path
import re
import threading
import uuid

STATES = {'idle', 'watching', 'event', 'uncertain', 'paused'}
ACTIONS = {'start', 'pause', 'next', 'history'}


def atomic_json(path, value):
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False)+'\n')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class FileBoardLink:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_file = self.root/'board-state.json'
        self.control_file = self.root/'board-control.json'
        self.alive_file = self.root/'controller-alive'
        self.alert_ack_file = self.root/'board-alert-ack.json'
        self.camera_file = self.root/'board-camera.json'
        self.camera_ack_file = self.root/'board-camera-ack.json'
        self._pending_alerts = []
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._last_control = 0
        self._state = {'status': 'paused', 'event_count': 0}
        self._closed = False
        try:
            previous = json.loads(self.control_file.read_text())
            self._last_control = max(0, int(previous.get('request_id', 0)))
        except (OSError, ValueError, TypeError):
            pass
        Path(str(self.state_file)+'.stop').unlink(missing_ok=True)
        self.camera_file.unlink(missing_ok=True)
        self.camera_ack_file.unlink(missing_ok=True)
        self.publish({'status': 'paused'})

    def camera_command(self, action, **fields):
        """Submit one private command to the sole Windows UART owner."""
        if action not in {'start', 'pause'}:
            raise ValueError('Invalid camera action')
        with self._lock:
            if self._closed:
                raise RuntimeError('Board link is closed')
            identity = uuid.uuid4().hex
            value = dict(fields, request_id=identity, action=action)
            atomic_json(self.camera_file, value)
            self.camera_file.chmod(0o600)
            return identity

    def camera_reply(self, identity):
        try:
            value = json.loads(self.camera_ack_file.read_text())
            return value if isinstance(value, dict) and value.get('request_id') == identity else None
        except (OSError, ValueError):
            return None

    def publish(self, value):
        with self._lock:
            if self._closed:
                return
            if not isinstance(value, dict):
                raise ValueError('Board update must be an object')
            state = dict(self._state)
            status = value.get('status', state['status'])
            count = value.get('event_count', state['event_count'])
            if status not in STATES or type(count) is not int or not 0 <= count <= 4294967295:
                raise ValueError('Invalid board state')
            state.update(status=status, event_count=count)
            pending = list(self._pending_alerts)
            try:
                acknowledged = json.loads(self.alert_ack_file.read_text()).get('alert_id')
                if acknowledged in pending:
                    pending = pending[pending.index(acknowledged)+1:]
            except (OSError, ValueError, AttributeError):
                pass
            if 'alert_id' in value:
                alert = value['alert_id']
                if not isinstance(alert, str) or not re.fullmatch('[0-9a-f]{32}', alert):
                    raise ValueError('Invalid announcement identity')
                if alert != state.get('alert_id') and alert not in pending:
                    if len(pending) >= 100:
                        raise ValueError('Announcement queue is full')
                    pending.append(alert)
                state['alert_id'] = alert
            state['alert_ids'] = pending
            task = value.get('task')
            if task:
                identity = str(task['id'])
                numeric_id = task['id']
                if type(numeric_id) is int and not 1 <= numeric_id <= 99999999:
                    raise ValueError('Task id exceeds board protocol range')
                label = str(task.get('plan', {}).get('target', 'task'))
                state.update(task_id=numeric_id if type(numeric_id) is int else int(hashlib.sha256(identity.encode()).hexdigest()[:8], 16)%99999999+1,
                             task_label=re.sub('[^A-Za-z0-9_]+', '_', label).strip('_')[:32] or 'task')
            atomic_json(self.state_file, state)
            self._state = state
            self._pending_alerts = pending

    def control(self):
        with self._lock:
            try:
                value = json.loads(self.control_file.read_text())
                sequence, action = value['request_id'], value['action']
                if type(sequence) is not int or sequence <= self._last_control or action not in ACTIONS:
                    return None
                self._last_control = sequence
                return {'request_id': sequence, 'action': action}
            except (OSError, ValueError, KeyError, TypeError):
                return None

    def start(self):
        with self._lock:
            if self._thread or self._closed:
                return
            def heartbeat():
                while not self._stop.is_set():
                    self.alive_file.touch()
                    self.publish({})
                    self._stop.wait(.5)
            self._thread = threading.Thread(target=heartbeat, name='board-lease', daemon=True)
            self._thread.start()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self.publish({'status': 'paused'})
            self._closed = True
            self._stop.set()
            if self._thread:
                self._thread.join(timeout=2)
            Path(str(self.state_file)+'.stop').touch()

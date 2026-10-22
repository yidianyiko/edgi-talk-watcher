"""Committed board-camera events use the same notification FIFO as PC events."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from watcher.app import create_app
from watcher.board_link import FileBoardLink
from tests.test_board_gateway import RAW
from tests.test_web_lifecycle import RESPONSE
from tests.test_web_store import PLAN


class BoardGatewayAlertTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.states = []
        self.link = FileBoardLink(Path(self.folder.name) / 'link')
        self.addCleanup(self.link.close)
        self.app = create_app(judge=lambda _: RESPONSE, compiler=lambda _: PLAN,
                              data_dir=Path(self.folder.name) / 'data', status_sink=self.publish)
        self.addCleanup(self.app.config['BOARD_GATEWAY'].close)
        self.client = self.app.test_client()
        self.web = {'X-Watcher-Token': self.app.config['WATCHER_TOKEN']}
        task = self.client.post('/api/tasks', json={'task': 'cup disappears'}, headers=self.web).json['task']
        self.headers = {'Authorization': 'Bearer ' + self.app.config['BOARD_GATEWAY_TOKEN'],
                        'X-Watch-Task': str(task['id']), 'X-Watch-Width': '320',
                        'X-Watch-Height': '240', 'X-Watch-Session': 'alert-run-1'}

    def publish(self, value):
        if value.get('alert_id'):
            # This callback observes a committed SQLite event, before FIFO delivery.
            self.assertEqual(value['event_count'], len(self.app.config['WATCHER_STORE'].events()))
            self.assertGreater(value['event_count'], 0)
        self.states.append(value)
        self.link.publish(value)

    def frame(self, stamp, reset='0'):
        return self.client.post('/api/board/observe', data=RAW,
                                headers={**self.headers, 'X-Watch-Time': str(stamp), 'X-Watch-Reset': reset})

    def alerts(self):
        return [state['alert_id'] for state in self.states if state.get('alert_id')]

    def test_committed_event_enters_fifo_once_and_history_never_replays_it(self):
        self.assertEqual(self.frame(1000, '1').text, 'watching 0\n')
        self.assertEqual(self.frame(6000).text, 'event 1\n')
        self.assertEqual(self.frame(11000).text, 'event 1\n')
        self.assertEqual(len(self.alerts()), 1)
        self.assertRegex(self.alerts()[0], r'^[0-9a-f]{32}$')
        state = json.loads(self.link.state_file.read_text())
        self.assertEqual(state['alert_ids'], self.alerts())
        self.client.delete('/api/events', headers=self.web)
        self.assertEqual(len(self.alerts()), 1)
        self.app.config['BOARD_GATEWAY'].close()
        reloaded = []
        create_app(data_dir=Path(self.folder.name) / 'data', status_sink=reloaded.append)
        self.assertFalse(any(value.get('alert_id') for value in reloaded))

    def test_uncertain_and_no_event_are_silent_and_separate_events_have_fresh_ids(self):
        decisions = iter(['uncertain', 'no_event', 'event', 'event', 'no_event', 'event'])
        def judge(_):
            choice = next(decisions)
            return {'answers': {'watch': {'type': 'choice', 'choice': choice,
                    'confidence': .95, 'probabilities': {name: .95 if name == choice else .025
                    for name in ('event', 'no_event', 'uncertain')}}}}
        self.app.config['BOARD_GATEWAY'].judge = judge
        self.assertEqual(self.frame(1000, '1').status_code, 200)
        self.assertEqual(self.alerts(), [])
        self.assertEqual(self.frame(6000).text, 'uncertain 0\n')
        self.assertEqual(self.frame(11000).text, 'watching 0\n')
        self.assertEqual(self.alerts(), [])
        for stamp in (16000, 21000, 26000, 31000):
            self.assertEqual(self.frame(stamp).status_code, 200)
        alerts = self.alerts()
        self.assertEqual(len(alerts), 2)
        self.assertNotEqual(alerts[0], alerts[1])
        for alert in alerts:
            self.assertRegex(alert, r'^[0-9a-f]{32}$')
        self.assertEqual(json.loads(self.link.state_file.read_text())['alert_ids'], alerts)

    def test_failed_event_commit_never_requests_audio(self):
        self.frame(1000, '1')
        with patch.object(self.app.config['WATCHER_STORE'], 'save_event', side_effect=OSError('disk full')):
            self.assertEqual(self.frame(6000).status_code, 502)
        self.assertEqual(self.alerts(), [])
        self.assertEqual(self.app.config['WATCHER_STORE'].events(), [])
        self.assertFalse(json.loads(self.link.state_file.read_text()).get('alert_ids'))

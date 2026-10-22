import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from watcher.board_link import FileBoardLink


class BoardLinkTests(unittest.TestCase):
    def test_database_task_id_matches_gateway_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            link=FileBoardLink(Path(folder))
            link.publish({'task': {'id': 1, 'plan': {'target':'hand'}}})
            self.assertEqual(json.loads(link.state_file.read_text())['task_id'],1)
            link.close()

    def test_gateway_token_is_private_stable_and_never_empty(self):
        from tools.run_product import configure_gateway
        import stat
        with tempfile.TemporaryDirectory() as folder:
            app=Mock();app.config={}
            path=configure_gateway(app, Path(folder))
            first=app.config['BOARD_GATEWAY_TOKEN']
            self.assertGreaterEqual(len(first),32)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            configure_gateway(app, Path(folder))
            self.assertEqual(app.config['BOARD_GATEWAY_TOKEN'],first)

    def test_task_decision_and_close_are_written_for_existing_bridge(self):
        with tempfile.TemporaryDirectory() as folder:
            link = FileBoardLink(Path(folder))
            link.publish({'status': 'watching', 'task': {'id': 'abc', 'task': '手离开',
                          'plan': {'target': 'hand'}}, 'event_count': 2})
            state = json.loads(link.state_file.read_text())
            self.assertEqual(state['status'], 'watching')
            self.assertEqual(state['task_label'], 'hand')
            self.assertEqual(state['event_count'], 2)
            self.assertTrue(1 <= state['task_id'] <= 99999999)
            link.close()
            self.assertEqual(json.loads(link.state_file.read_text())['status'], 'paused')
            self.assertTrue(Path(str(link.state_file)+'.stop').exists())

    def test_controls_are_once_only_and_restart_ignores_existing_request(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            link=FileBoardLink(root)
            link.control_file.write_text(json.dumps({'request_id': 1, 'action': 'pause'}))
            self.assertEqual(link.control()['action'], 'pause')
            self.assertIsNone(link.control())
            replacement=FileBoardLink(root)
            self.assertIsNone(replacement.control())
            replacement.control_file.write_text(json.dumps({'request_id': 2, 'action': 'start'}))
            self.assertEqual(replacement.control()['action'], 'start')
            replacement.control_file.write_text('{broken')
            self.assertIsNone(replacement.control())
            replacement.close()

    def test_hyphenated_target_is_compatible_with_board_label(self):
        with tempfile.TemporaryDirectory() as folder:
            link=FileBoardLink(Path(folder))
            link.publish({'task': {'id': 1, 'plan': {'target': 'red-haired person'}}})
            self.assertEqual(json.loads(link.state_file.read_text())['task_label'], 'red_haired_person')
            link.close()

    def test_failed_bridge_cannot_be_reported_ready(self):
        from tools.run_product import wait_board_ready
        with tempfile.TemporaryDirectory() as folder:
            ready=Path(folder)/'board-ready.json'
            ready.write_text('{"ready":true}')
            process=Mock()
            process.poll.return_value=1
            with self.assertRaises(RuntimeError):
                wait_board_ready(process, ready, timeout=0)

    def test_invalid_state_and_unknown_controls_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            link=FileBoardLink(Path(folder))
            with self.assertRaises(ValueError):
                link.publish({'status': 'fake'})
            with self.assertRaises(ValueError):
                link.publish({'status': 'event', 'event_count': -1})
            link.control_file.write_text(json.dumps({'request_id': 3, 'action': 'shell'}))
            self.assertIsNone(link.control())
            self.assertEqual(json.loads(link.state_file.read_text())['status'], 'paused')
            link.close()

if __name__=='__main__':
    unittest.main()

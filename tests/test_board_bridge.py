import unittest
import contextlib
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch, call
from tools import judge_to_board
from tools.judge_to_board import display_status


class BridgeTests(unittest.TestCase):
    def test_model_choices_map_to_screen(self):
        self.assertEqual(display_status('event'), 'event')
        self.assertEqual(display_status('no_event'), 'watching')
        self.assertEqual(display_status('uncertain'), 'uncertain')
        with self.assertRaises(ValueError):
            display_status('error')

    def test_missing_key_pauses_without_claiming_a_model_request(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest = Path(folder) / 'manifest.json'
            report = Path(folder) / 'report.json'
            manifest.write_text(json.dumps({'cases': [{'id': 'test', 'expected': 'uncertain'}]}))
            with patch('sys.argv', ['judge_to_board', str(manifest), '--output', str(report)]), \
                 patch.object(judge_to_board, 'build_request', return_value={}), \
                 patch.object(judge_to_board, 'send_status') as board, \
                 patch('watcher.app.load_key', return_value=''), \
                 patch('watcher.app.urllib.request.urlopen') as network, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(judge_to_board.main(), 1)
            network.assert_not_called()
            self.assertEqual(board.call_args_list, [call('idle', 0), call('paused', 10)])
            result = json.loads(report.read_text())
            self.assertNotIn('model_calls', result)
            self.assertEqual(result['decision_attempts'], 1)
            self.assertTrue(result['board_acknowledged'])


if __name__ == '__main__':
    unittest.main()

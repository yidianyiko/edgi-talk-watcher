import unittest
from unittest.mock import MagicMock as Mock
from tools.run_product import dispatch_board_control

class BoardControlTests(unittest.TestCase):
    def test_start_uses_hardware_supervisor_and_pause_invalidates_http_owner(self):
        app=Mock(); camera=Mock(); client=app.test_client.return_value.__enter__.return_value
        app.config={'WATCHER_TOKEN':'private'}
        self.assertTrue(dispatch_board_control(app,camera,{'action':'start'}))
        camera.assert_called_once_with('start'); client.post.assert_not_called()
        self.assertTrue(dispatch_board_control(app,camera,{'action':'next'}))
        client.post.assert_called_once_with('/api/control',json={'action':'pause'},headers={'X-Watcher-Token':'private'})
        self.assertEqual(camera.call_args.args,('pause',))
        self.assertFalse(dispatch_board_control(app,camera,{'action':'history'}))

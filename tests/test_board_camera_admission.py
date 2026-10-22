"""Managed hardware capture cannot be revived by delayed frames after pause."""
import tempfile
import unittest
from watcher.app import create_app
from tests.test_web_store import PLAN
from tests.test_web_lifecycle import RESPONSE
from tests.test_board_gateway import RAW

class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.app = create_app(judge=lambda _: RESPONSE, compiler=lambda _: PLAN, data_dir=self.tmp.name)
        self.app.config['BOARD_CAMERA_MANAGED'] = True
        self.client = self.app.test_client()
        self.web = {'X-Watcher-Token': self.app.config['WATCHER_TOKEN']}
        self.task = self.client.post('/api/tasks', json={'task':'cup disappears'}, headers=self.web).json['task']
        self.ready = []; self.app.config['BOARD_FRAME_READY'] = self.ready.append
        self.addCleanup(self.app.config['BOARD_GATEWAY'].close)
    def frame(self, seed='reserved', reset='1', stamp='1000'):
        return self.client.post('/api/board/observe', data=RAW, headers={
            'Authorization':'Bearer '+self.app.config['BOARD_GATEWAY_TOKEN'],
            'X-Watch-Task':str(self.task['id']), 'X-Watch-Width':'320', 'X-Watch-Height':'240',
            'X-Watch-Session':seed+'_1','X-Watch-Reset':reset,'X-Watch-Time':stamp})
    def test_reservation_ready_and_pause_rejects_delayed_new_sessions(self):
        self.assertEqual(self.frame().status_code,409)
        generation = self.app.config['VOICE_GENERATION']()
        admitted = self.app.config['BOARD_CAMERA_ADMIT'](generation,'reserved')
        self.assertEqual(admitted['generation'], generation+1)
        self.assertEqual(admitted['task']['id'], self.task['id'])
        self.assertEqual(self.frame().status_code,200)
        self.assertEqual(self.ready,['reserved_1'])
        self.client.post('/api/control', json={'action':'pause'}, headers=self.web)
        self.assertEqual(self.frame(seed='reserved_late').status_code,409)
        self.assertEqual(self.ready,['reserved_1'])
    def test_stale_admission_and_cleanup_cannot_stop_new_owner(self):
        generation = self.app.config['VOICE_GENERATION']()
        first = self.app.config['BOARD_CAMERA_ADMIT'](generation,'first')
        with self.assertRaises(ValueError): self.app.config['BOARD_CAMERA_ADMIT'](generation,'stale')
        second = self.app.config['BOARD_CAMERA_ADMIT'](first['generation'],'second')
        self.app.config['BOARD_CAMERA_STOP'](first['generation'])
        self.assertEqual(self.frame(seed='second').status_code,200)
        self.app.config['BOARD_CAMERA_STOP'](second['generation'])
        self.assertEqual(self.frame(seed='second',reset='0',stamp='6000').status_code,409)

    def test_recording_preserves_each_accepted_frame_with_transport_metadata(self):
        import json
        from pathlib import Path
        recordings=Path(self.tmp.name)/'recordings'
        self.app.config['BOARD_RECORDING_ROOT']=recordings
        generation=self.app.config['VOICE_GENERATION']()
        self.app.config['BOARD_CAMERA_ADMIT'](generation,'saved')
        self.assertEqual(self.frame(seed='saved').status_code,200)
        self.assertEqual(self.frame(seed='saved',reset='0',stamp='6000').status_code,200)
        folder=recordings/'saved_1'
        metadata=[json.loads(line) for line in (folder/'frames.jsonl').read_text().splitlines()]
        self.assertEqual([item['time_ms'] for item in metadata],[1000,6000])
        self.assertEqual((folder/metadata[0]['raw']).read_bytes(),RAW)
        self.assertEqual(len(list(folder.glob('*.jpg'))),2)
        self.assertEqual(metadata[0]['source'],'board-uvc-yuyv-320x240')

    def test_model_failure_frame_is_retained_for_offline_debugging(self):
        from pathlib import Path
        recordings=Path(self.tmp.name)/'failed-recordings'
        self.app.config['BOARD_RECORDING_ROOT']=recordings
        self.app.config['BOARD_CAMERA_ADMIT'](self.app.config['VOICE_GENERATION'](),'failure')
        self.frame(seed='failure')
        def fail(_): raise OSError('model unavailable')
        self.app.config['BOARD_GATEWAY'].judge=fail
        self.assertEqual(self.frame(seed='failure',reset='0',stamp='6000').status_code,502)
        self.assertEqual(len(list((recordings/'failure_1').glob('*.yuyv'))),2)

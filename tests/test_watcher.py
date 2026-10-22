import base64
import io
import unittest
from PIL import Image
from watcher.app import create_app


def image_data():
    out = io.BytesIO()
    Image.new('RGB', (320, 320), 'white').save(out, 'JPEG')
    return 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode()


class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        def judge(payload):
            self.calls.append(payload)
            return {'answers': {'watch': {'type': 'choice', 'choice': 'event',
                    'confidence': .95, 'probabilities': {'event': .96, 'no_event': .02, 'uncertain': .02}}},
                    'model': 'jev-1.14.0', 'usage': {'input_tokens': 20}}
        self.app = create_app(judge=judge)
        self.client = self.app.test_client()
        self.headers = {'X-Watcher-Token': self.app.config['WATCHER_TOKEN']}
        self.body = {'task': 'Tell me when a cup is removed.', 'frames': [
            {'image': image_data(), 'seconds_ago': 3}, {'image': image_data(), 'seconds_ago': 0}]}

    def test_valid_pair_reaches_judge(self):
        r = self.client.post('/api/judge', json=self.body, headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['status'], 'event')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.calls[0]['assets']), 2)

    def test_invalid_frame_never_reaches_paid_judge(self):
        self.body['frames'][0]['image'] = 'data:image/jpeg;base64,broken'
        r = self.client.post('/api/judge', json=self.body, headers=self.headers)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json['status'], 'error')
        self.assertFalse(self.calls)

    def test_untrusted_request_is_rejected(self):
        self.assertEqual(self.client.post('/api/judge', json=self.body).status_code, 403)
        self.assertFalse(self.calls)

    def test_timeout_is_attention_not_no_event(self):
        def fail(payload):
            raise TimeoutError('private detail')
        app = create_app(judge=fail)
        r = app.test_client().post('/api/judge', json=self.body,
                                  headers={'X-Watcher-Token': app.config['WATCHER_TOKEN']})
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.json['status'], 'error')
        self.assertNotIn('private detail', r.get_data(as_text=True))

    def test_inflight_request_blocks_second_judge(self):
        self.app.config['JUDGE_LOCK'].acquire()
        try:
            r = self.client.post('/api/judge', json=self.body, headers=self.headers)
            self.assertEqual(r.status_code, 429)
            self.assertFalse(self.calls)
        finally:
            self.app.config['JUDGE_LOCK'].release()

    def test_home_does_not_expose_env(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get('/.env.local').status_code, 404)

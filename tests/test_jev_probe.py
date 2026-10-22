import base64
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('jev_probe', ROOT / 'research/jev_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def response(choice='event', confidence=0.95, probabilities=None):
    return {'model': 'jev-1.14.0', 'answers': {'watch': {
        'type': 'choice', 'choice': choice, 'confidence': confidence,
        'probabilities': probabilities or {'event': 0.96, 'no_event': 0.02, 'uncertain': 0.02},
    }}, 'usage': {'input_tokens': 1000}}


class ProbeTests(unittest.TestCase):
    def test_all_manifest_metadata_is_validated_before_running(self):
        valid = {'id': 'one', 'expected': 'event'}
        for bad in [{'id': 'two', 'expected': 'typo'}, {'expected': 'event'},
                    {'id': 'one', 'expected': 'no_event'}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                probe.validate_cases([valid, bad])

    def test_low_confidence_never_announces_event(self):
        self.assertEqual(probe.read_decision(response(confidence=0.1))['status'], 'uncertain')

    def test_invalid_probability_never_becomes_decision(self):
        for value in [math.nan, math.inf, -0.1, 1.1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                probe.read_decision(response(probabilities={'event': value, 'no_event': 0, 'uncertain': 0}))

    def test_missing_or_inconsistent_answer_is_rejected(self):
        for value in [{}, response(choice='unknown'), response(probabilities={'event': 0.1}),
                      response(choice='no_event')]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                probe.read_decision(value)

    def test_high_confidence_event_is_kept_and_usage_preserved(self):
        decision = probe.read_decision(response())
        self.assertEqual(decision['status'], 'event')
        self.assertEqual(decision['model'], 'jev-1.14.0')
        self.assertEqual(decision['input_tokens'], 1000)

    def test_fixture_labels_and_names_do_not_leak_into_model_state(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new('RGB', (320, 320), 'white').save(root / 'event.png')
            case = {'id': 'correct_answer_event', 'task': 'Watch for a parcel arriving.',
                    'expected': 'event', 'frames': [
                        {'path': 'event.png', 'seconds_ago': 1},
                        {'path': 'event.png', 'seconds_ago': 0}]}
            payload = probe.build_request(case, root, 'jev-1.14.0')
            self.assertEqual(set(payload['state']), {'task', 'frames'})
            self.assertEqual(payload['questions']['watch']['type'], 'choice')
            self.assertEqual(payload['model'], 'jev-1.14.0')
            refs = [frame['image'] for frame in payload['state']['frames']]
            self.assertEqual(len(set(refs)), 2)
            for ref in refs:
                self.assertNotIn('event', ref)
                self.assertTrue(base64.b64decode(payload['assets'][ref]['data_base64']).startswith(b'\x89PNG'))

    def test_camera_image_below_documented_minimum_is_rejected(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new('RGB', (320, 240)).save(root / 'small.png')
            case = {'task': 'Watch.', 'frames': [{'path': 'small.png', 'seconds_ago': 0}]}
            with self.assertRaisesRegex(ValueError, '280'):
                probe.build_request(case, root, 'jev-1.14.0')


if __name__ == '__main__':
    unittest.main()

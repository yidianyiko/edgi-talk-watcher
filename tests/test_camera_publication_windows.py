"""Windows/WSL publication regression; run with Windows Python."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.windows_camera_stream import atomic_json


@unittest.skipUnless(os.name == 'nt', 'Windows file sharing semantics')
class PublicationTests(unittest.TestCase):
    def test_new_frame_metadata_can_publish_while_previous_reader_is_open(self):
        # Exercise the actual shared WSL filesystem, not a Windows TEMP directory.
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'artifacts') as folder:
            root = Path(folder)
            previous = root/'000001.json'
            atomic_json(previous, {'frame': 1})
            with previous.open('rb') as reader:
                with self.assertRaises(PermissionError):
                    atomic_json(previous, {'frame': 2})
                atomic_json(root/'000002.json', {'frame': 2})
                self.assertEqual(json.loads(reader.read())['frame'], 1)
                self.assertEqual(json.loads((root/'000002.json').read_text())['frame'], 2)


if __name__ == '__main__':
    unittest.main()

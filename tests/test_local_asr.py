"""Optional actual local ASR regression; uses preserved speech, never a person."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = importlib.util.find_spec('faster_whisper') is not None and (ROOT/'var/models/whisper-base/model.bin').is_file()

@unittest.skipUnless(AVAILABLE, 'Install requirements-voice.txt and the pinned local ASR model')
class LocalASRTests(unittest.TestCase):
 def test_preserved_board_microphone_pause_is_correct_with_room_noise(self):
  import wave
  from watcher.voice import LocalTranscriber,command
  with wave.open(str(ROOT/'testdata/voice/board-pause.wav')) as wav:
   pcm=wav.readframes(wav.getnframes())
  text=LocalTranscriber()(pcm)
  self.assertEqual(command(text),'pause',text)

 def test_saved_synthetic_commands_and_non_speech_noise(self):
  import numpy as np
  import wave
  from watcher.voice import LocalTranscriber,command
  transcribe=LocalTranscriber()
  for name,expected in [('pause','pause'),('start','start'),('task','task')]:
   with self.subTest(fixture=name),wave.open(str(ROOT/'testdata/voice'/f'{name}.wav')) as wav:
    self.assertEqual(command(transcribe(wav.readframes(wav.getnframes()))),expected)
  noise=np.random.default_rng(7).normal(0,250,96000).clip(-32768,32767).astype('<i2').tobytes()
  with self.assertRaises(ValueError):transcribe(noise)

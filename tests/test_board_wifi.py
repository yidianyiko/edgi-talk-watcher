import shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(shutil.which('powershell.exe'),'Windows PowerShell required')
class WifiConfigTests(unittest.TestCase):
 def run_config(self,text):
  with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as folder:
   p=Path(folder)/'wifi.env';p.write_text(text)
   win=lambda f:subprocess.check_output(['wslpath','-w',str(f)],text=True).strip()
   return subprocess.run(['powershell.exe','-NoProfile','-File',win(ROOT/'tools/connect_board_wifi.ps1'),'-ConfigPath',win(p),'-ValidateOnly'],capture_output=True,text=True)
 def test_password_never_echoed_and_spaces_supported(self):
  r=self.run_config('WIFI_SSID="test network"\nWIFI_PASSWORD="dummy secret 123"\n')
  self.assertEqual(r.returncode,0,r.stderr);self.assertIn('configuration valid',r.stdout);self.assertNotIn('dummy secret',r.stdout+r.stderr)
 def test_oversized_or_unsafe_command_fails_without_secret(self):
  password='secretvalue'+('x'*60)
  r=self.run_config('WIFI_SSID=test\nWIFI_PASSWORD='+password+'\n')
  self.assertNotEqual(r.returncode,0);self.assertNotIn(password,r.stdout+r.stderr)
 def test_missing_credentials_fail_before_serial(self):
  r=self.run_config('JEV_TOKEN=unrelated_dummy\n')
  self.assertNotEqual(r.returncode,0);self.assertNotIn('unrelated_dummy',r.stdout+r.stderr)

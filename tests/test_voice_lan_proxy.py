import http.client
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class ProxyTests(unittest.TestCase):
 def test_only_authenticated_bounded_voice_upload_is_forwarded(self):
  from tools.voice_lan_proxy import VoiceProxyServer
  seen=[]
  class Backend(BaseHTTPRequestHandler):
   def do_POST(self):
    seen.append((self.path,self.headers.get('X-Voice-Request'),self.rfile.read(int(self.headers['Content-Length']))))
    self.send_response(200);self.send_header('Content-Length','9');self.end_headers();self.wfile.write(b'ok pause\n')
   def log_message(self,*args):pass
  backend=ThreadingHTTPServer(('127.0.0.1',0),Backend)
  proxy=VoiceProxyServer(('127.0.0.1',0),upstream=f'http://127.0.0.1:{backend.server_port}',token='private-test-token')
  for server in (backend,proxy):threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   def request(method,path,body=None,headers=None):
    c=http.client.HTTPConnection('127.0.0.1',proxy.server_port,timeout=3)
    c.request(method,path,body=body,headers=headers or {});r=c.getresponse();data=r.read();c.close();return r.status,data
   self.assertEqual(request('GET','/')[0],403)
   self.assertEqual(request('POST','/api/board/voice',b'x')[0],403)
   headers={'Authorization':'Bearer private-test-token','Content-Type':'application/octet-stream','X-Voice-Request':'sample_1'}
   self.assertEqual(request('POST','/api/board/voice',b'\x01\x00'*8000,headers),(200,b'ok pause\n'))
   self.assertEqual(seen,[('/api/board/voice','sample_1',b'\x01\x00'*8000)])
   self.assertEqual(request('POST','/api/board/observe',b'x',headers)[0],413)
   self.assertEqual(request('POST','/api/board/voice',None,{**headers,'Content-Length':'256001'})[0],413)
   self.assertEqual(len(seen),1)
  finally:
   for server in (proxy,backend):server.shutdown();server.server_close()

 def test_proxy_rejects_nonlocal_backend_configuration(self):
  from tools.voice_lan_proxy import VoiceProxyServer
  with self.assertRaises(ValueError):VoiceProxyServer(('127.0.0.1',0),upstream='http://example.com',token='secret')

class StartupLeaseTests(unittest.TestCase):
 def test_slow_provisioning_does_not_expire_proxy_before_first_heartbeat(self):
  import json,os,socket,subprocess,sys,tempfile,time
  from pathlib import Path
  from tools import voice_lan_proxy
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);alive=root/'alive';alive.touch();os.utime(alive,(time.time()-30,time.time()-30))
   token=root/'token';token.write_text('private-voice-test-token')
   with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
   config=dict(bind='127.0.0.1',port=port,upstream='http://127.0.0.1:1',token_file=str(token),alive_file=str(alive),stop_file=str(root/'stop'),ready_file=str(root/'ready'))
   path=root/'config.json';path.write_text(json.dumps(config))
   process=subprocess.Popen([sys.executable,voice_lan_proxy.__file__,'--config',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   try:
    for _ in range(100):
     if (root/'ready').exists():break
     time.sleep(.02)
    self.assertTrue((root/'ready').exists())
    time.sleep(.8)
    self.assertIsNone(process.poll(),'Proxy expired before parent could publish its first post-start heartbeat')
    # With no parent heartbeat it must still stop within the lease.
    self.assertEqual(process.wait(timeout=5),0)
   finally:
    if process.poll() is None:process.terminate();process.wait(timeout=3)

class CameraProxyTests(unittest.TestCase):
 def test_camera_frame_and_exact_transport_headers_share_authenticated_relay(self):
  from tools.voice_lan_proxy import VoiceProxyServer
  seen=[]
  class Backend(BaseHTTPRequestHandler):
   def do_POST(self):
    seen.append((self.path,{k:self.headers.get(k) for k in ('X-Watch-Task','X-Watch-Time','X-Watch-Session','X-Watch-Reset','X-Watch-Width','X-Watch-Height')},self.rfile.read(int(self.headers['Content-Length']))))
    self.send_response(200);self.send_header('Content-Length','11');self.end_headers();self.wfile.write(b'watching 0\n')
   def log_message(self,*args):pass
  backend=ThreadingHTTPServer(('127.0.0.1',0),Backend)
  proxy=VoiceProxyServer(('127.0.0.1',0),upstream=f'http://127.0.0.1:{backend.server_port}',token='test-camera-token')
  for server in (backend,proxy):threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   headers={'Authorization':'Bearer test-camera-token','Content-Type':'application/octet-stream','X-Watch-Task':'1','X-Watch-Time':'1000','X-Watch-Session':'seed_1','X-Watch-Reset':'1','X-Watch-Width':'320','X-Watch-Height':'240'}
   frame=b'\x80'*153600
   def send(headers,body=frame,path='/api/board/observe'):
    c=http.client.HTTPConnection('127.0.0.1',proxy.server_port,timeout=3);c.request('POST',path,body,headers)
    response=c.getresponse();result=(response.status,response.read());c.close();return result
   self.assertEqual(send(headers),(200,b'watching 0\n'))
   self.assertEqual(seen[0],('/api/board/observe',{k:headers[k] for k in headers if k.startswith('X-Watch-')},frame))
   # Send rejected headers without streaming an unread body: an early close
   # while the peer is uploading may legitimately reset TCP on Windows/Linux.
   self.assertEqual(send({**headers,'Authorization':'Bearer wrong','Content-Length':'153600'},None)[0],403)
   self.assertEqual(send(headers,frame[:-1])[0],413)
   self.assertEqual(send({**headers,'X-Watch-Session':'../bad','Content-Length':'153600'},None)[0],400)
   self.assertEqual(send({**headers,'Content-Length':'153600'},None,path='/api/tasks')[0],403)
   self.assertEqual(len(seen),1)
  finally:
   for server in (proxy,backend):server.shutdown();server.server_close()

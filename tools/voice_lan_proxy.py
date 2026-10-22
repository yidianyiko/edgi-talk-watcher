"""Windows LAN endpoint for authenticated board microphone and camera uploads.

No transcript, audio, token, HTTP path or response body is logged. The parent
heartbeat bounds this child service if the product runtime exits unexpectedly.
"""
import argparse
import http.server
import json
from pathlib import Path
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

MAX_PCM = 16000 * 2 * 8


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class VoiceProxyServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, *, upstream, token):
        parsed = urllib.parse.urlsplit(upstream)
        if (parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1', '::1')
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.username):
            raise ValueError('Voice upstream must be local HTTP')
        if not token or len(token) > 128 or not token.isascii() or any(c.isspace() for c in token):
            raise ValueError('Invalid voice gateway token')
        self.upstream, self.token = upstream.rstrip('/'), token
        self.busy = threading.BoundedSemaphore(2)
        super().__init__(address, VoiceProxyHandler)


class VoiceProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, body=b'Voice request rejected\n'):
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_GET(self):
        self.reply(403)

    def do_POST(self):
        expected = ('Bearer ' + self.server.token).encode()
        if self.path not in ('/api/board/voice', '/api/board/observe') or not secrets.compare_digest(
                self.headers.get('Authorization', '').encode(), expected):
            return self.reply(403)
        length = self.headers.get('Content-Length', '')
        if not re.fullmatch(r'[0-9]{1,8}', length) or self.headers.get('Transfer-Encoding'):
            return self.reply(400)
        camera = self.path == '/api/board/observe'
        if (camera and int(length) != 153600) or (not camera and (
                not 16000 <= int(length) <= MAX_PCM or int(length) % 2)):
            return self.reply(413)
        if self.headers.get('Content-Type') != 'application/octet-stream':
            return self.reply(415)
        forwarded = {}
        if camera:
            patterns = {'X-Watch-Task':r'[1-9][0-9]{0,7}', 'X-Watch-Time':r'[0-9]{1,16}',
                        'X-Watch-Session':r'[A-Za-z0-9_-]{1,64}', 'X-Watch-Reset':r'[01]',
                        'X-Watch-Width':r'320', 'X-Watch-Height':r'240'}
            for name, pattern in patterns.items():
                value = self.headers.get(name, '')
                if not re.fullmatch(pattern, value):
                    return self.reply(400)
                forwarded[name] = value
        else:
            identity = self.headers.get('X-Voice-Request', '')
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', identity):
                return self.reply(400)
            forwarded['X-Voice-Request'] = identity
        if not self.server.busy.acquire(blocking=False):
            return self.reply(429)
        try:
            self.connection.settimeout(12)
            body = self.rfile.read(int(length))
            if len(body) != int(length):
                return self.reply(400)
            req = urllib.request.Request(self.server.upstream + self.path, data=body, headers={
                'Authorization': 'Bearer ' + self.server.token,
                'Content-Type': 'application/octet-stream', **forwarded})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            try:
                with opener.open(req, timeout=30 if camera else 115) as response:
                    result = response.read(2049)
                    if len(result) > 2048:
                        return self.reply(502)
                    self.reply(response.status, result)
            except urllib.error.HTTPError as exc:
                # Error details stay on the local product service.
                self.reply(exc.code)
            except (OSError, ValueError):
                self.reply(502)
        except (OSError, ValueError):
            try:
                self.reply(408)
            except OSError:
                pass
        finally:
            self.server.busy.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    server = VoiceProxyServer((config['bind'], config['port']), upstream=config['upstream'],
                              token=Path(config['token_file']).read_text().strip())
    alive, stop = Path(config['alive_file']), Path(config['stop_file'])
    ready = Path(config['ready_file'])
    done = threading.Event()
    started = time.time()
    def monitor():
        while not done.wait(.5):
            try:
                fresh = time.time() - max(started, alive.stat().st_mtime) < 4
            except OSError:
                fresh = False
            if stop.exists() or not fresh:
                server.shutdown()
                return
    threading.Thread(target=monitor, daemon=True).start()
    ready.write_text(json.dumps({'ready': True, 'port': server.server_port}))
    print('VOICE LAN READY', flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    finally:
        done.set()
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

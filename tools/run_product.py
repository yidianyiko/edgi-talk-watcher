"""Run the local watcher product; optionally attach the real leased Edgi Talk display."""
import argparse
import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import threading
import ipaddress

from werkzeug.serving import make_server
from watcher.app import ROOT, create_app
from watcher.board_link import FileBoardLink


def windows_path(path):
    return subprocess.check_output(['wslpath', '-w', str(Path(path).resolve())], text=True).strip()


def configure_gateway(app, directory):
    directory.mkdir(parents=True, exist_ok=True)
    path=directory/'board-gateway-token'
    try:
        with open(path,'x', opener=lambda name, flags: os.open(name,flags,0o600)) as stream:
            stream.write(secrets.token_urlsafe(32))
    except FileExistsError:
        pass
    path.chmod(0o600)
    token=path.read_text().strip()
    if len(token)<32 or not token.isascii() or any(c.isspace() for c in token):
        raise RuntimeError('Invalid board gateway token file')
    app.config['BOARD_GATEWAY_TOKEN']=token
    app.config['BOARD_GATEWAY_LAN_ONLY']=True
    return path


def wait_board_ready(process, ready_file, *, timeout=20, clock=time.monotonic, wait=time.sleep):
    deadline = clock()+timeout
    while True:
        if process.poll() is not None:
            raise RuntimeError('Board bridge failed before readiness; see board.log')
        try:
            if json.loads(ready_file.read_text()).get('ready') is True:
                return
        except (OSError, ValueError, AttributeError):
            pass
        if clock() >= deadline:
            raise RuntimeError('Board did not become ready; see board.log')
        wait(.1)


def monitor_board(process, server, stop):
    while not stop.wait(.5):
        if process.poll() is not None:
            print('Board bridge stopped; product runtime shutting down. See board.log', flush=True)
            server.shutdown()
            return


def voice_host_address(explicit=None):
    if explicit:
        address = ipaddress.ip_address(explicit)
        if address.version != 4 or address.is_loopback or address.is_unspecified:
            raise ValueError('Voice host requires the Windows LAN IPv4 address')
        return str(address)
    result = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command',
        'Get-NetIPConfiguration | Where-Object { $_.NetAdapter.HardwareInterface -and '
        '$_.NetAdapter.Status -eq "Up" -and $_.IPv4Address } | ForEach-Object {$_.IPv4Address.IPAddress}'], text=True)
    addresses = [str(ipaddress.ip_address(line.strip())) for line in result.splitlines()
                 if line.strip() and not line.strip().startswith('169.254.')]
    if len(addresses) != 1:
        raise RuntimeError('Could not select one Windows LAN address; provide --voice-host')
    return addresses[0]


def prepare_voice_proxy(app, directory, port, host, upstream_port):
    """A Windows child handles LAN reachability without exposing the product UI."""
    token_path = configure_gateway(app, directory)
    run = directory / ('voice-runtime-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run.mkdir(parents=True)
    alive = run / 'parent-alive'
    alive.touch()
    config = dict(bind='0.0.0.0', host=host, port=port,
        upstream=f'http://127.0.0.1:{upstream_port}', token_file=windows_path(token_path),
        alive_file=windows_path(alive), stop_file=windows_path(run/'stop'),
        ready_file=windows_path(run/'ready.json'))
    path = run / 'proxy.json'
    path.write_text(json.dumps(config))
    subprocess.run(['powershell.exe', '-NoProfile', '-File', windows_path(ROOT/'tools/connect_board_wifi.ps1')], check=True)
    subprocess.run(['powershell.exe', '-NoProfile', '-File', windows_path(ROOT/'tools/configure_board_voice.ps1'),
                    '-ConfigPath', windows_path(path)], check=True)
    log = (run/'proxy.log').open('w')
    alive.touch()  # Wi-Fi provisioning can take longer than the child lease.
    try:
        process = subprocess.Popen(['/mnt/c/Users/YDYK/AppData/Local/Python/pythoncore-3.12-64/python.exe',
            windows_path(ROOT/'tools/voice_lan_proxy.py'), '--config', windows_path(path)],
            stdout=log, stderr=subprocess.STDOUT)
        wait_board_ready(process, run/'ready.json', timeout=12)
    except BaseException:
        (run/'stop').touch()
        log.close()
        raise
    return process, run, log


def dispatch_board_control(app, camera, control):
    action = control.get('action')
    if action == 'start':
        camera('start')
        return True
    if action in ('pause', 'next'):
        with app.test_client() as client:
            client.post('/api/control', json={'action':'pause'},
                        headers={'X-Watcher-Token':app.config['WATCHER_TOKEN']})
        camera('pause')
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data-dir', type=Path, default=ROOT/'var/watcher')
    parser.add_argument('--board', action='store_true', help='Connect the actual KitProg3 serial bridge')
    parser.add_argument('--gateway', action='store_true', help='Expose the authenticated board gateway on the local network')
    parser.add_argument('--voice', action='store_true', help='Board microphone commands, local ASR and managed camera; implies --board')
    parser.add_argument('--camera-source', choices=('board','pc'), default='board', help='Voice-controlled camera source (default: board USB camera)')
    parser.add_argument('--voice-port', type=int, default=8766, help='Windows LAN microphone upload port')
    parser.add_argument('--voice-host', help='Windows LAN IPv4 address; normally detected automatically')
    parser.add_argument('--voice-recording', type=Path, help='Explicit regression mode: reuse archived camera frames after voice start')
    parser.add_argument('--seconds', type=int, default=86400, help='Bounded service lifetime, 10..604800 seconds')
    args = parser.parse_args()
    if args.voice:
        args.board = True
    if args.board and args.gateway:
        parser.error('--board serial display and --gateway standalone capture use different board ownership modes; select one')
    if not 1 <= args.port <= 65535 or not 10 <= args.seconds <= 604800 or not 1 <= args.voice_port <= 65535 or (args.voice and args.port == args.voice_port):
        parser.error('Invalid port or lifetime')
    link = board = log = server = None
    timer = None
    monitor_stop = threading.Event()
    monitor = None
    voice_process = voice_run = voice_log = camera = None
    voice_heartbeat = None
    failed = False
    try:
        def publish_board(value):
            if link:
                link.publish(value)
        app = create_app(data_dir=args.data_dir, status_sink=publish_board)
        if args.voice:
            from tools.voice_capture import CameraSupervisor, capture_runner
            # Fail before configuring board/network if local speech dependencies/model are absent.
            from faster_whisper import WhisperModel
            model = Path(os.environ.get('WATCHER_ASR_MODEL', ROOT/'var/models/whisper-base'))
            if not (model/'model.bin').is_file():
                raise RuntimeError('Local ASR model absent; see docs/board-voice.md')
            voice_host = voice_host_address(args.voice_host)
            voice_process, voice_run, voice_log = prepare_voice_proxy(app, args.data_dir.resolve(), args.voice_port,
                voice_host, args.port)
            def keep_voice_alive():
                while not monitor_stop.wait(.5):
                    (voice_run/'parent-alive').touch()
            voice_heartbeat = threading.Thread(target=keep_voice_alive, daemon=True)
            voice_heartbeat.start()
            if args.camera_source == 'pc' or args.voice_recording:
                camera = CameraSupervisor(capture_runner(f'http://127.0.0.1:{args.port}', ROOT/'artifacts/voice-camera',
                    recording=args.voice_recording), ticket=app.config['VOICE_GENERATION'], track_ready=True)
        if args.board:
            run = ROOT/'artifacts/product-runtime'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            link = FileBoardLink(run)
            link.start()
            log = (run/'board.log').open('w')
            board = subprocess.Popen(['powershell.exe', '-NoProfile', '-File', windows_path(ROOT/'tools/board_status.ps1'),
                '-StateFile', windows_path(link.state_file), '-AliveFile', windows_path(link.alive_file),
                '-ControlFile', windows_path(link.control_file), '-StreamSeconds', str(args.seconds),
                '-LogPath', windows_path(run/'serial.txt')], stdout=log, stderr=subprocess.STDOUT)
            wait_board_ready(board, run/'board-ready.json')
        if args.voice:
            if camera is None:
                from tools.board_capture import board_capture_runner
                app.config['BOARD_CAMERA_MANAGED'] = True
                app.config['BOARD_RECORDING_ROOT'] = ROOT/'artifacts/board-recordings'
                camera = CameraSupervisor(board_capture_runner(app,link,voice_host,args.voice_port,
                    args.data_dir.resolve()/'board-gateway-token',ROOT/'artifacts/board-camera-sessions'),
                    ticket=app.config['VOICE_GENERATION'],track_ready=True)
            app.config['VOICE_CAPTURE'] = camera
        if args.gateway:
            token_path=configure_gateway(app,args.data_dir)
            print(f'Board gateway token file: {token_path} (private; configure board without logging its value)',flush=True)
        if link:
            if args.voice and args.camera_source == 'board' and not args.voice_recording:
                pending_control = [{}]
                control_lock = threading.Lock()
                def get_pending_control():
                    with control_lock:
                        value, pending_control[0] = pending_control[0], {}
                        return value
                app.config['BOARD_CONTROL_SOURCE'] = get_pending_control
                def hardware_controls():
                    while not monitor_stop.wait(.3):
                        control = link.control()
                        if control and not dispatch_board_control(app,camera,control):
                            with control_lock:
                                pending_control[0] = control
                threading.Thread(target=hardware_controls,daemon=True).start()
            else:
                app.config['BOARD_CONTROL_SOURCE'] = link.control
            store = app.config['WATCHER_STORE']
            link.publish({'status':'paused', 'task':store.active_task(), 'event_count':len(store.events())})
        bind='0.0.0.0' if args.gateway else '127.0.0.1'
        server = make_server(bind, args.port, app, threaded=True)
        if board:
            monitor = threading.Thread(target=monitor_board, args=(board,server,monitor_stop), daemon=True)
            monitor.start()
        if voice_process:
            threading.Thread(target=monitor_board, args=(voice_process,server,monitor_stop), daemon=True).start()
        timer = threading.Timer(args.seconds, server.shutdown)
        timer.daemon = True
        timer.start()
        print(f'Watcher http://127.0.0.1:{args.port}/ lifetime={args.seconds}s board={bool(link)}', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except (RuntimeError, OSError, ValueError, ImportError, subprocess.SubprocessError) as exc:
        print(str(exc), flush=True)
        failed = True
    finally:
        if camera:
            camera.close()
        monitor_stop.set()
        if monitor:
            monitor.join(timeout=2)
        if timer:
            timer.cancel()
        if server:
            server.server_close()
        if link:
            link.close()
        if voice_run:
            (voice_run/'stop').touch()
        if voice_heartbeat:
            voice_heartbeat.join(timeout=2)
        if voice_process:
            try:
                voice_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                voice_process.terminate()
                voice_process.wait(timeout=5)
        if voice_log:
            voice_log.close()
        if board:
            try:
                board.wait(timeout=15)
            except subprocess.TimeoutExpired:
                board.terminate()
                board.wait(timeout=5)
        if log:
            log.close()
    return 0 if not failed and (board is None or board.returncode == 0) else 1


if __name__ == '__main__':
    raise SystemExit(main())

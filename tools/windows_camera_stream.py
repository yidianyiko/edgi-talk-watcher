"""Windows-only named physical camera worker. No third-party Python packages."""
import argparse
import json
from pathlib import Path
import subprocess
import threading
import time


def stop_camera(proc):
    try:
        proc.stdin.write(b'q\n')
        proc.stdin.flush()
    except (OSError,ValueError): pass
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value), encoding='utf-8')
    temporary.replace(path)


def camera_chunks(stream, stopping):
    # FFmpeg must be able to flush stdout after q, even after publication stops.
    while True:
        chunk = stream.read(4096)
        if not chunk:
            return
        if not stopping():
            yield chunk


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ffmpeg', required=True)
    parser.add_argument('--seconds', type=int, required=True)
    args = parser.parse_args()
    root = args.output
    frames = root/'frames'
    frames.mkdir()
    # Verify the actual installed FFmpeg supports the pipeline options.
    info = subprocess.run([args.ffmpeg,'-hide_banner','-h','full'],capture_output=True,text=True,timeout=10)
    assert '-rtbufsize' in info.stdout
    muxer = subprocess.run([args.ffmpeg,'-hide_banner','-h','muxer=image2pipe'],capture_output=True,text=True,timeout=10)
    assert 'image2pipe' in muxer.stdout
    log = (root/'camera-ffmpeg.log').open('wb')
    command = [args.ffmpeg,'-hide_banner','-f','dshow','-rtbufsize','64M',
               '-i','video=USB 2.0 Camera','-an','-vf','fps=1','-c:v','mjpeg','-q:v','2','-f','image2pipe','pipe:1']
    proc = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
    shutdown = threading.Event()
    def watchdog():
        deadline = time.monotonic()+args.seconds
        while not shutdown.wait(.1):
            if (root/'camera.stop').exists() or time.monotonic() >= deadline:
                stop_camera(proc)
                return
    watchdog_thread = threading.Thread(target=watchdog,daemon=True)
    watchdog_thread.start()
    count, pending, last_alert = 0, bytearray(), ''
    error = None
    try:
        for chunk in camera_chunks(proc.stdout, lambda: (root/'camera.stop').exists()):
            pending.extend(chunk)
            while True:
                start = pending.find(b'\xff\xd8')
                end = pending.find(b'\xff\xd9',max(0,start)+2)
                if start < 0 or end < 0: break
                image = bytes(pending[start:end+2])
                del pending[:end+2]
                count += 1
                path = frames/f'{count:06d}.jpg'
                path.write_bytes(image)
                # Immutable metadata avoids replacing a Windows/WSL file held by a reader.
                atomic_json(path.with_suffix('.json'), {'path': 'frames/'+path.name, 'time': time.time(), 'frame':count})
                signal = root/'alert.signal'
                if signal.exists():
                    event = signal.read_text()
                    if event != last_alert:
                        try:
                            import winsound
                            winsound.MessageBeep()
                            print('ALERT '+event,flush=True)
                        except RuntimeError:
                            print('ALERT_SOUND_FAILED '+event,flush=True)
                        last_alert = event
            if len(pending) > 8*1024*1024: raise ValueError('Camera JPEG exceeds buffer limit')
    except Exception as exc:
        error = type(exc).__name__
        import traceback
        traceback.print_exc()
    finally:
        shutdown.set()
        stop_camera(proc)
        watchdog_thread.join(timeout=7)
        proc.communicate(timeout=5)
        log.close()
        atomic_json(root/'camera-cleanup.json',{'frames':count,'ffmpeg_exit':proc.returncode,
                    'released':proc.poll() is not None,'error_type':error})
    return 0 if not error and proc.returncode==0 and count else 1


if __name__ == '__main__':
    raise SystemExit(main())

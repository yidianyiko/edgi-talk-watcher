"""Bounded sequential physical-camera / Jev / Edgi Talk test (Windows + WSL)."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import time
import threading

from research.jev_probe import build_request, read_decision
from watcher.app import ROOT, MODEL, call_jev, load_key
from tools.judge_to_board import display_status
from watcher.task_plan import load_plan, compile_task_cached
from watcher.engine import WatchEngine


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def run_session(task, duration, interval, max_calls, capture, judge, publish, output,
                *, clock=time.monotonic, wait=time.sleep, alert=lambda event: None):
    started = clock()
    deadline = started + duration
    report = {'task': task, 'duration_seconds': duration, 'interval_seconds': interval,
              'decision_attempts': 0, 'decisions': 0, 'events': 0, 'counts': {}, 'stop_reason': 'duration'}
    # The public helper retains the original injected judge(task, before, after)
    # seam. Production CLI supplies its validated plan explicitly.
    plan = task if isinstance(task, dict) else {
        'supported': True, 'target': 'visual target', 'transition': 'appears',
        'instruction': task, 'reason': ''}
    engine = WatchEngine(plan, deadline=deadline, max_calls=max_calls, clock=clock)
    try:
        publish('idle')
        engine.observe(capture(), None)
        while clock() < deadline:
            wait(min(interval, max(0, deadline-clock())))
            if clock() >= deadline: break
            if engine.calls >= max_calls:
                report['stop_reason'] = 'call_limit'
                break
            current = capture()
            if clock() >= deadline: break
            decision_started = clock()
            publish('idle')
            try:
                result = engine.observe(current, lambda plan, before, after: judge(task, before, after))
            finally:
                report['decision_attempts'] = engine.calls
            if result['discarded']:
                report['discarded_late_results'] = report.get('discarded_late_results', 0) + 1
                break
            decision = {k:v for k,v in result.items() if k not in
                        ('alert','before','after','discarded','generation')}
            status = decision['status']
            record = {'round': engine.calls, 'elapsed_seconds': round(clock()-started, 3),
                      'latency_seconds': round(clock()-decision_started, 3), 'decision': decision,
                      'before': str(result['before']['path']), 'after': str(current['path'])}
            with (output / 'rounds.jsonl').open('a') as log:
                log.write(json.dumps(record, ensure_ascii=False)+'\n')
            report['decisions'] += 1
            report['counts'][status] = report['counts'].get(status, 0) + 1
            publish(display_status(status))
            if result['alert']:
                alert(record)
                report['events'] += 1
            print(f"round={record['round']} status={status} elapsed={record['elapsed_seconds']}s", flush=True)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        if isinstance(exc, TimeoutError) and clock() >= deadline:
            report['stop_reason'] = 'duration'
            report['deadline_timeout'] = True
        else:
            report['stop_reason'] = 'error'
            report['error_type'] = type(exc).__name__
    finally:
        try:
            publish('paused')
        except (OSError, subprocess.SubprocessError):
            report['pause_delivery_failed'] = True
        report['elapsed_seconds'] = round(clock()-started, 3)
        write_json(output / 'summary.json', report)
    return report


def windows_path(path):
    return subprocess.check_output(['wslpath', '-w', str(path.resolve())], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    task_source = parser.add_mutually_exclusive_group(required=True)
    task_source.add_argument('--task')
    task_source.add_argument('--plan', type=Path, help='Validated saved task plan; no new compilation')
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--max-calls', type=int, default=60)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 10 <= args.seconds <= 3600 or not 3 <= args.interval <= 60 or not 1 <= args.max_calls <= 60:
        parser.error('seconds 10..3600, interval 3..60, max-calls 1..60')
    plan = load_plan(args.plan) if args.plan else compile_task_cached(args.task)
    if plan:
        args.task = plan['instruction']
    if not args.task.strip() or len(args.task) > 2000:
        parser.error('task must contain 1..2000 characters')
    if not load_key(): parser.error('Missing model key; no model calls made')
    output = (args.output or ROOT / 'artifacts/continuous' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')).resolve()
    output.mkdir(parents=True, exist_ok=False)
    if plan:
        write_json(output/'task-plan.json', plan)
    state = output / 'board-state.json'
    write_json(state, {'status': 'idle'})
    board_log = (output / 'board-host.log').open('w')
    camera_log = (output / 'camera-host.log').open('w')
    board = camera = None
    report = None
    alive = output/'controller-alive'
    heartbeat_stop = threading.Event()
    lease_deadline = [time.monotonic()+40]
    def heartbeat():
        while not heartbeat_stop.is_set() and time.monotonic() < lease_deadline[0]:
            alive.touch()
            heartbeat_stop.wait(.5)
    heartbeat_thread = threading.Thread(target=heartbeat,daemon=True)
    heartbeat_thread.start()
    try:
        board = subprocess.Popen(['powershell.exe','-NoProfile','-File',windows_path(ROOT/'tools/board_status.ps1'),
            '-StateFile',windows_path(state),'-StreamSeconds',str(args.seconds+30),
            '-AliveFile',windows_path(alive),
            '-LogPath',windows_path(output/'serial.txt')],stdout=board_log,stderr=subprocess.STDOUT)
        ready_deadline = time.monotonic()+20
        while not (output/'board-ready.json').exists():
            if board.poll() is not None or time.monotonic() > ready_deadline:
                raise RuntimeError('Board did not become ready; no model calls made')
            time.sleep(.1)
        python_windows = '/mnt/c/Users/YDYK/AppData/Local/Python/pythoncore-3.12-64/python.exe'
        ffmpeg = (ROOT/'artifacts/physical-camera/ffmpeg-path.txt').read_text().strip()
        camera = subprocess.Popen([python_windows,windows_path(ROOT/'tools/windows_camera_stream.py'),
            '--output',windows_path(output),'--ffmpeg',ffmpeg,'--seconds',str(args.seconds+20)],
            stdout=camera_log,stderr=subprocess.STDOUT)
        ready_deadline = time.monotonic()+15
        while not list((output/'frames').glob('*.json')):
            if camera.poll() is not None or time.monotonic() > ready_deadline:
                raise RuntimeError('Physical camera did not produce a frame')
            time.sleep(.1)
        def publish(status):
            if board.poll() is not None: raise OSError('Board bridge stopped')
            write_json(state, {'status': status})
        def capture():
            if camera.poll() is not None: raise OSError('Physical camera stopped')
            metadata = max((output/'frames').glob('*.json'))
            frame = json.loads(metadata.read_text())
            if time.time()-frame['time'] > 4: raise OSError('Physical camera frame stale')
            frame['path'] = output / frame['path']
            return frame
        def judge(task, before, after):
            payload = build_request({'task': task['instruction'] if isinstance(task, dict) else task, 'frames': [
                {'path': str(before['path']), 'seconds_ago': after['time']-before['time']},
                {'path': str(after['path']), 'seconds_ago': 0}]}, output, MODEL)
            remaining = session_deadline-time.monotonic()
            if remaining <= 0: raise TimeoutError('Session deadline during payload preparation')
            return read_decision(call_jev(payload, timeout=min(20,remaining)))
        def alert(record):
            event = output / 'events' / str(record['round'])
            event.mkdir(parents=True)
            shutil.copyfile(record['before'],event/'before.jpg')
            shutil.copyfile(record['after'],event/'after.jpg')
            write_json(event/'decision.json',record)
            (output/'alert.signal').write_text(str(record['round']))
            print('EVENT evidence='+str(event),flush=True)
        write_json(output/'run.json', {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'source': 'physical Windows USB 2.0 Camera', 'model': MODEL, 'duration_seconds': args.seconds,
            'max_calls': args.max_calls, 'task': args.task})
        session_deadline = time.monotonic()+args.seconds
        lease_deadline[0] = session_deadline+25
        report = run_session(plan,args.seconds,args.interval,args.max_calls,capture,judge,publish,output,alert=alert)
    finally:
        write_json(state,{'status':'paused'})
        (output/'camera.stop').touch()
        (output/'board-state.json.stop').touch()
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=2)
        cleanup = {}
        for name, proc in [('camera',camera),('board',board)]:
            if proc is not None:
                try: proc.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    proc.wait(timeout=5)
                    cleanup[name+'_forced_stop'] = True
                cleanup[name+'_exit'] = proc.returncode
        write_json(output/'cleanup.json',cleanup)
        board_log.close()
        camera_log.close()
    print('Report: '+str(output/'summary.json'),flush=True)
    return 0 if report and report['stop_reason']=='duration' and all(v==0 for k,v in cleanup.items() if k.endswith('_exit')) else 1


if __name__ == '__main__':
    raise SystemExit(main())

"""One real Jev decision from a saved frame pair, displayed on the actual board."""
import argparse
import json
from pathlib import Path
import subprocess
import time

from research.jev_probe import build_request, read_decision, validate_cases
from watcher.app import call_jev, MODEL, ROOT


def display_status(choice):
    try:
        return {'event': 'event', 'no_event': 'watching', 'uncertain': 'uncertain'}[choice]
    except (KeyError, TypeError) as exc:
        raise ValueError('No valid model decision') from exc


def send_status(status, seconds):
    script = subprocess.check_output(
        ['wslpath', '-w', str(ROOT / 'tools/board_status.ps1')], text=True).strip()
    subprocess.run(['powershell.exe', '-NoProfile', '-File', script,
                    '-Status', status, '-Seconds', str(seconds)],
                   check=True, timeout=seconds + 30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--hold-seconds', type=int, default=10)
    parser.add_argument('--output', type=Path, default=Path('artifacts/board-status/model-to-board.json'))
    args = parser.parse_args()
    if not 0 <= args.hold_seconds <= 3600:
        parser.error('--hold-seconds must be 0..3600')
    manifest = json.loads(args.manifest.read_text())
    cases = manifest['cases']
    validate_cases(cases)
    if len(cases) != 1:
        parser.error('Exactly one case is required for the board smoke test')
    payload = build_request(cases[0], args.manifest.parent, MODEL)
    # Check the actual board before making a model request.
    send_status('idle', 0)
    started = time.monotonic()
    try:
        decision = read_decision(call_jev(payload))
        status = display_status(decision['status'])
        report = {'mode': 'live', 'decision_attempts': 1, 'case': cases[0]['id'],
                  'decision': decision, 'screen_status': status,
                  'latency_seconds': round(time.monotonic() - started, 3)}
    except (ValueError, TypeError, OSError, KeyError):
        report = {'mode': 'live', 'decision_attempts': 1, 'screen_status': 'paused',
                  'error': 'Model request failed or returned an invalid decision'}
    try:
        send_status(report['screen_status'], args.hold_seconds)
        report['board_acknowledged'] = True
    except (subprocess.SubprocessError, OSError):
        report['board_acknowledged'] = False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['board_acknowledged'] and 'error' not in report else 1


if __name__ == '__main__':
    raise SystemExit(main())

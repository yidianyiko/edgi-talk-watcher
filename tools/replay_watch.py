"""Replay saved real frames. Offline by default; never opens camera or serial port."""
import argparse
import json
from pathlib import Path

from research.jev_probe import build_request, read_decision, validate_cases
from watcher.app import MODEL, call_jev
from watcher.task_plan import load_plan


def summarize(items):
    evaluated = [x for x in items if x['status'] not in ('not_evaluated', 'error')]
    return {'exact_matches': sum(x['status'] == x['expected'] for x in evaluated),
            'false_alerts': sum(x['status'] == 'event' and x['expected'] != 'event' for x in evaluated),
            'missed_events': sum(x['status'] != 'event' and x['expected'] == 'event' for x in evaluated),
            'evaluated': len(evaluated)}


def evaluate_cases(cases, root, plan, judge=None):
    # Validate every image before the first potentially billable call.
    payloads = [build_request({**case, 'task': plan['instruction']}, root, MODEL) for case in cases]
    report = {'mode': 'live_model_recorded_frames' if judge else 'offline_validation',
              'model': MODEL, 'plan': plan, 'model_calls': 0, 'cases': []}
    for case, payload in zip(cases, payloads):
        item = {'id': case['id'], 'expected': case['expected'], 'frames': case['frames'],
                'status': 'not_evaluated'}
        if judge:
            report['model_calls'] += 1
            try:
                item.update(read_decision(judge(payload)))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                item.update(status='error', error_type=type(exc).__name__)
        report['cases'].append(item)
        if item['status'] == 'error':
            break  # No hidden retries, no repeated transport/auth failures.
    report.update(summarize(report['cases']))
    report['complete'] = len(report['cases']) == len(cases) and all(x['status'] != 'error' for x in report['cases'])
    report['passed'] = (report['complete'] and report['exact_matches'] == len(cases)) if judge else None
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--run', action='store_true', help='Billable Jev evaluation, max 12 calls')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists')
    manifest = json.loads(args.manifest.read_text())
    cases = manifest['cases']
    validate_cases(cases)
    plan = load_plan(args.plan)
    report = evaluate_cases(cases, args.manifest.parent, plan, judge=call_jev if args.run else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('cases', 'plan')}))
    return 0 if report['complete'] and (not args.run or report['passed']) else 1

if __name__ == '__main__':
    raise SystemExit(main())

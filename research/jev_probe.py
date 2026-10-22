"""Bounded Jev image probe. Offline validation is not model evaluation."""
import argparse
import base64
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid

LABELS = {'event', 'no_event', 'uncertain'}
ENDPOINT = 'https://api.typesafe.ai/v1/systemone'


def read_decision(response):
    try:
        answer = response['answers']['watch']
        probs = answer['probabilities']
        confidence = answer['confidence']
        choice = answer['choice']
        if answer['type'] != 'choice' or choice not in LABELS or set(probs) != LABELS:
            raise ValueError('Invalid choice fields')
        values = [confidence, *probs.values()]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
               not math.isfinite(v) or not 0 <= v <= 1 for v in values):
            raise ValueError('Invalid probability or confidence')
        if abs(sum(probs.values()) - 1) > 0.02 or probs[choice] < max(probs.values()):
            raise ValueError('Inconsistent choice probabilities')
        return {'status': choice if confidence >= 0.8 else 'uncertain',
                'raw_choice': choice, 'confidence': confidence, 'probabilities': probs,
                'model': response.get('model'),
                'input_tokens': response.get('usage', {}).get('input_tokens')}
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Missing or malformed model answer') from exc


def build_request(case, root, model):
    from PIL import Image
    if not isinstance(case.get('task'), str) or not case['task'].strip():
        raise ValueError('A task is required')
    if not case.get('frames'):
        raise ValueError('At least one frame is required')
    frames, assets = [], {}
    previous = float('inf')
    for frame in case['frames']:
        age = frame['seconds_ago']
        if isinstance(age, bool) or not isinstance(age, (int, float)) or not math.isfinite(age) or age < 0 or age > previous:
            raise ValueError('Frames must be ordered oldest first, with finite nonnegative seconds_ago')
        previous = age
        path = (root / frame['path']).resolve()
        data = path.read_bytes()
        if len(data) > 16 * 1024 * 1024:
            raise ValueError('Image exceeds 16 MiB')
        with Image.open(path) as im:
            if im.format not in ('PNG', 'JPEG') or getattr(im, 'is_animated', False):
                raise ValueError('Only still PNG/JPEG supported')
            if not all(280 <= dimension <= 1568 for dimension in im.size):
                raise ValueError('Image dimensions must each be between 280 and 1568 pixels')
            im.verify()
            fmt = 'png' if im.format == 'PNG' else 'jpg'
        ref = str(uuid.uuid4())
        assets[ref] = {'type': 'image', 'format': fmt,
                       'data_base64': base64.b64encode(data).decode('ascii')}
        frames.append({'seconds_ago': age, 'image': ref})
    payload = {'model': model, 'state': {'task': case['task'], 'frames': frames},
               'assets': assets, 'questions': {'watch': {
                   'type': 'choice',
                   'instructions': 'Evaluate the user task in state.task using the chronological frames in state.frames. Judge only visible evidence. For a change, compare earlier and later frames. Do not assume unseen facts.',
                   'criteria': {
                       'event': 'The requested event is clearly supported by the visible frames.',
                       'no_event': 'The scene is sufficiently visible and the requested event is not observed.',
                       'uncertain': 'The requested event cannot be judged because evidence is missing, obstructed, dark, or ambiguous.'}}}}
    if len(json.dumps(payload).encode()) > 32 * 1024 * 1024:
        raise ValueError('Request exceeds 32 MiB')
    return payload


def validate_cases(cases):
    if not isinstance(cases, list) or not 1 <= len(cases) <= 12:
        raise ValueError('A probe must contain 1..12 cases')
    seen = set()
    for case in cases:
        case_id = case.get('id')
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError('Case IDs must be nonempty unique strings')
        if case.get('expected') not in LABELS:
            raise ValueError('Invalid expected label')
        seen.add(case_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--run', action='store_true', help='Make billable API calls (default: offline only)')
    parser.add_argument('--key-file', type=Path, help='Private text file containing API key')
    parser.add_argument('--model', default='jev-1.14.0')
    parser.add_argument('--output', type=Path, default=Path('artifacts/jev-report.json'))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    cases = manifest['cases']
    try:
        validate_cases(cases)
    except ValueError as exc:
        parser.error(str(exc))
    payloads = [build_request(case, args.manifest.parent, args.model) for case in cases]
    key = (args.key_file.read_text().strip() if args.key_file else os.environ.get('TYPESAFE_API_KEY', '').strip())
    if args.run and not key:
        parser.error('No API key: set TYPESAFE_API_KEY or supply --key-file. No model calls made.')
    report = {'mode': 'live' if args.run else 'offline', 'model': args.model,
              'fixture_kind': manifest.get('fixture_kind', 'unspecified'), 'model_calls': 0,
              'note': 'Synthetic fixtures are smoke tests, not real-camera accuracy evidence.', 'cases': []}
    for case, payload in zip(cases, payloads):
        item = {'id': case['id'], 'expected': case['expected'], 'frames': len(payload['assets'])}
        if args.run:
            request = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(), headers={
                'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
                'TypeSafe-Danger-Zone-Images': 'true'})
            started = time.monotonic()
            report['model_calls'] += 1
            try:
                with urllib.request.urlopen(request, timeout=45) as result:
                    item.update(read_decision(json.load(result)))
                item['matches_expected'] = item['status'] == case['expected']
            except urllib.error.HTTPError as exc:
                item.update(status='error', error='HTTP ' + str(exc.code))
            except (urllib.error.URLError, TimeoutError, ValueError, OSError):
                item.update(status='error', error='Transport failure or invalid model response')
            item['latency_seconds'] = round(time.monotonic() - started, 3)
        else:
            item['status'] = 'not_evaluated'
        report['cases'].append(item)
        print(f"{item['id']}: {item['status']}", flush=True)
        if item['status'] == 'error':
            break  # No repeated billing/auth failures or automatic retries.
    report['complete'] = len(report['cases']) == len(cases) and all(x['status'] != 'error' for x in report['cases'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f"Report: {args.output}; model calls: {report['model_calls']}")
    return 0 if report['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

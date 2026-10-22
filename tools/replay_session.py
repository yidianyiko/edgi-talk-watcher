"""Replay an entire chronological archive without camera or board access.

Offline validation is default. --run makes bounded billable calls. --responses
replays the saved responses through the same engine without network access.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from watcher.engine import WatchEngine
from watcher.task_plan import FIELDS, load_plan


def load_recording(folder):
    folder = Path(folder).resolve()
    recording = json.loads((folder/'recording.json').read_text())
    frames = []
    for entry in recording['frames']:
        path = (folder/entry['path']).resolve()
        if not path.is_relative_to(folder): raise ValueError('Frame outside archive')
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Frame checksum mismatch')
        if frames and entry['time'] <= frames[-1]['time']: raise ValueError('Nonchronological recording')
        frames.append({**entry, 'path':str(path)})
    if len(frames) < 2: raise ValueError('At least two frames required')
    return frames


def sample_frames(frames, interval=10):
    if interval <= 0: raise ValueError('Positive interval required')
    chosen = [frames[0]]
    for frame in frames[1:]:
        if frame['time']-chosen[-1]['time'] >= interval:
            chosen.append(frame)
    if chosen[-1] != frames[-1]: chosen.append(frames[-1])
    return chosen


class CachedJudge:
    def __init__(self, rounds): self.rounds = iter(rounds)
    def __call__(self, plan, before, after):
        try: record = next(self.rounds)
        except StopIteration as exc: raise ValueError('Response log exhausted') from exc
        if record.get('plan') != {k:plan[k] for k in FIELDS}:
            raise ValueError('Response log task mismatch')
        if record['before'] != before or record['after'] != after:
            raise ValueError('Response log frame mismatch')
        return record['decision']


def replay_session(frames, plan, judge, *, max_calls=40, on_round=None):
    if not 1 <= max_calls <= 40: raise ValueError('Call bound must be 1..40')
    engine = WatchEngine(plan,max_calls=max_calls)
    report = {'rounds': [], 'events':0, 'counts':{}, 'stop_reason':'end',
              'complete':False, 'covered_until':frames[0]['time'],
              'recording_start':frames[0]['time'], 'recording_end':frames[-1]['time']}
    engine.observe(frames[0], judge)
    for frame in frames[1:]:
        try:
            result = engine.observe(frame,judge)
        except Exception as exc:
            report.update(stop_reason='error',error_type=type(exc).__name__)
            break
        if result['status'] == 'call_limit':
            report['stop_reason'] = 'call_limit'
            break
        decision = {k:v for k,v in result.items() if k not in ('before','after','alert','generation','discarded')}
        record = {'round':len(report['rounds'])+1, 'elapsed_seconds':frame['time']-frames[0]['time'],
                  'before':result['before'],'after':result['after'],'decision':decision,'alert':result['alert'],
                  'plan':dict(engine.plan)}
        report['rounds'].append(record)
        report['events'] += int(result['alert'])
        status = result['status']
        report['counts'][status] = report['counts'].get(status,0)+1
        report['covered_until'] = frame['time']
        if on_round: on_round(record)
    report['decision_attempts'] = engine.calls
    report['complete'] = report['stop_reason']=='end' and report['covered_until']==frames[-1]['time']
    report['covered_seconds'] = report['covered_until']-frames[0]['time']
    report['uncovered_tail_seconds'] = frames[-1]['time']-report['covered_until']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording',type=Path)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--interval',type=float,default=10)
    parser.add_argument('--max-calls',type=int,default=40)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--run',action='store_true')
    mode.add_argument('--responses',type=Path)
    args = parser.parse_args()
    if args.output.exists(): parser.error('Output already exists')
    if args.interval <= 0 or not 1 <= args.max_calls <= 40: parser.error('interval >0, max-calls 1..40')
    plan = load_plan(args.plan)
    frames = load_recording(args.recording)
    sampled = sample_frames(frames,args.interval)
    args.output.mkdir(parents=True)
    if not args.run and not args.responses:
        report = {'mode':'offline_validation','complete':None,'model_calls':0,
                  'source_frames':len(frames),'sampled_frames':len(sampled),
                  'required_calls':len(sampled)-1,'within_call_limit':len(sampled)-1<=args.max_calls,
                  'original_elapsed_seconds':frames[-1]['time']-frames[0]['time']}
    else:
        raw_log = args.output/'responses.jsonl'
        from watcher.app import MODEL, call_jev
        from research.jev_probe import build_request, read_decision
        cached = None
        if args.responses:
            cached = CachedJudge([json.loads(line) for line in args.responses.read_text().splitlines() if line.strip()])
        def judge(plan,before,after):
            if cached: return cached(plan,before,after)
            payload = build_request({'task':plan['instruction'],'frames':[
                {'path':before['path'],'seconds_ago':after['time']-before['time']},
                {'path':after['path'],'seconds_ago':0}]},args.recording,MODEL)
            response = call_jev(payload)
            decision = read_decision(response)
            with (args.output/'raw-model-responses.jsonl').open('a') as handle:
                handle.write(json.dumps({'before':before,'after':after,'response':response})+'\n')
            return decision
        def save(record):
            with raw_log.open('a') as handle: handle.write(json.dumps(record)+'\n')
            if record['alert']:
                dest = args.output/'events'/str(record['round'])
                dest.mkdir(parents=True)
                for key in ('before','after'): shutil.copyfile(record[key]['path'],dest/(key+'.jpg'))
            print(f"round={record['round']} elapsed={record['elapsed_seconds']:.3f} status={record['decision']['status']} alert={record['alert']}",flush=True)
        report = replay_session(sampled,plan,judge,max_calls=args.max_calls,on_round=save)
        report.update(mode='cached_response_replay' if cached else 'live_model_recorded_frames',
                      model_calls=0 if cached else report['decision_attempts'],source_frames=len(frames),
                      sampled_frames=len(sampled),model=MODEL,plan=plan)
    (args.output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('rounds','plan')}))
    return 1 if report.get('complete') is False else 0


if __name__ == '__main__': raise SystemExit(main())

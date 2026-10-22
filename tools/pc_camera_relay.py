"""Relay the named Windows PC camera into the running persistent watcher product.

Start tools.run_product --board first. --recording reuses archived samples without
opening a camera. Model calls occur on the existing server and are billable.
"""
import argparse
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import threading
import time
import urllib.parse
import urllib.request

from watcher.app import ROOT
from tools.continuous_watch import windows_path
from tools.replay_session import load_recording, sample_frames


class ProductClient:
    def __init__(self, url):
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='http' or parsed.hostname not in ('localhost','127.0.0.1','::1') or parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.username:
            raise ValueError('Relay requires a local HTTP product URL')
        self.url=url.rstrip('/')
        # Ignore environment proxies so local frames and page tokens remain local.
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with self.opener.open(self.url+'/',timeout=5) as response:
            html=response.read().decode()
        match=re.search(r'<meta name="watcher-token" content="([A-Za-z0-9_-]+)">',html)
        if not match:raise ValueError('Product token missing')
        self.token=match[1]

    def post(self, path, body, *, timeout=20):
        request=urllib.request.Request(self.url+path,data=json.dumps(body).encode(),headers={
            'X-Watcher-Token':self.token,'Content-Type':'application/json'})
        with self.opener.open(request,timeout=timeout) as response:return json.load(response)

    def get(self,path,*,timeout=3):
        request=urllib.request.Request(self.url+path,headers={'X-Watcher-Token':self.token})
        with self.opener.open(request,timeout=timeout) as response:return json.load(response)


def relay_frames(client, frames, *, seconds, max_calls, clock=time.monotonic,poll_controls=False,stop=None):
    deadline=clock()+seconds
    report={'observations':0,'judgments':0,'events':0,'stop_reason':'source_end'}
    session=None
    stop=stop or threading.Event()
    control_stop=threading.Event()
    monitor=None
    control_reason=[]
    def controls():
        while not control_stop.is_set():
            try:
                control=client.get('/api/board/control') or {}
                if not isinstance(control,dict):raise ValueError('Invalid board control response')
                action=control.get('action')
                if action in ('pause','next'):
                    control_reason.append('board_'+action)
                    stop.set()
                    client.post('/api/control',{'action':'pause','session_id':session},timeout=5)
                    return
            except (OSError,ValueError,TypeError):
                control_reason.append('control_error');stop.set()
                try:client.post('/api/control',{'action':'pause','session_id':session},timeout=5)
                except (OSError,ValueError):pass
                return
            control_stop.wait(.5)
    try:
        session=client.post('/api/control',{'action':'start'})['session_id']
        if poll_controls:
            monitor=threading.Thread(target=controls,daemon=True);monitor.start()
        iterator=iter(frames)
        while clock()<deadline:
            if stop.is_set():break
            if report['judgments']>=max_calls:
                report['stop_reason']='call_limit';break
            try:frame=next(iterator)
            except StopIteration:break
            if stop.is_set():break
            if clock()>=deadline:report['stop_reason']='duration';break
            image=base64.b64encode(Path(frame['path']).read_bytes()).decode()
            result=client.post('/api/observe',{'session_id':session,'frame':{
                'image':'data:image/jpeg;base64,'+image,'time':frame['time']*1000}},timeout=max(.1,min(25,deadline-clock())))
            report['observations']+=1
            if result['status']!='preparing':report['judgments']+=1
            if result.get('alert'):report['events']+=1
            print('Relay '+result['status'],flush=True)
        else:report['stop_reason']='duration'
    except (OSError,ValueError,KeyError,TypeError) as exc:
        report.update(stop_reason='error',error_type=type(exc).__name__)
    finally:
        control_stop.set()
        if monitor:monitor.join(timeout=9)
        if control_reason:
            report['stop_reason']=control_reason[0]
            report.pop('error_type',None)
        if session:
            try:client.post('/api/control',{'action':'pause','session_id':session},timeout=5)
            except (OSError,ValueError):report['pause_delivery_failed']=True
    return report


def live_frames(output, camera, deadline, interval,stop):
    previous=0
    while time.monotonic()<deadline and not stop.is_set():
        if camera.poll() is not None:raise OSError('Camera worker stopped')
        metadata=sorted((output/'frames').glob('*.json'))
        if not metadata:
            time.sleep(.1);continue
        frame=json.loads(metadata[-1].read_text())
        if time.time()-frame['time']>4:raise OSError('Camera frame stale')
        if frame['time']<=previous:
            time.sleep(.1);continue
        previous=frame['time'];frame['path']=output/frame['path']
        yield frame
        remaining=deadline-time.monotonic()
        if remaining>0:stop.wait(min(interval,remaining))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8765')
    parser.add_argument('--task',help='Compile/select a task once, otherwise use the active saved task')
    parser.add_argument('--seconds',type=int,default=300)
    parser.add_argument('--interval',type=float,default=5)
    parser.add_argument('--max-calls',type=int,default=60)
    parser.add_argument('--recording',type=Path,help='Use saved frames; no physical camera')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not 10<=args.seconds<=3600 or not 3<=args.interval<=60 or not 1<=args.max_calls<=60:parser.error('Invalid runtime, interval or call budget')
    output=(args.output or ROOT/'artifacts/pc-relay'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')).resolve()
    output.mkdir(parents=True,exist_ok=False)
    camera=log=None;report={'stop_reason':'startup_error'};cleanup={}
    try:
        client=ProductClient(args.url)
        if args.task:client.post('/api/tasks',{'task':args.task},timeout=95)
        deadline=time.monotonic()+args.seconds
        stop=threading.Event()
        if args.recording:
            frames=sample_frames(load_recording(args.recording),args.interval)
        else:
            python_windows=Path('/mnt/c/Users/YDYK/AppData/Local/Python/pythoncore-3.12-64/python.exe')
            ffmpeg=(ROOT/'artifacts/physical-camera/ffmpeg-path.txt').read_text().strip()
            log=(output/'camera-host.log').open('w')
            camera=subprocess.Popen([str(python_windows),windows_path(ROOT/'tools/windows_camera_stream.py'),
                '--output',windows_path(output),'--ffmpeg',ffmpeg,'--seconds',str(args.seconds+5)],stdout=log,stderr=subprocess.STDOUT)
            frames=live_frames(output,camera,deadline,args.interval,stop)
        report=relay_frames(client,frames,seconds=max(.1,deadline-time.monotonic()),max_calls=args.max_calls,poll_controls=True,stop=stop)
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        report['error_type']=type(exc).__name__
    finally:
        if camera:
            (output/'camera.stop').touch()
            try:camera.wait(timeout=12)
            except subprocess.TimeoutExpired:
                camera.terminate();camera.wait(timeout=5);cleanup['forced_stop']=True
            cleanup['camera_exit']=camera.returncode
        if log:log.close()
        report.update(source='recording' if args.recording else 'PC USB 2.0 Camera',cleanup=cleanup)
        (output/'summary.json').write_text(json.dumps(report,indent=2))
    print('Report: '+str(output/'summary.json'),flush=True)
    return 0 if report['stop_reason'] in ('duration','call_limit','source_end','board_pause','board_next') and cleanup.get('camera_exit',0)==0 else 1


if __name__=='__main__':raise SystemExit(main())

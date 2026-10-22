"""Isolated browser fixture: fake media and deterministic paid-model substitute only."""
import argparse
from watcher.app import create_app
from watcher.task_plan import compile_task_cached

parser=argparse.ArgumentParser();parser.add_argument('--data-dir',required=True);parser.add_argument('--port',type=int,default=18765);args=parser.parse_args()
def translate(task):
    if '预测' in task:
        return dict(supported=False,target='',transition='unsupported',instruction='',reason='不支持预测任务。')
    return dict(supported=True,target='cup',transition='disappears',instruction='Alert when cup disappears. An obstructed view is uncertain.',reason='')
def judge(payload):
    return {'answers':{'watch':{'type':'choice','choice':'event','confidence':.95,'probabilities':{'event':.95,'no_event':.03,'uncertain':.02}}}}
app=create_app(judge=judge,compiler=lambda task:compile_task_cached(task,cache_dir=args.data_dir+'/plans',translator=translate),data_dir=args.data_dir,transcriber=lambda raw:'暂停看守。')
app.config.update(BOARD_GATEWAY_TOKEN='browser-board-voice',VOICE_CAPTURE=lambda action:True)
app.run(host='127.0.0.1',port=args.port,threaded=True)

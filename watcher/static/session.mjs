// One sequential watch session. Each restart invalidates older async work.
export class WatchSession {
  constructor({capture,judge,observe,onState,onEvent,schedule=(fn,ms)=>setTimeout(fn,ms),cancel=id=>clearTimeout(id)}) {
    Object.assign(this,{capture,judge,observe,onState,onEvent,schedule,cancel});
    this.running=false; this.generation=0; this.busy=false;
  }
  pause(state='paused',detail='已暂停，不再发送新的画面。') {
    this.running=false; this.generation++;
    this.cancel(this.timer); this.controller?.abort();
    this.onState(state,detail);
  }
  async start(task,interval) {
    if(this.busy || this.running) return;
    this.running=true; this.task=task; this.interval=interval; this.latched=false;
    const gen=++this.generation;
    this.onState('preparing','正在采集第一帧，等待下一帧后开始判断。');
    this.busy=true;
    try {
      const frame=await this.capture();
      if(gen!==this.generation) return;
      if(this.observe) await this.observe(frame,new AbortController().signal);
      if(gen!==this.generation) return;
      this.previous=frame; this.last=frame;
      this.timer=this.schedule(()=>this.tick(gen),interval);
    } catch(e) {
      if(gen===this.generation) this.pause('attention',e.message);
    } finally { this.busy=false; }
  }
  async tick(gen) {
    if(!this.running || gen!==this.generation || this.busy) return;
    this.busy=true;
    this.controller=new AbortController();
    try {
      const current=await this.capture();
      if(gen!==this.generation) return;
      if(current.time<this.last.time) throw new Error('画面时间无效，请重新开始。');
      if(current.time-this.previous.time>30000) this.previous=this.last;
      this.onState('checking','正在判断这次采样；两次采样之间的变化可能被漏掉。');
      const result=this.observe ? await this.observe(current,this.controller.signal) : await this.judge({task:this.task,frames:[
        {image:this.previous.image,seconds_ago:Math.max(0,(current.time-this.previous.time)/1000)},
        {image:current.image,seconds_ago:0}]},this.controller.signal);
      if(gen!==this.generation) return;
      if(!['event','no_event','uncertain'].includes(result.status)) throw new Error('模型返回无效，请重新开始。');
      if(result.status==='event' && (this.observe ? result.alert : !this.latched)) {
        this.latched=true;
        await this.onEvent({task:this.task,before:this.previous.image,after:current.image,time:Date.now(),result});
      }
      if(result.status==='no_event') this.latched=false;
      if(result.status!=='uncertain') this.previous=current;
      this.last=current;
      this.onState(result.status,
        result.status==='event'?'检测到你关心的事件，请查看前后画面。':
        result.status==='uncertain'?'本次画面无法确定，请检查光线、遮挡或任务描述。':'本次采样未发现事件，继续看守。',result);
    } catch(e) {
      if(gen===this.generation) this.pause('attention',e.message || '判断失败，请重新开始。');
    } finally {
      this.busy=false;
      if(this.running && gen===this.generation) this.timer=this.schedule(()=>this.tick(gen),this.interval);
    }
  }
}

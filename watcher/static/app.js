import { WatchSession } from './session.mjs';
const $=id=>document.getElementById(id);
let stream=null,opening=false,compiling=false,checks=0,audio=null,activeTask=null,serverSession=null;
const token=document.querySelector('meta[name="watcher-token"]').content;
async function api(path,method="GET",body){
 const response=await fetch(path,{method,headers:{"Content-Type":"application/json","X-Watcher-Token":token},body:body===undefined?undefined:JSON.stringify(body)});
 const value=await response.json();if(!response.ok) throw new Error(value.message || "本机服务暂不可用，请手动重试。");return value;
}
function notify(action){
 if(!serverSession)return;
 const owned=serverSession;if(action==='pause')serverSession=null;
 api("/api/control","POST",{action,session_id:owned}).catch(()=>{});
}
const names={idle:'等待开始',paused:'已暂停',preparing:'准备看守',checking:'正在判断',event:'发现事件',no_event:'正在看守',uncertain:'需要关注 · 无法确定',attention:'需要关注'};
function buttons(){
  $('camera').disabled=opening || !!stream;
  $('start').disabled=!stream || session.running || session.busy || opening || compiling;
  $('pause').disabled=!session.running;
  $('close').disabled=!stream;
  $('task').disabled=session.running || compiling;
  $('interval').disabled=session.running;
  $('voice').disabled=session.running || compiling || !(window.SpeechRecognition || window.webkitSpeechRecognition);
  document.querySelectorAll('.example').forEach(b=>b.disabled=session.running);
}
function setState(state,detail,result){
  $('status').textContent=names[state] || state;
  $('status').dataset.state=state;
  $('detail').textContent=detail;
  if(result){
    checks++; $('count').textContent=`已判断 ${checks} 次`;
    $('checked').textContent=`上次判断 ${new Date().toLocaleTimeString()}`;
    $('latency').textContent=`${result.latency_seconds.toFixed(2)} 秒 · 置信度 ${Math.round(result.confidence*100)}%`;
  }
  buttons();
}
async function capture(){
  const v=$('video'), track=stream?.getVideoTracks()[0];
  if(!track || track.readyState!=='live' || track.muted || v.readyState<2) throw new Error('摄像头画面不可用，请重新开启。');
  // Wait for a newly presented frame rather than reusing a frozen preview.
  if(v.requestVideoFrameCallback){
    await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{v.cancelVideoFrameCallback(id);reject(new Error('摄像头画面没有更新，请重新开启。'));},2500);
      const id=v.requestVideoFrameCallback(()=>{clearTimeout(timer);resolve();});
    });
  }
  if(!stream || track.readyState!=='live' || track.muted) throw new Error('摄像头已断开。');
  const scale=Math.min(1,960/v.videoWidth,960/v.videoHeight);
  const canvas=document.createElement('canvas');
  canvas.width=Math.round(v.videoWidth*scale);canvas.height=Math.round(v.videoHeight*scale);
  if(Math.min(canvas.width,canvas.height)<280) throw new Error('摄像头分辨率太低，请使用宽高至少 280 像素的画面。');
  canvas.getContext('2d').drawImage(v,0,0,canvas.width,canvas.height);
  return {image:canvas.toDataURL('image/jpeg',.85),time:Date.now()};
}
async function judge(body,signal){
  const timeout=new AbortController();
  const abort=()=>timeout.abort();signal.addEventListener('abort',abort,{once:true});
  const timer=setTimeout(abort,23000);
  try{
    const r=await fetch('/api/judge',{method:'POST',headers:{'Content-Type':'application/json','X-Watcher-Token':document.querySelector('meta[name="watcher-token"]').content},body:JSON.stringify({...body,task_id:activeTask?.id}),signal:timeout.signal});
    const result=await r.json();
    if(!r.ok) throw new Error(result.message || '判断失败，请重新开始。');
    return result;
  }catch(e){
    if(e.name==='AbortError') throw new Error('请求已取消或超时，请重新开始。');
    if(e instanceof TypeError) throw new Error('无法连接本机服务，请检查服务是否运行。');
    throw e;
  }finally{clearTimeout(timer);signal.removeEventListener('abort',abort);}
}
function eventCard(event){
  $('empty').hidden=true;
  const card=document.createElement('article');card.className='event-card';
  const title=document.createElement('h3');title.textContent=event.task;
  const when=document.createElement('p');when.textContent=`发现事件 · ${new Date(event.time).toLocaleString()}`;
  const pair=document.createElement('div');pair.className='pair';
  for(const [label,src] of [['前一帧',event.before || `/api/events/${event.id}/before`],['触发帧',event.after || `/api/events/${event.id}/after`]]){
    const fig=document.createElement('figure'),img=document.createElement('img'),caption=document.createElement('figcaption');
    img.src=src;img.alt=label;caption.textContent=label;fig.append(img,caption);pair.append(fig);
  }
  const remove=document.createElement('button');remove.textContent='删除';remove.className='text-button';remove.onclick=async()=>{try{await api(`/api/events/${event.id}`,'DELETE');card.remove();$('empty').hidden=!!$('events').children.length;$('event-count').textContent=`${$('events').children.length} 条`;}catch(e){setState('attention',e.message);}};
  card.append(when,title,pair,remove);$('events').prepend(card);
  while($('events').children.length>100) $('events').lastChild.remove();
  $('event-count').textContent=`${$('events').children.length} 条`;
  document.title='● 发现事件 · 看守';
  if(audio && audio.state==='running'){
    const osc=audio.createOscillator(),gain=audio.createGain();
    osc.frequency.value=740;gain.gain.value=.1;osc.connect(gain);gain.connect(audio.destination);osc.start();osc.stop(audio.currentTime+.25);
  }
}
async function observe(frame,signal){
 const controller=new AbortController();const cancel=()=>controller.abort();
 signal.addEventListener('abort',cancel,{once:true});const timer=setTimeout(cancel,23000);
 try{
  const response=await fetch('/api/observe',{method:'POST',headers:{'Content-Type':'application/json','X-Watcher-Token':token},body:JSON.stringify({session_id:serverSession,frame}),signal:controller.signal});
  const value=await response.json();if(!response.ok)throw new Error(value.message || '判断失败，请手动重试。');return value;
 }catch(error){
  if(error.name==='AbortError')throw new Error('请求已取消或超时，看守已暂停，请手动重试。');
  if(error instanceof TypeError)throw new Error('无法连接本机服务，看守已暂停，请检查后手动重试。');
  throw error;
 }finally{clearTimeout(timer);signal.removeEventListener('abort',cancel);}
}
const session=new WatchSession({capture,judge,observe,onState:(...args)=>{setState(...args);if(['paused','attention'].includes(args[0])) notify('pause');},onEvent:async event=>{
 if(event.result.event)eventCard(event.result.event);
}});
$('camera').onclick=async()=>{
  if(opening || stream) return;
  opening=true;buttons();setState('preparing','请允许浏览器访问摄像头。');
  try{
    if(!navigator.mediaDevices?.getUserMedia) throw new Error('请使用本机 localhost 地址，并允许浏览器访问摄像头。');
    stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1280},height:{ideal:720}},audio:false});
    $('video').srcObject=stream;await $('video').play();$('placeholder').hidden=true;
    const track=stream.getVideoTracks()[0];
    track.addEventListener('ended',()=>closeCamera('attention','摄像头已断开，请重新开启。'));
    track.addEventListener('mute',()=>session.pause('attention','摄像头画面暂不可用，请检查后重新开始。'));
    setState('idle','摄像头已就绪，点击「开始看守」后发送采样画面。');
  }catch(e){
    stream?.getTracks().forEach(t=>t.stop());stream=null;
    const messages={NotAllowedError:'摄像头权限未获允许，请在浏览器地址栏设置中开启。',NotFoundError:'没有找到摄像头，请连接摄像头后重试。',NotReadableError:'摄像头被占用或无法打开，请关闭其他使用它的程序。'};
    setState('attention',messages[e.name] || e.message);
  }finally{opening=false;buttons();}
};
$('start').onclick=async()=>{
  const task=$('task').value.trim();if(!task){$('task').focus();return;}
  try{audio ||= new AudioContext();await audio.resume();}catch{}
  compiling=true;buttons();setState('preparing','正在建立任务，首次编译可能需要约 90 秒。');
  try{
    const saved=await api('/api/tasks','POST',{task});activeTask=saved.task;
    if(document.hidden || !stream) return;
    const started=await api('/api/control','POST',{action:'start'});serverSession=started.session_id;
    await session.start(task,Number($('interval').value));
  }catch(e){setState('attention',e.message);}
  finally{compiling=false;buttons();}
};
$('pause').onclick=()=>{session.pause();buttons();};
function closeCamera(state='paused',detail='摄像头已关闭，不再看守。'){
  session.pause(state,detail);stream?.getTracks().forEach(t=>t.stop());stream=null;
  $('video').srcObject=null;$('placeholder').hidden=false;buttons();
}
$('close').onclick=()=>closeCamera();
$('clear').onclick=async()=>{try{await api('/api/events','DELETE');$('events').replaceChildren();$('event-count').textContent='0 条';$('empty').hidden=false;document.title='看守 · 把一件事交给它';}catch(e){setState('attention',e.message);}};
document.querySelectorAll('.example').forEach(b=>b.onclick=()=>{$('task').value=b.dataset.task;});
document.addEventListener('visibilitychange',()=>{if(document.hidden && session.running) session.pause('paused','页面进入后台，看守已暂停；返回后请手动开始。');});
window.addEventListener('pagehide',()=>closeCamera());
// Update controls when cancelled work finishes, without changing displayed state.
setInterval(buttons,250);
buttons();

api('/api/state').then(saved=>{
 activeTask=saved.task;if(activeTask) $('task').value=activeTask.task;
 for(const event of saved.events.slice().reverse()) eventCard(event);
 setState('paused','已恢复本地任务与事件。看守已暂停，请手动开启摄像头并开始。');
}).catch(e=>setState('attention',e.message));
let boardRequest=null;
setInterval(async()=>{try{const action=await api('/api/board/control');if(!action.request_id || action.request_id===boardRequest)return;boardRequest=action.request_id;
 if(action.action==='pause')session.pause();
 if(action.action==='start' && stream && !session.running && !compiling)$('start').click();
 if(action.action==='history')$('events').scrollIntoView();
}catch{}},2000);
const Recognition=window.SpeechRecognition || window.webkitSpeechRecognition;
$('voice').disabled=!Recognition;
$('voice-hint').textContent=Recognition?'可用语音填写任务，识别后请检查文字。':'此浏览器不支持语音输入，请直接输入任务。';
$('voice').onclick=()=>{try{const recognition=new Recognition();recognition.lang='zh-CN';recognition.onresult=event=>{if(!session.running && !compiling)$('task').value=event.results[0][0].transcript;};recognition.onerror=()=>{$('voice-hint').textContent='语音输入未完成，请重试或直接输入。';};recognition.start();}catch{$('voice-hint').textContent='语音输入不可用，请直接输入。';}};
const voiceNames={idle:'等待板卡语音命令',recognizing:'正在识别板卡录音…',failed:'语音命令未完成，请重新点 SPEAK 后说话。',cancelled:'语音命令已取消。'};
const voiceActions={pause:'已暂停看守',start:'已接受继续看守命令',task:'已接受新的看守任务'};
let lastBoardVoice='';
async function refreshBoardVoice(){
 try{
  const value=await api('/api/voice/state');
  $('board-voice-state').textContent=value.status==='done'?(voiceActions[value.action] || '命令已处理'):(voiceNames[value.status] || '等待板卡语音命令');
  $('board-voice-text').textContent=value.text?`识别文字：${value.text}`:'';
  const identity=JSON.stringify([value.status,value.text,value.action]);
  if(identity!==lastBoardVoice && value.status==='done' && !session.running && !compiling){
   const saved=await api('/api/state');activeTask=saved.task;
   if(value.action==='task' && activeTask)$('task').value=activeTask.task;
   $('events').replaceChildren();$('empty').hidden=false;
   for(const event of saved.events.slice().reverse())eventCard(event);
   $('event-count').textContent=`${saved.events.length} 条`;
  }
  lastBoardVoice=identity;
 }catch{
  $('board-voice-state').textContent='暂时无法读取板卡语音状态。';
 }
}
refreshBoardVoice();setInterval(refreshBoardVoice,2000);

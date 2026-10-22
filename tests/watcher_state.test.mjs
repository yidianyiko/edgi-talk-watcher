import test from 'node:test';
import assert from 'node:assert/strict';
import { WatchSession } from '../watcher/static/session.mjs';

function setup(judge) {
  const states=[], events=[]; let next;
  const session = new WatchSession({capture:async()=>({image:'frame',time:Date.now()}),judge,
    onState:(...s)=>states.push(s),onEvent:e=>events.push(e),
    schedule:fn=>{next=fn;return 1;},cancel:()=>{next=null;}});
  return {session,states,events,tick:()=>next()};
}
test('paused session ignores in-flight result and sends no new request',async()=>{
  let finish;
  const x=setup(()=>new Promise(r=>{finish=r;}));
  await x.session.start('task',3000);
  const pending=x.tick();
  await Promise.resolve(); // Let capture finish so the request is actually in flight.
  assert.equal(typeof finish,'function');
  x.session.pause(); finish({status:'event'}); await pending;
  assert.equal(x.events.length,0);
  assert.equal(x.states.at(-1)[0],'paused');
  assert.equal(x.session.running,false);
});
test('persistent event alerts once; no_event rearms',async()=>{
  const results=['event','event','uncertain','event','no_event','event'];
  const x=setup(async()=>({status:results.shift()}));
  await x.session.start('task',3000);
  for(let i=0;i<6;i++) await x.tick();
  assert.equal(x.events.length,2);
});
test('network failure stops watch and requests attention',async()=>{
  const x=setup(async()=>{throw new Error('连接失败');});
  await x.session.start('task',3000); await x.tick();
  assert.equal(x.session.running,false);
  assert.equal(x.states.at(-1)[0],'attention');
});
test('default timers do not receive the session as their browser receiver',async()=>{
  const originalSet=globalThis.setTimeout,originalClear=globalThis.clearTimeout;
  globalThis.setTimeout=function(){assert.equal(this,undefined);return 1;};
  globalThis.clearTimeout=function(){assert.equal(this,undefined);};
  try{
    const x=new WatchSession({capture:async()=>({image:'frame',time:0}),judge:async()=>({status:'no_event'}),onState:()=>{},onEvent:()=>{}});
    await x.start('task',3000);
    assert.equal(x.running,true);
    x.pause();
  }finally{globalThis.setTimeout=originalSet;globalThis.clearTimeout=originalClear;}
});
test('uncertain retains trustworthy reference until thirty second expiry',async()=>{
 const frames=[0,5000,10000,40000].map(time=>({image:String(time),time}));const pairs=[];let next;
 const s=new WatchSession({capture:async()=>frames.shift(),judge:async body=>{pairs.push(body.frames.map(f=>f.image));return {status:'uncertain'};},onState:()=>{},onEvent:()=>{},schedule:fn=>{next=fn;},cancel:()=>{}});
 await s.start('task',5000);await next();await next();await next();
 assert.deepEqual(pairs,[['0','5000'],['0','10000'],['10000','40000']]);
});

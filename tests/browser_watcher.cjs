// Real local HTTP app, deterministic server model and Chromium virtual camera.
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const output=path.resolve(process.env.WATCHER_BROWSER_OUTPUT || path.join(__dirname,'../artifacts/product-completion/web'));fs.mkdirSync(output,{recursive:true});
const data=fs.mkdtempSync('/tmp/watcher-browser-');const port=18765,url=`http://127.0.0.1:${port}`;let server;
function launch(){server=spawn('python3',['-m','tests.web_fixture_server','--data-dir',data,'--port',String(port)],{cwd:path.resolve(__dirname,'..'),stdio:['ignore','ignore','ignore']});}
async function ready(){for(let i=0;i<100;i++){try{if((await fetch(url)).ok)return;}catch{}await new Promise(r=>setTimeout(r,50));}throw new Error('fixture startup failed');}
(async()=>{launch();await ready();const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH || undefined,headless:true,args:['--no-sandbox','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1080}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(url);await page.waitForFunction(()=>document.querySelector('#status').dataset.state==='paused');
 const voiceResponse=await page.evaluate(async()=>{
  const pcm=new Uint8Array(32000);for(let i=1;i<pcm.length;i+=2)pcm[i]=16;
  const response=await fetch('/api/board/voice',{method:'POST',headers:{Authorization:'Bearer browser-board-voice','Content-Type':'application/octet-stream','X-Voice-Request':'browser-pause'},body:pcm});return {status:response.status,body:await response.text()};
 });assert.deepEqual(voiceResponse,{status:200,body:'ok pause\n'});
 await page.waitForFunction(()=>document.querySelector('#board-voice-state').textContent==='已暂停看守');
 assert.equal(await page.locator('#board-voice-text').innerText(),'识别文字：暂停看守。');
 await page.addInitScript(()=>{window.SpeechRecognition=class{start(){this.onresult({results:[[{transcript:'杯子消失时提醒我'}]]});}};});await page.reload();await page.waitForFunction(()=>document.querySelector('#status').dataset.state==='paused');await page.click('#voice');assert.equal(await page.inputValue('#task'),'杯子消失时提醒我');
 await page.click('.example');await page.click('#camera');await page.waitForFunction(()=>!document.querySelector('#start').disabled);
 await page.selectOption('#interval','3000');await page.click('#start');await page.waitForSelector('.event-card',{timeout:15000});
 await page.waitForFunction(()=>document.querySelector('#count').textContent==='已判断 2 次',{},{timeout:12000});
 assert.equal(await page.locator('.event-card').count(),1);
 await page.click('#pause');await page.screenshot({path:path.join(output,'event.png'),fullPage:true});
 const task=await page.inputValue('#task');await page.reload();await page.waitForSelector('.event-card');
 assert.equal(await page.inputValue('#task'),task);assert.equal(await page.locator('#status').innerText(),'已暂停');assert.equal(await page.evaluate(()=>document.querySelector('video').srcObject),null);
 assert.equal(await page.locator('.event-card img').first().evaluate(img=>img.complete&&img.naturalWidth>0),true);
 // A complete server process restart must recover persisted plan and screenshots.
 await new Promise(resolve=>{server.once('exit',resolve);server.kill('SIGTERM');});launch();await ready();await page.reload();await page.waitForSelector('.event-card');
 assert.equal(await page.inputValue('#task'),task);assert.equal(await page.locator('#status').innerText(),'已暂停');
 await page.click('#camera');await page.waitForFunction(()=>!document.querySelector('#start').disabled);
 await page.fill('#task','预测明天是否下雨');await page.click('#start');await page.waitForFunction(()=>document.querySelector('#status').dataset.state==='attention');assert.match(await page.innerText('#detail'),/仅支持/);
 await page.fill('#task',task);let failedCalls=0;await page.route('**/api/observe',async route=>{failedCalls++;await route.abort();});await page.click('#start');await page.waitForFunction(()=>document.querySelector('#status').dataset.state==='attention');await page.waitForTimeout(3600);assert.equal(failedCalls,1);await page.unroute('**/api/observe');
 await page.click('#start');await page.waitForFunction(()=>document.querySelector('#status').dataset.state==='preparing');await page.click('#pause');
 await page.click('#clear');await page.waitForFunction(()=>document.querySelector('#events').children.length===0);await page.reload();await page.waitForFunction(()=>document.querySelector('#status').dataset.state==='paused');assert.equal(await page.locator('.event-card').count(),0);
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.deepEqual(errors,[]);
 const report={realHttpServer:true,virtualCamera:true,deterministicModel:true,paidCalls:0,persistentImages:true,processRestartPaused:true,unsupportedRejected:true,networkFailureStops:true,duplicateSuppressed:true,deletePersists:true,voiceMocked:true,jsErrors:errors};fs.writeFileSync(path.join(output,'browser-report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>{server?.kill();fs.rmSync(data,{recursive:true,force:true});});

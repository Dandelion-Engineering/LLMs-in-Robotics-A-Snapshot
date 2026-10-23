// Isolated installed Edge, public CDP, our loopback player only. No accounts/profile reuse.
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const dir=__dirname,qa=path.join(dir,'qa-browser-v3');fs.mkdirSync(qa,{recursive:true});
const sourceVideo=JSON.parse(fs.readFileSync(path.join(dir,'source-timecode-manifest.json'),'utf8')).video;
const profile=path.join(dir,'.local','edge-playback-v3');fs.mkdirSync(profile,{recursive:true});
const url=process.argv[2];if(!/^http:\/\/127\.0\.0\.1:\d+\/$/.test(url))throw Error('Loopback player required');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const browser=spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',[
 '--headless=new','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync',
 '--autoplay-policy=no-user-gesture-required','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',
 '--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
let ws,id=0,pending=new Map(),exceptions=[];
async function main(){
 let port;for(let i=0;i<100;i++){try{port=Number(fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0]);break}catch{}await sleep(200)}
 if(!port)throw Error('No isolated browser debugging port');
 const tab=await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`,{method:'PUT'})).json();
 ws=new WebSocket(tab.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject});
 ws.onmessage=e=>{const r=JSON.parse(e.data);if(r.id){const p=pending.get(r.id);pending.delete(r.id);r.error?p.reject(Error(JSON.stringify(r.error))):p.resolve(r.result)}else if(r.method==='Runtime.exceptionThrown')exceptions.push(r.params)};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}))});
 const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value};
 await call('Page.enable');await call('Runtime.enable');await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1080,deviceScaleFactor:1,mobile:false});
 const version=await call('Browser.getVersion');const navigation=await call('Page.navigate',{url});if(navigation.errorText)throw Error(navigation.errorText);
 let ready=false;for(let i=0;i<100;i++){if(await evaluate("document.querySelector('video')?.readyState>=2")){ready=true;break}await sleep(200)}
 if(!ready)throw Error('Video element did not become ready: '+await evaluate('document.body.innerText'));
 await evaluate(`(()=>{const v=document.querySelector('video');window.reviewPresented=0;function frame(){window.reviewPresented++;v.requestVideoFrameCallback(frame)}v.requestVideoFrameCallback(frame);v.muted=true;v.playbackRate=1;v.currentTime=0;return v.play().then(()=>true)})()`);
 const started=Date.now(),targets=[1.5,10,26,37.5,43,53,62,69,75.8,83,90,99,105,111,115,123,130,138],captures=[],samples=[];
 let next=0,lastLog=-1;
 while(true){
   const s=await evaluate(`(()=>{const v=document.querySelector('video');return {time:v.currentTime,duration:v.duration,paused:v.paused,ended:v.ended,rate:v.playbackRate,ready:v.readyState,error:v.error?.message||null,width:v.videoWidth,height:v.videoHeight,presented:window.reviewPresented}})()`);
   s.wall_elapsed_s=(Date.now()-started)/1000;samples.push(s);if(s.error)throw Error(s.error);
   if(next<targets.length&&s.time>=targets[next]){
     const phone=(s.time>=49&&s.time<77)||(s.time>=97&&s.time<103)||s.time>=127;
     await evaluate(`document.querySelector('video').style.width='${phone?'640px':'1280px'}'`);await sleep(80);
     const rect=await evaluate(`(()=>{const r=document.querySelector('video').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,scale:1}})()`);
     const image=await call('Page.captureScreenshot',{format:'png',clip:rect,captureBeyondViewport:true});
     const name=`playback-${String(next).padStart(2,'0')}-${phone?'phone':'desktop'}.png`;fs.writeFileSync(path.join(qa,name),Buffer.from(image.data,'base64'));
     captures.push({target_video_s:targets[next],observed_video_s:s.time,phone,clip:rect,file:'qa-browser-v3/'+name});next++;
   }
   const ten=Math.floor(s.time/10);if(ten!==lastLog){console.log(`Normal playback: ${s.time.toFixed(2)} / 140 s; ${s.presented} presented frames`);lastLog=ten}
   if(s.ended)break;if(Date.now()-started>190000)throw Error('Playback did not finish within the bounded review');await sleep(250);
 }
 const final=samples.at(-1);if(final.time<139.95||final.rate!==1||captures.length!==targets.length||exceptions.length)throw Error('Playback review failed');
 const report={passed:true,method:'Full 1x playback of actual MP4 in isolated installed headless Edge; direct screenshots of video element at semantic points.',
   browser:version,source_video:sourceVideo,elapsed_wall_s:(Date.now()-started)/1000,final,captures,samples,exceptions,
   cua_failures:['trusted Node process exited unexpectedly; kernel reset, rerun your request','Repeated same initial-create call failed before browser state was available.'],
   visibility:'Loopback only; a fresh isolated QA profile was used. No repository publication or user browser profile access.'};
 fs.writeFileSync(path.join(dir,'browser-playback-review.json'),JSON.stringify(report,null,2)+'\n');
 await call('Browser.close');console.log('Browser playback review passed.');
}
main().catch(e=>{fs.writeFileSync(path.join(dir,'browser-playback-failure.json'),JSON.stringify({error:String(e),exceptions},null,2)+'\n');console.error(e);if(browser.pid)browser.kill();process.exitCode=1});

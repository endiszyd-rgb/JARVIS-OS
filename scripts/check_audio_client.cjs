/* Controlled API/microphone/clock checks, not a real browser or hardware test. */
'use strict';
const assert=require('node:assert/strict');
const JarvisAudioSession=require('../jarvis/audio_client.js');
const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
class Clock{
 constructor(){this.now=0;this.next=0;this.timers=new Map();}
 set=(fn,delay)=>{const id=++this.next;this.timers.set(id,{at:this.now+delay,fn});return id;};
 clear=id=>this.timers.delete(id);
 async advance(ms){const end=this.now+ms;while(true){const due=[...this.timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!due)break;this.now=due[1].at;this.timers.delete(due[0]);due[1].fn();await flush();}this.now=end;await flush();}
}
function stream(){const tracks=[{stops:0,stop(){this.stops++;}},{stops:0,stop(){this.stops++;}}];return {getTracks:()=>tracks,tracks};}
function setup(options={}){
 const clock=new Clock(),requests=[],streams=[],states=[];
 let remote=null,serial=0,eventSerial=0,micCalls=0,playbackStops=0;
 const api={hook:null,remote:()=>remote,setRemote:s=>{remote={...s};}};
 const request=async(path,method,body)=>{
  requests.push({path,method,body});
  if(api.hook){const intercepted=api.hook(path,method,body);if(intercepted!==undefined)return await intercepted;}
  if(path==='voice/sessions'){remote={id:'session-'+(++serial),state:'idle',revision:0,reason:'not_activated'};return {...remote};}
  if(method==='GET')return {...remote};
  const target={activate:'listening',activity:'listening',process:'processing',speak:'speaking',complete:'listening',resume:'listening',interrupt:'listening',end:'idle',cancel:'idle'}[body.action];
  remote={...remote,state:target,revision:remote.revision+1,reason:target==='idle'?body.action:null};return {...remote};
 };
 let getMedia=async()=>{const value=stream();streams.push(value);return value;};
 const controller=new JarvisAudioSession({request,getUserMedia:c=>{assert.deepEqual(c,{audio:true});micCalls++;return getMedia(c);},onState:s=>states.push(s),stopPlayback:()=>playbackStops++,now:()=>clock.now,setTimeout:clock.set,clearTimeout:clock.clear,eventId:()=>String(++eventSerial),...options});
 return {controller,clock,requests,streams,states,api,setMedia:fn=>{getMedia=fn;},micCalls:()=>micCalls,playbackStops:()=>playbackStops};
}
async function noPrematureMic(){
 const s=setup(),created=deferred();
 s.api.hook=(path)=>path==='voice/sessions'?created.promise:undefined;
 assert.equal(s.micCalls(),0);assert.equal(s.clock.timers.size,0);
 const start=s.controller.start();await flush();assert.equal(s.micCalls(),0);
 s.api.setRemote({id:'manual-1',state:'idle',revision:0});created.resolve(s.api.remote());
 await start;assert.equal(s.micCalls(),1);assert.equal(s.controller.snapshot.mic_active,true);
 s.controller.stop();assert.equal(s.streams[0].tracks[0].stops,1);assert.equal(s.clock.timers.size,0);
}
async function rejectionClosesEverything(){
 const s=setup();s.setMedia(async()=>{throw Error('permission denied');});
 await assert.rejects(s.controller.start(),/permission denied/);
 assert.equal(s.controller.active,false);assert.equal(s.clock.timers.size,0);assert.equal(s.playbackStops(),1);
}
async function cancelledPermissionRace(){
 const s=setup(),permission=deferred(),late=stream();s.setMedia(()=>permission.promise);
 const start=s.controller.start();await flush();assert.equal(s.micCalls(),1);
 s.controller.cancel();assert.equal(s.controller.active,false);assert.equal(s.clock.timers.size,0);
 permission.resolve(late);await start;
 assert.ok(late.tracks.every(t=>t.stops===1));assert.equal(s.controller.snapshot.mic_active,false);
}
async function cancelledActivationNeverOpensMic(){
 const s=setup(),activation=deferred();s.api.hook=(_p,_m,b)=>b?.action==='activate'?activation.promise:undefined;
 const start=s.controller.start();await flush();s.controller.dispose();
 activation.resolve({id:'session-1',state:'listening',revision:1});await start;
 assert.equal(s.micCalls(),0);assert.equal(s.clock.timers.size,0);
 await assert.rejects(s.controller.start(),/disposed/);
 assert.ok(s.requests.some(r=>r.body?.action==='cancel'));
}
async function remoteExpiryAndPollError(){
 for(const failure of [false,true]){
  const s=setup();await s.controller.start();
  if(failure)s.api.hook=(_p,m)=>m==='GET'?Promise.reject(Error('offline')):undefined;
  else s.api.setRemote({...s.api.remote(),state:'idle',revision:2,reason:'silence_timeout'});
  await s.clock.advance(1000);
  assert.equal(s.controller.active,false);assert.ok(s.streams[0].tracks.every(t=>t.stops===1));assert.equal(s.clock.timers.size,0);
  assert.equal(s.controller.snapshot.local_reason,failure?'poll_error':'silence_timeout');
 }
}
async function localSilenceSurvivesHungPoll(){
 const s=setup(),poll=deferred();await s.controller.start();
 s.api.hook=(_p,m)=>m==='GET'?poll.promise:undefined;
 await s.clock.advance(30000);
 assert.equal(s.requests.filter(r=>r.method==='GET').length,1);
 assert.equal(s.controller.active,false);assert.equal(s.controller.snapshot.local_reason,'local_silence_timeout');
 assert.ok(s.streams[0].tracks.every(t=>t.stops===1));assert.equal(s.clock.timers.size,0);
 poll.resolve({id:'session-1',state:'listening',revision:1});await flush();assert.equal(s.controller.active,false);
}
async function localSilenceSurvivesPermissionHang(){
 const s=setup(),permission=deferred(),late=stream();s.setMedia(()=>permission.promise);
 const start=s.controller.start();await flush();await s.clock.advance(30000);
 assert.equal(s.controller.active,false);assert.equal(s.controller.snapshot.local_reason,'local_silence_timeout');assert.equal(s.clock.timers.size,0);
 permission.resolve(late);await start;assert.ok(late.tracks.every(t=>t.stops===1));
}
async function hungTransitionHasIndependentWatchdog(){
 const s=setup({phaseTimeoutMs:2000}),processing=deferred();await s.controller.start();
 s.api.hook=(_p,_m,b)=>b?.action==='process'?processing.promise:undefined;
 const pending=s.controller.process();await flush();assert.equal(s.controller.snapshot.mic_active,false);
 await assert.rejects(s.controller.process(),/pending/);
 await s.clock.advance(2000);assert.equal(s.controller.active,false);assert.equal(s.controller.snapshot.local_reason,'local_phase_timeout');
 assert.equal(s.requests.filter(r=>r.body?.action==='process').length,1);
 processing.resolve({id:'session-1',state:'processing',revision:2});await pending;assert.equal(s.clock.timers.size,0);
}
async function playbackTransitionsAndLifetime(){
 const s=setup();await s.controller.start();await s.controller.process();assert.equal(s.streams[0].tracks[0].stops,1);
 await s.controller.speak();assert.equal(s.micCalls(),1);
 await s.controller.complete();assert.equal(s.micCalls(),2);
 await s.controller.process();await s.controller.speak();const before=s.playbackStops();await s.controller.interrupt();
 assert.equal(s.playbackStops(),before+1);assert.equal(s.micCalls(),3);
 s.controller.dispose();assert.ok(s.streams.every(media=>media.tracks.every(t=>t.stops===1)));assert.equal(s.clock.timers.size,0);
 const life=setup({maxLifetimeMs:2000});await life.controller.start();await life.clock.advance(2000);
 assert.equal(life.controller.snapshot.local_reason,'local_lifetime_timeout');assert.equal(life.clock.timers.size,0);
}
async function rejectedApiAndActivity(){
 const s=setup();s.api.hook=()=>Promise.reject(Error('API unavailable'));
 await assert.rejects(s.controller.start(),/API unavailable/);assert.equal(s.micCalls(),0);assert.equal(s.clock.timers.size,0);
 const activity=setup();await activity.controller.start(5);await activity.clock.advance(4000);await activity.controller.activity();await activity.clock.advance(4000);
 assert.equal(activity.controller.active,true);await activity.clock.advance(1000);assert.equal(activity.controller.active,false);
}
async function streamHookCleanup(){
 const seen=[],s=setup({onStream:value=>seen.push(value)});await s.controller.start();
 assert.equal(seen[0],s.streams[0]);await s.controller.process();assert.equal(seen[1],null);
 await s.controller.resume();assert.equal(seen[2],s.streams[1]);s.controller.cancel();assert.equal(seen[3],null);
 assert.ok(s.streams.every(media=>media.tracks.every(t=>t.stops===1)));
 const broken=setup({onStream:value=>{if(value)throw Error('capture setup failed');}});
 await assert.rejects(broken.controller.start(),/capture setup failed/);
 assert.equal(broken.controller.active,false);assert.ok(broken.streams[0].tracks.every(t=>t.stops===1));
 assert.equal(broken.clock.timers.size,0);
}
async function endedMicrophoneStopsSession(){
 const s=setup(),media=stream(),listeners=[];
 for(const track of media.tracks)track.addEventListener=(event,fn)=>{assert.equal(event,'ended');listeners.push(fn);};
 s.setMedia(async()=>media);await s.controller.start();listeners[0]();
 assert.equal(s.controller.active,false);assert.equal(s.controller.snapshot.local_reason,'microphone_ended');
 assert.equal(s.clock.timers.size,0);assert.ok(media.tracks.every(t=>t.stops===1));
}
(async()=>{
 for(const test of [noPrematureMic,rejectionClosesEverything,cancelledPermissionRace,cancelledActivationNeverOpensMic,remoteExpiryAndPollError,localSilenceSurvivesHungPoll,localSilenceSurvivesPermissionHang,hungTransitionHasIndependentWatchdog,playbackTransitionsAndLifetime,rejectedApiAndActivity,streamHookCleanup,endedMicrophoneStopsSession])await test();
 console.log('12 audio client lifecycle checks passed with controlled mic/API/clock (no real browser).');
})().catch(error=>{console.error(error);process.exitCode=1;});

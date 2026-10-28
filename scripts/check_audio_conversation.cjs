/* Controlled conversation pipeline checks; no real audio, browser or model. */
'use strict';
const assert=require('node:assert/strict');
const Conversation=require('../jarvis/audio_conversation.js');
const flush=async()=>{for(let i=0;i<100;i++)await Promise.resolve();};
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
class Clock{
 constructor(){this.now=0;this.serial=0;this.timers=new Map();}
 set=(fn,ms)=>{const id=++this.serial;this.timers.set(id,{at:this.now+ms,fn});return id;};
 clear=id=>this.timers.delete(id);
 async advance(ms){const end=this.now+ms;while(true){const due=[...this.timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!due)break;this.now=due[1].at;this.timers.delete(due[0]);due[1].fn();await flush();}this.now=end;await flush();}
}
function setup(overrides={}){
 const clock=new Clock(),calls=[],controllers=[],captures=[],transcripts=[],replies=[],states=[],errors=[];
 const hooks={};let replyIndex=0;
 const operation=(name,args,value)=>{calls.push({name,args});if(hooks[name])return hooks[name](...args);return Promise.resolve(value);};
 const createController=callbacks=>{
  const ctrl={callbacks,active:false,state:'idle',get snapshot(){return {active:this.active,state:this.state};},
   emit(){callbacks.onState(this.snapshot);},
   stream(){callbacks.onStream({fake:true});},
   async start(seconds){await operation('start',[seconds],null);this.active=true;this.state='listening';this.emit();this.stream();},
   async activity(){await operation('activity',[],null);},
   async process(){await operation('process',[],null);this.state='processing';callbacks.onStream(null);this.emit();},
   async speak(){await operation('speak',[],null);this.state='speaking';this.emit();},
   async complete(){await operation('complete',[],null);this.state='listening';this.emit();this.stream();},
   async resume(){await operation('resume',[],null);this.state='listening';this.emit();this.stream();},
   async interrupt(){await operation('interrupt',[],null);callbacks.stopPlayback();this.state='listening';this.emit();this.stream();},
   stop(){calls.push({name:'stop'});this.active=false;this.state='idle';callbacks.onStream(null);this.emit();},
   cancel(){calls.push({name:'cancel'});this.active=false;this.state='idle';callbacks.onStream(null);this.emit();},
   dispose(){calls.push({name:'dispose'});this.active=false;this.state='idle';callbacks.onStream(null);this.emit();},
   remoteEnd(){this.active=false;this.state='idle';this.emit();}
  };controllers.push(ctrl);return ctrl;
 };
 const createCapture=callbacks=>{
  const capture={callbacks,closed:false,start:stream=>operation('capture',[stream],null),close(){this.closed=true;}};captures.push(capture);return capture;
 };
 const conversation=new Conversation({createController,createCapture,
  transcribe:(wav,signal)=>operation('transcribe',[wav,signal],{text:'Jak działa projekt?'}),
  chat:(text,session,signal)=>operation('chat',[text,session,signal],{reply:'Odpowiedź '+(++replyIndex),session_id:'chat-'+controllers.length}),
  synthesize:(text,signal)=>operation('synthesize',[text,signal],{audio:'controlled'}),
  play:(audio,signal)=>operation('play',[audio,signal],null),stopPlayback:()=>calls.push({name:'stopPlayback'}),
  onTranscript:text=>transcripts.push(text),onReply:(reply,meta)=>replies.push({reply,meta}),
  onState:s=>states.push(s),onError:error=>errors.push(error),now:()=>clock.now,setTimeout:clock.set,clearTimeout:clock.clear,...overrides});
 return {conversation,clock,calls,hooks,controllers,captures,transcripts,replies,states,errors};
}
const wav=()=>new ArrayBuffer(100);
const count=(s,name)=>s.calls.filter(c=>c.name===name).length;
async function successfulMultiTurn(){
 const s=setup();assert.equal(s.captures.length,0);await s.conversation.start();
 assert.equal(s.conversation.snapshot.stage,'listening');assert.equal(s.captures.length,1);
 await s.conversation.submit(wav());await s.conversation.submit(wav());
 assert.equal(s.conversation.snapshot.stage,'listening');assert.equal(count(s,'transcribe'),2);assert.equal(count(s,'chat'),2);
 assert.deepEqual(s.calls.filter(c=>c.name==='chat').map(c=>c.args[1]),[null,'chat-1']);
 assert.equal(s.replies.length,2);assert.equal(s.transcripts.length,2);assert.equal(s.captures.length,3);
 assert.equal(s.captures[0].closed,true);assert.equal(s.captures[1].closed,true);assert.equal(s.captures[2].closed,false);
 s.conversation.dispose();assert.equal(s.captures[2].closed,true);assert.equal(s.clock.timers.size,0);
}
async function emptyTranscriptResumes(){
 const s=setup();s.hooks.transcribe=()=>({text:'  '});await s.conversation.start();await s.conversation.submit(wav());
 assert.equal(count(s,'chat'),0);assert.equal(count(s,'synthesize'),0);assert.equal(count(s,'resume'),1);assert.equal(s.conversation.snapshot.stage,'listening');s.conversation.dispose();
}
async function stopPhrasesAndNonPhrase(){
 for(const text of ['Koniec rozmowy.','Zakończ rozmowę!','STOP JARVIS']){
  const s=setup();s.hooks.transcribe=()=>({text});await s.conversation.start();await s.conversation.submit(wav());
  assert.equal(s.conversation.active,false);assert.equal(count(s,'chat'),0);assert.equal(s.clock.timers.size,0);
 }
 assert.equal(Conversation.stopPhrase('Co oznacza stop Jarvis w instrukcji?'),false);
}
async function reviewCorrectsRejectsOrStops(){
 for(const outcome of ['Poprawiona wypowiedź',null,'koniec rozmowy']){
  const seen=[];const s=setup({reviewTranscript:async(text,signal)=>{seen.push({text,signal});return outcome;}});
  await s.conversation.start();await s.conversation.submit(wav());assert.equal(seen[0].text,'Jak działa projekt?');
  if(outcome==='Poprawiona wypowiedź')assert.equal(s.calls.find(c=>c.name==='chat').args[0],outcome);
  else assert.equal(count(s,'chat'),0);
  assert.ok(s.states.some(state=>state.stage==='reviewing'));
  if(outcome===null)assert.equal(s.conversation.snapshot.stage,'listening');
  s.conversation.dispose();
 }
}
async function cancellationIgnoresLateResults(){
 for(const stage of ['transcribe','chat','synthesize','play']){
  const s=setup(),wait=deferred();s.hooks[stage]=()=>wait.promise;await s.conversation.start();
  const pending=s.conversation.submit(wav());await flush();assert.equal(count(s,stage),1,stage);
  s.conversation.cancel();const callsAtCancel=s.calls.length;
  const value=stage==='transcribe'?{text:'Pozna wypowiedz'}:stage==='chat'?{reply:'Pozna odpowiedz',session_id:'late-chat'}:{};
  wait.resolve(value);await pending;await flush();
  assert.equal(s.conversation.active,false,stage);assert.equal(s.calls.length,callsAtCancel,stage);assert.equal(s.clock.timers.size,0,stage);
  if(stage==='transcribe')assert.equal(s.transcripts.length,0);
  if(stage==='chat')assert.equal(s.replies.length,0);
 }
}
async function errorsNeverRetry(){
 for(const stage of ['transcribe','chat','synthesize','play']){
  const s=setup();s.hooks[stage]=()=>Promise.reject(Error('controlled private service error'));await s.conversation.start();await s.conversation.submit(wav());
  assert.equal(s.conversation.active,false);assert.equal(count(s,stage),1);assert.equal(s.errors.length,1);
  assert.equal(s.errors[0].message.includes('private'),false);assert.equal(s.clock.timers.size,0);
 }
}
async function processingBudgetIsCumulative(){
 const s=setup({processingBudgetMs:1000}),asr=deferred(),chat=deferred();s.hooks.transcribe=()=>asr.promise;s.hooks.chat=()=>chat.promise;
 await s.conversation.start();const turn=s.conversation.submit(wav());await flush();await s.clock.advance(700);
 asr.resolve({text:'Dalsza wypowiedź'});await flush();assert.equal(count(s,'chat'),1);
 await s.clock.advance(300);await turn;assert.equal(s.conversation.active,false);assert.equal(s.errors.length,1);assert.equal(s.clock.timers.size,0);
 chat.resolve({reply:'za późno',session_id:'late'});await flush();assert.equal(s.replies.length,0);
}
async function playbackInterruptContinuesWithoutReplay(){
 const s=setup(),playing=deferred();s.hooks.play=()=>playing.promise;await s.conversation.start();
 const old=s.conversation.submit(wav());await flush();assert.equal(s.conversation.snapshot.stage,'speaking');
 await s.conversation.interrupt();await old;assert.equal(s.conversation.snapshot.stage,'listening');assert.equal(count(s,'interrupt'),1);assert.equal(count(s,'complete'),0);
 delete s.hooks.play;await s.conversation.submit(wav());assert.equal(count(s,'chat'),2);assert.equal(count(s,'complete'),1);
 playing.resolve();await flush();assert.equal(count(s,'complete'),1);s.conversation.dispose();
}
async function noOverlappingUtterancesOrActivity(){
 const s=setup(),activity=deferred(),asr=deferred();s.hooks.activity=()=>activity.promise;s.hooks.transcribe=()=>asr.promise;
 await s.conversation.start();s.captures[0].callbacks.onSpeechActivity();s.captures[0].callbacks.onSpeechActivity();await flush();assert.equal(count(s,'activity'),1);
 const turn=s.conversation.submit(wav());assert.deepEqual(await s.conversation.submit(wav()),{ignored:true});await flush();assert.equal(count(s,'process'),0);
 activity.resolve();await flush();assert.equal(count(s,'process'),1);assert.equal(count(s,'transcribe'),1);
 s.conversation.cancel();await turn;asr.resolve({text:'late'});await flush();assert.equal(s.clock.timers.size,0);
}
async function truncationAndSessionIsolation(){
 const s=setup();s.hooks.chat=()=>({reply:'a'.repeat(1200),session_id:'separate'});await s.conversation.start();await s.conversation.submit(wav());
 assert.equal(s.replies[0].reply.reply.length,1200);assert.equal(s.replies[0].meta.truncated,true);assert.equal(s.calls.find(c=>c.name==='synthesize').args[0].length,1000);
 s.conversation.stop();await s.conversation.start();assert.equal(s.conversation.snapshot.chat_session_id,null);await s.conversation.submit(wav());
 const requests=s.calls.filter(c=>c.name==='chat');assert.equal(requests[1].args[1],null);s.conversation.dispose();
}
async function remoteExpiryAndReviewCancellation(){
 const wait=deferred();let reviewSignal;
 const s=setup({reviewTranscript:(_text,signal)=>{reviewSignal=signal;return wait.promise;}});
 await s.conversation.start();const pending=s.conversation.submit(wav());await flush();assert.equal(s.conversation.snapshot.stage,'reviewing');
 s.controllers[0].remoteEnd();await pending;assert.equal(reviewSignal.aborted,true);assert.equal(count(s,'chat'),0);assert.equal(s.clock.timers.size,0);
 wait.resolve('Pozna korekta');await flush();assert.equal(count(s,'chat'),0);
}
async function staleCaptureAndWrongSessionAreRejected(){
 const s=setup();await s.conversation.start();const old=s.captures[0];await s.conversation.submit(wav());
 const before=s.calls.length;old.callbacks.onSpeechActivity();old.callbacks.onUtterance(wav());await flush();
 assert.equal(s.calls.length,before);assert.equal(s.conversation.snapshot.stage,'listening');
 s.hooks.chat=()=>({reply:'Unexpected session',session_id:'wrong-chat'});await s.conversation.submit(wav());
 assert.equal(s.conversation.active,false);assert.equal(s.replies.length,1);assert.equal(s.errors.length,1);assert.equal(count(s,'synthesize'),1);
}
async function oldControllerStreamCannotCloseNewCapture(){
 const s=setup();await s.conversation.start();const old=s.controllers[0];s.conversation.stop();await s.conversation.start();
 const current=s.captures.at(-1);old.callbacks.onStream(null);old.callbacks.onStream({stale:true});await flush();
 assert.equal(current.closed,false);assert.equal(s.captures.at(-1),current);assert.equal(s.conversation.active,true);s.conversation.dispose();
}
async function shortSilenceActivityThrottle(){
 const s=setup();await s.conversation.start(1);s.captures[0].callbacks.onSpeechActivity();await flush();assert.equal(count(s,'activity'),1);
 await s.clock.advance(334);s.captures[0].callbacks.onSpeechActivity();await flush();assert.equal(count(s,'activity'),2);s.conversation.dispose();
}
async function unicodeSpeechTruncationKeepsCodepoints(){
 const s=setup();s.hooks.chat=()=>({reply:'a'.repeat(999)+'😀'+'tail',session_id:'unicode-chat'});
 await s.conversation.start();await s.conversation.submit(wav());
 const spoken=s.calls.find(c=>c.name==='synthesize').args[0];assert.equal(Array.from(spoken).length,1000);assert.ok(spoken.endsWith('😀'));
 assert.equal(s.replies[0].meta.truncated,true);s.conversation.dispose();
}
async function immediateCancellationDoesNotStartResources(){
 for(const action of ['cancel','dispose']){
  const s=setup();const pending=s.conversation.start();s.conversation[action]();await pending;await flush();
  assert.equal(count(s,'start'),0,action);assert.equal(count(s,'capture'),0,action);assert.equal(s.controllers[0].active,false,action);assert.equal(s.clock.timers.size,0,action);
 }
 // A stream notification can enqueue setup in the same stack as cancellation.
 let callbacks;
 const captureRace=setup({createController:options=>{callbacks=options;return {snapshot:{active:false,state:'idle'},start:async()=>{},cancel(){},dispose(){},stop(){}};}});
 const pending=captureRace.conversation.start();
 callbacks.onStream({fake:true});captureRace.conversation.cancel();await pending;await flush();
 assert.equal(count(captureRace,'capture'),0);assert.equal(captureRace.captures[0].closed,true);assert.equal(captureRace.clock.timers.size,0);
}
async function releasedStreamNeverStartsDeferredCapture(){
 let callbacks;
 const s=setup({createController:options=>{callbacks=options;return {snapshot:{active:true,state:'listening'},start:async()=>{},cancel(){},dispose(){},stop(){}};}});
 const pending=s.conversation.start();callbacks.onStream({fake:true});const closed=s.captures[0];callbacks.onStream(null);
 await pending;await flush();assert.equal(closed.closed,true);assert.equal(count(s,'capture'),0);assert.equal(s.errors.length,0);s.conversation.dispose();assert.equal(s.clock.timers.size,0);
}
async function captureSetupErrorAndLateStart(){
 const s=setup();s.hooks.capture=()=>Promise.reject(Error('capture unavailable'));
 await s.conversation.start();assert.equal(s.conversation.active,false);assert.equal(s.captures[0].closed,true);assert.equal(s.errors.length,1);assert.equal(s.clock.timers.size,0);
 const late=setup(),starting=deferred();late.hooks.start=()=>starting.promise;
 const pending=late.conversation.start();await flush();late.conversation.dispose();starting.resolve();await pending;await flush();
 assert.equal(late.conversation.active,false);assert.equal(late.captures.length,0);assert.equal(late.clock.timers.size,0);
}
(async()=>{
 const checks=[successfulMultiTurn,emptyTranscriptResumes,stopPhrasesAndNonPhrase,reviewCorrectsRejectsOrStops,cancellationIgnoresLateResults,errorsNeverRetry,processingBudgetIsCumulative,playbackInterruptContinuesWithoutReplay,noOverlappingUtterancesOrActivity,truncationAndSessionIsolation,remoteExpiryAndReviewCancellation,captureSetupErrorAndLateStart,staleCaptureAndWrongSessionAreRejected,unicodeSpeechTruncationKeepsCodepoints,oldControllerStreamCannotCloseNewCapture,shortSilenceActivityThrottle,immediateCancellationDoesNotStartResources,releasedStreamNeverStartsDeferredCapture];
 for(const check of checks)await check();
 console.log(checks.length+' voice conversation checks passed with controlled capture/API/playback/clock (no browser/model).');
})().catch(error=>{console.error(error);process.exitCode=1;});

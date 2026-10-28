/* Serial owner voice conversation. No tool execution, wake word or hidden retries. */
(function(root){
'use strict';
const abortError=()=>Object.assign(Error('Audio operation cancelled'),{name:'AbortError'});
function stopPhrase(text){
 const value=text.toLocaleLowerCase('pl').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/ł/g,'l').trim().replace(/[.!?]+$/,'').trim();
 return ['koniec rozmowy','zakoncz rozmowe','stop jarvis'].includes(value);
}
class JarvisAudioConversation{
 constructor(options={}){
  for(const name of ['transcribe','chat','synthesize','play'])if(typeof options[name]!=='function')throw Error('Missing voice dependency: '+name);
  this.options=options;this.createController=options.createController||(o=>new root.JarvisAudioSession(o));
  this.createCapture=options.createCapture||(o=>new root.JarvisPcmCapture(o));
  this.now=options.now||(()=>performance.now());this.setTimer=options.setTimeout||((fn,delay)=>setTimeout(fn,delay));this.clearTimer=options.clearTimeout||(id=>clearTimeout(id));
  this.processingBudgetMs=options.processingBudgetMs??110000;this.playbackBudgetMs=options.playbackBudgetMs??110000;
  this.setupTimeoutMs=options.setupTimeoutMs??10000;this.activityIntervalMs=options.activityIntervalMs??1000;
  if(![this.processingBudgetMs,this.playbackBudgetMs,this.setupTimeoutMs,this.activityIntervalMs].every(v=>Number.isFinite(v)&&v>0)||this.processingBudgetMs>110000||this.playbackBudgetMs>110000)throw Error('Invalid bounded voice timeouts');
  this._epoch=0;this._turn=0;this._active=false;this._disposed=false;this._starting=false;this._inTurn=false;
  this._stage='idle';this._controller=null;this._capture=null;this._capturePromise=null;this._streamGeneration=0;
  this._pending=new Set();this._activityPromise=null;this._lastActivity=-Infinity;this._activityThrottleMs=this.activityIntervalMs;this._processingDeadline=null;this._chatSessionId=null;
 }
 get active(){return this._active;}
 get snapshot(){return {active:this._active,stage:this._stage,chat_session_id:this._chatSessionId,audio:this._controller?.snapshot||null};}
 _emit(){try{this.options.onState?.(this.snapshot);}catch(_){}}
 _current(epoch,turn=null){return this._active&&!this._disposed&&epoch===this._epoch&&(turn===null||turn===this._turn);}
 _setStage(stage){this._stage=stage;this._emit();}
 _notify(name,...args){try{this.options[name]?.(...args);}catch(_){}}
 _closeCapture(){this._streamGeneration++;const capture=this._capture;this._capture=null;this._capturePromise=null;try{capture?.close();}catch(_){}}
 _stopPlayback(){this._notify('stopPlayback');}
 _abortPending(){for(const item of [...this._pending])item.abort.abort();}
 _stop(reason,action){
  this._epoch++;this._turn++;this._active=false;this._starting=false;this._inTurn=false;this._processingDeadline=null;this._activityPromise=null;
  this._abortPending();this._closeCapture();this._stopPlayback();
  this._stage=reason;
  try{if(action==='dispose')this._controller?.dispose();else if(action==='end')this._controller?.stop();else if(action==='cancel')this._controller?.cancel();}catch(_){}
  this._emit();
 }
 stop(){this._stop('stopped','end');}
 cancel(){this._stop('stopped','cancel');}
 dispose(){if(this._disposed)return;this._disposed=true;this._stop('stopped','dispose');}
 _fail(stage,error){
  if(!this._active)return;
  this._stop('error','cancel');
  const safe=Object.assign(Error(error?.name==='AudioTimeout'?'Voice stage timed out: '+stage:'Voice stage failed: '+stage),{stage});
  this._notify('onError',safe);
 }
 async _call(name,operation,epoch,turn=null,timeoutMs=this.setupTimeoutMs){
  if(!this._current(epoch,turn))throw abortError();
  if(this._processingDeadline!==null)timeoutMs=Math.min(timeoutMs,this._processingDeadline-this.now());
  if(timeoutMs<=0)throw Object.assign(Error('Processing budget expired'),{name:'AudioTimeout'});
  const abort=new AbortController(),item={abort,timer:null};this._pending.add(item);
  let rejectAbort;
  const stopped=new Promise((_,reject)=>{rejectAbort=()=>reject(abortError());abort.signal.addEventListener('abort',rejectAbort,{once:true});});
  const timed=new Promise((_,reject)=>{item.timer=this.setTimer(()=>{reject(Object.assign(Error('Voice timeout'),{name:'AudioTimeout'}));abort.abort();},timeoutMs);});
  try{
   const result=await Promise.race([Promise.resolve().then(()=>{if(abort.signal.aborted||!this._current(epoch,turn))throw abortError();return operation(abort.signal);}),stopped,timed]);
   if(!this._current(epoch,turn))throw abortError();
   return result;
  }finally{
   this.clearTimer(item.timer);abort.signal.removeEventListener('abort',rejectAbort);this._pending.delete(item);
  }
 }
 _controllerState(snapshot,epoch){
  if(!this._current(epoch))return;
  if(snapshot.active===false){this._stop('stopped',null);return;}
  this._emit();
 }
 _stream(stream,epoch){
  if(!this._current(epoch))return;
  this._closeCapture();
  if(!stream||!this._current(epoch))return;
  const generation=this._streamGeneration;
  let capture;
  try{capture=this.createCapture({
   ...(this.options.captureOptions||{}),
   onSpeechActivity:()=>{if(this._current(epoch)&&generation===this._streamGeneration&&this._capture===capture)this._activity(epoch);},
   onUtterance:wav=>{if(this._current(epoch)&&generation===this._streamGeneration&&this._capture===capture)this.submit(wav).catch(()=>{});},
   onError:error=>{if(this._current(epoch)&&this._capture===capture)this._fail('capture',error);}
  });this._capture=capture;}catch(error){this._fail('capture',error);return;}
  const pending=this._call('capture',()=>{if(generation!==this._streamGeneration||this._capture!==capture)throw abortError();return capture.start(stream);},epoch).then(()=>{
   if(this._current(epoch)&&generation===this._streamGeneration)this._emit();
  });
  this._capturePromise=pending;
  pending.catch(error=>{if(this._current(epoch)&&this._capture===capture)this._fail('capture',error);});
 }
 async _waitCapture(epoch,turn=null){
  const pending=this._capturePromise;if(pending)await pending;
  if(!this._current(epoch,turn))throw abortError();
 }
 _activity(epoch){
  if(!this._current(epoch)||this._starting||this._inTurn||this._stage!=='listening'||this._activityPromise||this.now()-this._lastActivity<this._activityThrottleMs)return;
  this._lastActivity=this.now();
  const pending=this._call('activity',()=>this._controller.activity(),epoch);
  this._activityPromise=pending;
  pending.catch(error=>{if(this._current(epoch))this._fail('activity',error);}).finally(()=>{if(this._activityPromise===pending)this._activityPromise=null;});
 }
 async start(silenceSeconds=30){
  if(this._disposed)throw Error('Voice conversation is disposed');
  if(this._active)throw Error('Voice conversation is already active');
  if(!Number.isInteger(silenceSeconds)||silenceSeconds<1||silenceSeconds>300)throw Error('Use 1–300 seconds of silence');
  this._activityThrottleMs=Math.max(50,Math.min(this.activityIntervalMs,silenceSeconds*1000/3));
  const epoch=++this._epoch;this._turn=0;this._active=true;this._starting=true;this._inTurn=false;this._chatSessionId=null;this._lastActivity=-Infinity;
  this._setStage('starting');
  try{
   this._controller=this.createController({
    ...(this.options.controllerOptions||{}),
    onState:s=>this._controllerState(s,epoch),
    onStream:stream=>this._stream(stream,epoch),
    stopPlayback:()=>this._stopPlayback()
   });
   await this._call('start',()=>this._controller.start(silenceSeconds),epoch);
   await this._waitCapture(epoch);
   this._starting=false;this._setStage('listening');return this.snapshot;
  }catch(error){if(this._current(epoch)){this._fail('start',error);throw error;}return this.snapshot;}
 }
 async submit(wav){
  if(!this._active||this._starting||this._inTurn||this._stage!=='listening')return {ignored:true};
  const epoch=this._epoch,turn=++this._turn;this._inTurn=true;this._processingDeadline=this.now()+this.processingBudgetMs;this._setStage('processing');
  try{
   const size=wav?.byteLength;
   if(!Number.isInteger(size)||size<44||size>2*1024*1024)throw Error('Invalid captured WAV');
   if(this._activityPromise)await this._activityPromise;
   await this._call('process',()=>this._controller.process(),epoch,turn);
   this._setStage('transcribing');
   const result=await this._call('transcribe',signal=>this.options.transcribe(wav,signal),epoch,turn,this.processingBudgetMs);
   let text=typeof result==='string'?result:result?.text;
   if(typeof text!=='string'||text.length>8000)throw Error('Invalid transcript');
   text=text.trim();
   if(text){this._notify('onTranscript',text);if(stopPhrase(text)){this.stop();return this.snapshot;}}
   if(text&&typeof this.options.reviewTranscript==='function'){
    this._setStage('reviewing');
    text=await this._call('review',signal=>this.options.reviewTranscript(text,signal),epoch,turn,this.processingBudgetMs);
    if(text!==null&&(typeof text!=='string'||text.length>8000))throw Error('Invalid reviewed transcript');
    text=text?.trim()||'';
    if(text&&stopPhrase(text)){this.stop();return this.snapshot;}
   }
   if(!text){
    this._processingDeadline=null;await this._call('resume',()=>this._controller.resume(),epoch,turn);await this._waitCapture(epoch,turn);this._setStage('listening');return this.snapshot;
   }
   this._setStage('chatting');
   const reply=await this._call('chat',signal=>this.options.chat(text,this._chatSessionId,signal),epoch,turn,this.processingBudgetMs);
   if(!reply||typeof reply.reply!=='string'||!reply.reply.trim()||reply.reply.length>32000||typeof reply.session_id!=='string'||!reply.session_id)throw Error('Invalid chat reply');
   if(this._chatSessionId!==null&&reply.session_id!==this._chatSessionId)throw Error('Chat session changed unexpectedly');
   this._chatSessionId=reply.session_id;
   const characters=Array.from(reply.reply),spoken=characters.slice(0,1000).join(''),meta={spoken_text:spoken,truncated:characters.length>1000};
   this._notify('onReply',reply,meta);
   this._setStage('synthesizing');
   const audio=await this._call('synthesize',signal=>this.options.synthesize(spoken,signal),epoch,turn,this.processingBudgetMs);
   this._processingDeadline=null;
   await this._call('speak',()=>this._controller.speak(),epoch,turn);
   this._setStage('speaking');
   await this._call('playback',signal=>this.options.play(audio,signal),epoch,turn,this.playbackBudgetMs);
   await this._call('complete',()=>this._controller.complete(),epoch,turn);
   await this._waitCapture(epoch,turn);this._setStage('listening');return this.snapshot;
  }catch(error){if(this._current(epoch,turn))this._fail(this._stage,error);return this.snapshot;}
  finally{if(this._current(epoch,turn)){this._processingDeadline=null;this._inTurn=false;}}
 }
 async interrupt(){
  if(!this._active||this._stage!=='speaking')throw Error('Voice reply is not speaking');
  const epoch=this._epoch,turn=++this._turn;this._inTurn=true;this._processingDeadline=null;this._abortPending();this._stopPlayback();this._setStage('processing');
  try{
   await this._call('interrupt',()=>this._controller.interrupt(),epoch,turn);
   await this._waitCapture(epoch,turn);this._setStage('listening');return this.snapshot;
  }catch(error){if(this._current(epoch,turn))this._fail('interrupt',error);return this.snapshot;}
  finally{if(this._current(epoch,turn))this._inTurn=false;}
 }
}
if(typeof module!=='undefined'&&module.exports){module.exports=JarvisAudioConversation;module.exports.stopPhrase=stopPhrase;}
if(root)root.JarvisAudioConversation=JarvisAudioConversation;
})(typeof window!=='undefined'?window:null);

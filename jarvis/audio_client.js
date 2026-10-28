/* Manual microphone lifecycle laboratory; no VAD, STT, TTS or wake word. */
(function (root) {
'use strict';
class JarvisAudioSession {
 constructor(options={}) {
  if(typeof options.request!=='function')throw Error('An authenticated request function is required');
  this.request=options.request;
  this.getUserMedia=options.getUserMedia||(constraints=>navigator.mediaDevices.getUserMedia(constraints));
  this.onState=options.onState||(()=>{});
  this.onStream=options.onStream||(()=>{});
  this.stopPlayback=options.stopPlayback||(()=>{});
  this.now=options.now||(()=>performance.now());
  this.setTimer=options.setTimeout||((fn,delay)=>setTimeout(fn,delay));
  this.clearTimer=options.clearTimeout||(id=>clearTimeout(id));
  this.eventId=options.eventId||(()=>crypto.randomUUID());
  this.pollMs=options.pollMs??1000;
  this.maxLifetimeMs=options.maxLifetimeMs??900000;
  this.phaseTimeoutMs=options.phaseTimeoutMs??120000;
  if(![this.pollMs,this.maxLifetimeMs,this.phaseTimeoutMs].every(v=>Number.isFinite(v)&&v>0))throw Error('Positive audio timer limits are required');
  this._epoch=0;this._active=false;this._disposed=false;this._remote=null;this._stream=null;
  this._pollTimer=null;this._watchTimer=null;this._busyEpoch=null;this._micPending=null;
  this._lifetimeDeadline=null;this._silenceDeadline=null;this._phaseDeadline=null;this._reason='not_started';
 }
 get active(){return this._active;}
 get snapshot(){return {...(this._remote||{}),active:this._active,mic_active:!!this._stream,local_reason:this._reason};}
 _emit(){try{this.onState(this.snapshot);}catch(_){/* A view callback cannot keep the microphone open. */}}
 _stopStream(stream){if(stream)for(const track of stream.getTracks()){try{track.stop();}catch(_){}}}
 _releaseMic(){const stream=this._stream;this._stream=null;try{if(stream)this.onStream(null);}catch(_){}finally{this._stopStream(stream);}}
 _stopPlayback(){try{this.stopPlayback();}catch(_){}}
 _clearTimers(){if(this._pollTimer!==null)this.clearTimer(this._pollTimer);if(this._watchTimer!==null)this.clearTimer(this._watchTimer);this._pollTimer=this._watchTimer=null;}
 _bestEffort(action,snapshot){
  if(!snapshot||!snapshot.id||snapshot.state==='idle')return;
  try{Promise.resolve(this.request('voice/sessions/'+snapshot.id+'/events','POST',{event_id:this.eventId(),revision:snapshot.revision,action})).catch(()=>{});}catch(_){}
 }
 _shutdown(reason,action=null){
  const previous=this._remote;
  this._epoch++;this._active=false;this._reason=reason;this._busyEpoch=null;this._micPending=null;
  this._clearTimers();this._releaseMic();this._stopPlayback();
  this._lifetimeDeadline=this._silenceDeadline=this._phaseDeadline=null;
  this._emit();if(action)this._bestEffort(action,previous);
 }
 stop(){this._shutdown('ended','end');}
 cancel(){this._shutdown('cancelled','cancel');}
 dispose(){if(this._disposed)return;this._disposed=true;this._shutdown('disposed','cancel');}
 _current(epoch){return this._active&&!this._disposed&&epoch===this._epoch;}
 _accept(snapshot,epoch){
  if(!snapshot||typeof snapshot.id!=='string'||!Number.isInteger(snapshot.revision)||snapshot.revision<0||!['idle','listening','processing','speaking'].includes(snapshot.state))throw Error('Invalid audio-session response');
  if(!this._current(epoch)){this._bestEffort('cancel',snapshot);return false;}
  if(this._remote&&snapshot.id!==this._remote.id)throw Error('Audio session changed unexpectedly');
  if(this._remote&&snapshot.revision<this._remote.revision)return false;
  this._remote={...snapshot};
  if(snapshot.state==='idle'){this._shutdown(snapshot.reason||'remote_idle');return false;}
  if(snapshot.state!=='listening')this._releaseMic();
  this._emit();return true;
 }
 _armWatchdog(epoch){
  if(this._watchTimer!==null)this.clearTimer(this._watchTimer);
  this._watchTimer=null;
  if(!this._current(epoch))return;
  const deadlines=[this._lifetimeDeadline,this._silenceDeadline,this._phaseDeadline].filter(v=>v!==null);
  const deadline=Math.min(...deadlines);
  const delay=Math.max(0,deadline-this.now());
  this._watchTimer=this.setTimer(()=>{
   this._watchTimer=null;if(!this._current(epoch))return;
   const now=this.now();
   if(now>=this._lifetimeDeadline)this._shutdown('local_lifetime_timeout','cancel');
   else if(this._silenceDeadline!==null&&now>=this._silenceDeadline)this._shutdown('local_silence_timeout','cancel');
   else if(this._phaseDeadline!==null&&now>=this._phaseDeadline)this._shutdown('local_phase_timeout','cancel');
   else this._armWatchdog(epoch);
  },delay);
 }
 _listening(epoch){this._phaseDeadline=null;this._silenceDeadline=this.now()+this._silenceSeconds*1000;this._armWatchdog(epoch);}
 _phase(epoch){this._silenceDeadline=null;this._phaseDeadline=this.now()+this.phaseTimeoutMs;this._armWatchdog(epoch);}
 async _acquire(epoch){
  if(!this._current(epoch)||this._remote?.state!=='listening'||this._stream)return;
  if(this._micPending?.epoch===epoch)return this._micPending.promise;
  const pending={epoch,promise:null};this._micPending=pending;
  pending.promise=(async()=>{
   const stream=await this.getUserMedia({audio:true});
   if(!stream||typeof stream.getTracks!=='function')throw Error('Invalid microphone stream');
   if(!this._current(epoch)||this._remote?.state!=='listening'){this._stopStream(stream);return;}
   this._stream=stream;
   for(const track of stream.getTracks())track.addEventListener?.('ended',()=>{if(this._current(epoch)&&this._stream===stream)this._shutdown('microphone_ended','cancel');},{once:true});
   try{this.onStream(stream);}catch(error){this._releaseMic();throw error;}
   this._emit();
  })();
  try{await pending.promise;}finally{if(this._micPending===pending)this._micPending=null;}
 }
 _schedulePoll(epoch){
  if(this._pollTimer!==null)this.clearTimer(this._pollTimer);
  this._pollTimer=null;if(!this._current(epoch))return;
  this._pollTimer=this.setTimer(()=>{this._pollTimer=null;this._poll(epoch).catch(()=>{});},this.pollMs);
 }
 async _poll(epoch){
  if(!this._current(epoch))return;
  if(this._busyEpoch===epoch){this._schedulePoll(epoch);return;}
  try{
   const snapshot=await this.request('voice/sessions/'+this._remote.id,'GET');
   if(!this._current(epoch))return;
   this._accept(snapshot,epoch);
   this._schedulePoll(epoch);
  }catch(_){if(this._current(epoch))this._shutdown('poll_error','cancel');}
 }
 async start(silenceSeconds=30){
  if(this._disposed)throw Error('Audio controller is disposed');
  if(this._active)throw Error('Audio session is already active');
  if(!Number.isInteger(silenceSeconds)||silenceSeconds<1||silenceSeconds>300)throw Error('Use 1–300 seconds of silence');
  const epoch=++this._epoch;this._active=true;this._reason=null;this._remote=null;this._silenceSeconds=silenceSeconds;
  this._lifetimeDeadline=this.now()+this.maxLifetimeMs;this._listening(epoch);this._busyEpoch=epoch;this._emit();
  try{
   const created=await this.request('voice/sessions','POST',{silence_seconds:silenceSeconds});
   if(!this._current(epoch)){this._bestEffort('cancel',created);return this.snapshot;}
   if(!created||created.state!=='idle'||typeof created.id!=='string'||!Number.isInteger(created.revision))throw Error('Invalid audio-session creation response');
   this._remote={...created};
   const activated=await this.request('voice/sessions/'+created.id+'/events','POST',{event_id:this.eventId(),revision:created.revision,action:'activate'});
   if(this._accept(activated,epoch)){
    this._listening(epoch);await this._acquire(epoch);this._schedulePoll(epoch);
   }
   return this.snapshot;
  }catch(error){if(this._current(epoch))this._shutdown('start_error','cancel');throw error;}
  finally{if(this._busyEpoch===epoch)this._busyEpoch=null;}
 }
 async _event(action){
  if(!this._active||!this._remote)throw Error('Audio session is not active');
  const epoch=this._epoch;
  if(this._busyEpoch===epoch)throw Error('An audio transition is already pending');
  this._busyEpoch=epoch;
  if(['process','speak'].includes(action)){this._releaseMic();this._phase(epoch);}
  if(action==='interrupt')this._stopPlayback();
  try{
   const snapshot=await this.request('voice/sessions/'+this._remote.id+'/events','POST',{event_id:this.eventId(),revision:this._remote.revision,action});
   if(this._accept(snapshot,epoch)){
    if(snapshot.state==='listening'){this._listening(epoch);await this._acquire(epoch);}
    else this._phase(epoch);
   }
   return this.snapshot;
  }catch(error){if(this._current(epoch))this._shutdown('event_error','cancel');throw error;}
  finally{if(this._busyEpoch===epoch)this._busyEpoch=null;}
 }
 activity(){return this._event('activity');}
 process(){return this._event('process');}
 speak(){return this._event('speak');}
 complete(){return this._event('complete');}
 resume(){return this._event('resume');}
 interrupt(){return this._event('interrupt');}
}
if(typeof module!=='undefined'&&module.exports)module.exports=JarvisAudioSession;
if(root)root.JarvisAudioSession=JarvisAudioSession;
})(typeof window!=='undefined'?window:null);

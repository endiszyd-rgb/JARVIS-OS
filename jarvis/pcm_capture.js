/* Local PCM capture and energy segmentation; no model, wake word or recognition. */
(function(root){
'use strict';
const RATE=16000, FRAME=320, MAX_SECONDS=30;
function finite(value,name){if(!Number.isFinite(value))throw Error('Invalid '+name);return value;}
function pcmWav(samples){
 if(!(samples instanceof Float32Array)||samples.length<1||samples.length>RATE*MAX_SECONDS)throw Error('Use 1–30 seconds of mono PCM');
 const buffer=new ArrayBuffer(44+samples.length*2),view=new DataView(buffer);
 function ascii(offset,text){for(let i=0;i<text.length;i++)view.setUint8(offset+i,text.charCodeAt(i));}
 ascii(0,'RIFF');view.setUint32(4,buffer.byteLength-8,true);ascii(8,'WAVE');ascii(12,'fmt ');view.setUint32(16,16,true);
 view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,RATE,true);view.setUint32(28,RATE*2,true);
 view.setUint16(32,2,true);view.setUint16(34,16,true);ascii(36,'data');view.setUint32(40,samples.length*2,true);
 for(let i=0;i<samples.length;i++){const value=Math.max(-1,Math.min(1,finite(samples[i],'PCM sample')));view.setInt16(44+i*2,Math.round(value*(value<0?32768:32767)),true);}
 return buffer;
}
class StreamingResampler{
 // Area-average rate conversion: each input sample is a constant-width bin.
 // Fractional bin coverage is retained across chunks; no duration drift or
 // chunk-boundary resets. This is a basic box filter, not a studio resampler.
 constructor(inputRate){
  if(!Number.isInteger(inputRate)||inputRate<8000||inputRate>192000)throw Error('Unsupported capture sample rate');
  this.ratio=inputRate/RATE;this.fill=0;this.sum=0;
 }
 push(input){
  if(!(input instanceof Float32Array)||input.length>8192)throw Error('Invalid bounded PCM block');
  const output=[];
  for(const raw of input){
   const value=Math.max(-1,Math.min(1,finite(raw,'PCM sample')));let remaining=1;
   while(remaining>1e-10){const amount=Math.min(remaining,this.ratio-this.fill);this.sum+=value*amount;this.fill+=amount;remaining-=amount;
    if(this.fill>=this.ratio-1e-10){output.push(this.sum/this.ratio);this.fill=0;this.sum=0;}
   }
  }
  return new Float32Array(output);
 }
}
class EnergySegmenter{
 constructor(options={}){
  this.threshold=options.threshold??0.015;
  const minSpeechMs=options.minSpeechMs??160,endSilenceMs=options.endSilenceMs??700,maxSeconds=options.maxUtteranceSeconds??20,preRollMs=options.preRollMs??200,activityMs=options.activityIntervalMs??1000;
  if(!Number.isFinite(this.threshold)||this.threshold<=0||this.threshold>1||!Number.isFinite(minSpeechMs)||minSpeechMs<20||minSpeechMs>2000||!Number.isFinite(endSilenceMs)||endSilenceMs<100||endSilenceMs>3000||!Number.isFinite(maxSeconds)||maxSeconds<1||maxSeconds>MAX_SECONDS||minSpeechMs>maxSeconds*1000||!Number.isFinite(preRollMs)||preRollMs<0||preRollMs>500||!Number.isFinite(activityMs)||activityMs<100||activityMs>10000)throw Error('Invalid energy segmentation limits');
  this.minSpeech=Math.ceil(minSpeechMs*RATE/1000);this.endSilence=Math.ceil(endSilenceMs*RATE/1000);this.maxSamples=Math.floor(maxSeconds*RATE);this.preFrames=Math.ceil(preRollMs*RATE/1000/FRAME);this.activitySamples=Math.ceil(activityMs*RATE/1000);
  this.onSpeechActivity=options.onSpeechActivity||(()=>{});this.onUtterance=options.onUtterance||(()=>{});
  this._closed=false;this._pending=new Float32Array(FRAME);this._pendingSize=0;this._pre=[];this._chunks=[];this._size=0;this._speech=0;this._silence=0;this._clock=0;this._lastActivity=-Infinity;
 }
 get bufferedSamples(){return this._size+this._pre.length*FRAME+this._pendingSize;}
 close(){this._closed=true;this._chunks=[];this._pre=[];this._pendingSize=this._size=0;}
 push(samples){
  if(this._closed)return;
  if(!(samples instanceof Float32Array)||samples.length>8192)throw Error('Invalid bounded 16kHz PCM block');
  for(const sample of samples){
   if(this._closed)break;
   this._pending[this._pendingSize++]=Math.max(-1,Math.min(1,finite(sample,'PCM sample')));
   if(this._pendingSize===FRAME){const frame=this._pending.slice();this._pendingSize=0;this._frame(frame);}
  }
 }
 _frame(frame){
  let square=0;for(const sample of frame)square+=sample*sample;
  const rms=Math.sqrt(square/FRAME),voiced=rms>=this.threshold;this._clock+=FRAME;
  if(!this._chunks.length&&!voiced){if(this.preFrames){this._pre.push(frame);while(this._pre.length>this.preFrames)this._pre.shift();}return;}
  if(!this._chunks.length){this._chunks=this._pre;this._pre=[];this._size=this._chunks.length*FRAME;this._speech=this._silence=0;}
  const remaining=this.maxSamples-this._size;
  if(remaining>0){this._chunks.push(remaining<FRAME?frame.slice(0,remaining):frame);this._size+=Math.min(remaining,FRAME);}
  if(voiced){this._speech+=FRAME;this._silence=0;if(this._speech>=this.minSpeech&&this._clock-this._lastActivity>=this.activitySamples){this._lastActivity=this._clock;this.onSpeechActivity({rms,seconds:this._clock/RATE});}}
  else this._silence+=FRAME;
  if(this._silence>=this.endSilence||this._size>=this.maxSamples)this._finish(this._size>=this.maxSamples?'limit':'silence');
 }
 _finish(reason){
  const chunks=this._chunks,size=this._size,speech=this._speech;
  this._chunks=[];this._size=this._speech=this._silence=0;
  if(speech<this.minSpeech)return;
  const samples=new Float32Array(size);let offset=0;for(const chunk of chunks){samples.set(chunk,offset);offset+=chunk.length;}
  this.onUtterance(pcmWav(samples),{reason,durationSeconds:size/RATE,speechSeconds:speech/RATE});
 }
}
class JarvisPcmCapture{
 constructor(options={}){
  this.options=options;this.onError=options.onError||(()=>{});this._epoch=0;this._context=null;this._source=null;this._node=null;this._gain=null;this._segmenter=null;this._resampler=null;this._active=false;
  this.Context=options.AudioContext||(root&&(root.AudioContext||root.webkitAudioContext));this.Node=options.AudioWorkletNode||(root&&root.AudioWorkletNode);
 }
 get active(){return this._active;}
 _fail(error,epoch){if(this._epoch!==epoch)return;this.close();try{this.onError(error instanceof Error?error:Error('PCM capture failed'));}catch(_){}}
 _callback(name,args,epoch){
  try{const result=this.options[name]?.(...args);if(result&&typeof result.then==='function')result.catch(error=>this._fail(error,epoch));}
  catch(error){this._fail(error,epoch);}
 }
 async start(stream){
  if(this._context)throw Error('PCM capture is already started');
  if(!stream||typeof stream.getAudioTracks!=='function'||!stream.getAudioTracks().length)throw Error('Supply an activated audio MediaStream');
  if(typeof this.Context!=='function'||typeof this.Node!=='function')throw Error('AudioWorklet is required for microphone capture');
  const epoch=++this._epoch;let context;
  try{
   context=new this.Context();this._context=context;
   if(!context.audioWorklet||typeof context.audioWorklet.addModule!=='function')throw Error('AudioWorklet is unavailable');
   this._resampler=new StreamingResampler(context.sampleRate);
   this._segmenter=new EnergySegmenter({...this.options,onSpeechActivity:(...args)=>this._callback('onSpeechActivity',args,epoch),onUtterance:(...args)=>this._callback('onUtterance',args,epoch)});
   await context.audioWorklet.addModule('/ui/pcm_worklet.js');
   if(this._epoch!==epoch)return false;
   const source=context.createMediaStreamSource(stream),node=new this.Node(context,'jarvis-pcm-capture',{numberOfInputs:1,numberOfOutputs:1,outputChannelCount:[1],channelCount:1,channelCountMode:'explicit'}),gain=context.createGain();
   this._source=source;this._node=node;this._gain=gain;gain.gain.value=0;
   node.port.onmessage=event=>{
    if(this._epoch!==epoch)return;
    const data=event.data;
    try{
     if(data?.type==='error')throw Error('AudioWorklet capture failed');
     if(!this._active)return;
     if(data?.type!=='samples'||!(data.samples instanceof Float32Array)||data.samples.length<1||data.samples.length>2048||!Number.isInteger(data.sequence)||data.rate!==context.sampleRate)throw Error('Invalid AudioWorklet PCM message');
     if(data.droppedSamples!==0)throw Error('Audio capture overrun; the incomplete utterance was discarded');
     this._segmenter.push(this._resampler.push(data.samples));
    }catch(error){this._fail(error,epoch);}
    finally{try{node.port.postMessage({type:'ack',sequence:data?.sequence});}catch(_){}}
   };
   node.onprocessorerror=()=>this._fail(Error('AudioWorklet processor stopped'),epoch);
   source.connect(node);node.connect(gain);gain.connect(context.destination);
   await context.resume();
   if(this._epoch!==epoch)return false;
   if(context.state!=='running')throw Error('AudioContext is not running; activate audio in a supported browser');
   this._active=true;
   context.onstatechange=()=>{if(this._epoch===epoch&&context.state!=='running')this._fail(Error('AudioContext stopped or was suspended'),epoch);};
   return true;
  }catch(error){if(this._epoch===epoch)this.close();throw error;}
 }
 close(){
  this._epoch++;this._active=false;
  if(this._segmenter)this._segmenter.close();this._segmenter=this._resampler=null;
  const source=this._source,node=this._node,gain=this._gain,context=this._context;this._context=this._source=this._node=this._gain=null;
  if(node){node.port.onmessage=null;node.onprocessorerror=null;try{node.port.postMessage({type:'stop'});}catch(_){}try{node.port.close();}catch(_){}}
  for(const item of [source,node,gain])if(item){try{item.disconnect();}catch(_){}}
  if(context){context.onstatechange=null;try{Promise.resolve(context.close()).catch(()=>{});}catch(_){}}
 }
}
const exports={JarvisPcmCapture,EnergySegmenter,StreamingResampler,pcmWav,RATE};
if(typeof module!=='undefined'&&module.exports)module.exports=exports;
if(root)root.JarvisPcmCapture=JarvisPcmCapture;
})(typeof window!=='undefined'?window:null);

/* Deterministic PCM/energy/worklet/resource checks; no browser or hardware. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {JarvisPcmCapture,StreamingResampler,EnergySegmenter,pcmWav}=require('../jarvis/pcm_capture.js');
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
function deferred(){let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve};}
function text(view,start,length){return String.fromCharCode(...new Uint8Array(view.buffer,start,length));}
function push(segmenter,samples){for(let offset=0;offset<samples.length;offset+=4096)segmenter.push(samples.subarray(offset,offset+4096));}
function tone(rate,seconds,hz=440,amplitude=0.5){return Float32Array.from({length:Math.floor(rate*seconds)},(_,i)=>Math.sin(2*Math.PI*hz*i/rate)*amplitude);}
function combine(blocks){const size=blocks.reduce((sum,b)=>sum+b.length,0),out=new Float32Array(size);let offset=0;for(const b of blocks){out.set(b,offset);offset+=b.length;}return out;}
function resample(input,rate,chunk=2048){const r=new StreamingResampler(rate),out=[];for(let i=0;i<input.length;i+=chunk)out.push(r.push(input.subarray(i,i+chunk)));return combine(out);}
function wavHeadersAndBounds(){
 const buffer=pcmWav(new Float32Array([-1,-0.5,0,0.5,1,2])),view=new DataView(buffer);
 assert.equal(text(view,0,4),'RIFF');assert.equal(text(view,8,4),'WAVE');assert.equal(text(view,12,4),'fmt ');assert.equal(text(view,36,4),'data');
 assert.equal(view.getUint32(4,true),buffer.byteLength-8);assert.equal(view.getUint16(20,true),1);assert.equal(view.getUint16(22,true),1);assert.equal(view.getUint32(24,true),16000);assert.equal(view.getUint32(28,true),32000);assert.equal(view.getUint16(34,true),16);assert.equal(view.getUint32(40,true),12);
 assert.deepEqual(Array.from({length:6},(_,i)=>view.getInt16(44+i*2,true)),[-32768,-16384,0,16384,32767,32767]);
 assert.throws(()=>pcmWav(new Float32Array()),/1–30/);assert.throws(()=>pcmWav(new Float32Array(16000*30+1)),/1–30/);assert.throws(()=>pcmWav(new Float32Array([NaN])),/Invalid/);
}
function resampleDurationFrequencyAndChunkBoundaries(){
 for(const rate of [44100,48000]){
  const input=tone(rate,1),output=resample(input,rate);
  assert.equal(output.length,16000);let crossings=0,energy=0;
  for(let i=1;i<output.length;i++){if(output[i-1]<=0&&output[i]>0)crossings++;energy+=output[i]*output[i];}
  assert.ok(Math.abs(crossings-440)<=1);assert.ok(Math.sqrt(energy/output.length)>0.34&&Math.sqrt(energy/output.length)<0.36);
  assert.deepEqual(output,resample(input,rate,127));
 }
 const r=new StreamingResampler(8000);assert.equal(r.push(new Float32Array([0.25,-0.25])).length,4);
 assert.throws(()=>new StreamingResampler(1),/Unsupported/);assert.throws(()=>r.push(new Float32Array([Infinity])),/Invalid/);
}
function noiseDoesNotEmitOrGrow(){
 let emitted=0,activities=0;const s=new EnergySegmenter({onUtterance:()=>emitted++,onSpeechActivity:()=>activities++});
 for(let i=0;i<1000;i++)s.push(new Float32Array(320));
 assert.equal(emitted,0);assert.equal(activities,0);assert.ok(s.bufferedSamples<=16000*0.5+320);
 push(s,tone(16000,0.04));push(s,new Float32Array(16000));assert.equal(emitted,0);
 assert.throws(()=>s.push(new Float32Array([NaN])),/Invalid/);
}
function speechEndsAfterSilenceAndActivityIsThrottled(){
 const utterances=[],activities=[];const s=new EnergySegmenter({onUtterance:(wav,meta)=>utterances.push({wav,meta}),onSpeechActivity:x=>activities.push(x)});
 push(s,new Float32Array(16000/2));push(s,tone(16000,1.5));push(s,new Float32Array(16000));
 assert.equal(utterances.length,1);assert.equal(utterances[0].meta.reason,'silence');assert.ok(utterances[0].meta.durationSeconds>=2.3&&utterances[0].meta.durationSeconds<=2.5);
 assert.equal(activities.length,2);assert.ok(activities[1].seconds-activities[0].seconds>=1-1e-9);
 const view=new DataView(utterances[0].wav);assert.equal(view.getUint32(24,true),16000);assert.equal(utterances[0].wav.byteLength,44+utterances[0].meta.durationSeconds*32000);
}
function maximumAndCloseDiscard(){
 const utterances=[];const s=new EnergySegmenter({maxUtteranceSeconds:1,onUtterance:(wav,meta)=>utterances.push({wav,meta})});
 push(s,tone(16000,1.5));assert.equal(utterances.length,1);assert.equal(utterances[0].meta.reason,'limit');assert.equal(utterances[0].wav.byteLength,32044);
 s.close();push(s,new Float32Array(16000));assert.equal(utterances.length,1);assert.equal(s.bufferedSamples,0);
 assert.throws(()=>new EnergySegmenter({maxUtteranceSeconds:31}),/Invalid/);
}
function resources(options={}){
 const contexts=[],nodes=[];
 class GraphNode{constructor(){this.disconnects=0;this.connections=[];}connect(n){this.connections.push(n);}disconnect(){this.disconnects++;}}
 class Context{
  constructor(){this.state='running';this.sampleRate=48000;this.destination={};this.closed=0;this.sources=[];this.gains=[];this.audioWorklet={addModule:async path=>{assert.equal(path,'/ui/pcm_worklet.js');if(options.module)await options.module.promise;}};contexts.push(this);}
  createMediaStreamSource(stream){assert.equal(stream,media);const source=new GraphNode();this.sources.push(source);return source;}
  createGain(){const gain=new GraphNode();gain.gain={value:1};this.gains.push(gain);return gain;}
  async resume(){if(options.suspended)this.state='suspended';if(options.resume)await options.resume.promise;}
  async close(){this.closed++;}
 }
 class Node extends GraphNode{
  constructor(_context,name){super();assert.equal(name,'jarvis-pcm-capture');this.port={messages:[],closed:0,onmessage:null,postMessage(message){this.messages.push(message);},close(){this.closed++;}};nodes.push(this);}
 }
 const errors=[],waves=[],media={getAudioTracks:()=>[{}]};
 const capture=new JarvisPcmCapture({AudioContext:Context,AudioWorkletNode:Node,onError:e=>errors.push(e),onUtterance:wav=>waves.push(wav)});
 return {capture,contexts,nodes,errors,waves,media};
}
async function resourceCleanupAndNoOwnershipOfStream(){
 const s=resources();assert.equal(s.contexts.length,0);assert.equal(s.capture.active,false);
 await s.capture.start(s.media);const context=s.contexts[0],node=s.nodes[0];assert.equal(s.capture.active,true);assert.equal(context.gains[0].gain.value,0);
 node.port.onmessage({data:{type:'samples',samples:new Float32Array(2048),sequence:1,rate:48000,droppedSamples:0}});
 assert.deepEqual(node.port.messages[0],{type:'ack',sequence:1});
 s.capture.close();assert.equal(s.capture.active,false);assert.equal(context.closed,1);assert.equal(node.disconnects,1);assert.equal(context.sources[0].disconnects,1);assert.equal(context.gains[0].disconnects,1);assert.equal(node.port.onmessage,null);assert.equal(node.port.closed,1);
 s.capture.close();assert.equal(context.closed,1);
}
async function lateSetupCannotConnect(){
 const module=deferred(),s=resources({module});const pending=s.capture.start(s.media);await flush();assert.equal(s.contexts.length,1);
 s.capture.close();module.resolve();assert.equal(await pending,false);assert.equal(s.nodes.length,0);assert.equal(s.contexts[0].closed,1);
 const resume=deferred(),second=resources({resume});const started=second.capture.start(second.media);await flush();second.capture.close();resume.resolve();assert.equal(await started,false);assert.equal(second.contexts[0].sources[0].disconnects,1);
}
async function suspendedContextFailsClosed(){
 const s=resources({suspended:true});await assert.rejects(s.capture.start(s.media),/not running/);assert.equal(s.capture.active,false);assert.equal(s.contexts[0].closed,1);
 const running=resources();await running.capture.start(running.media);running.contexts[0].state='suspended';running.contexts[0].onstatechange();assert.equal(running.capture.active,false);assert.equal(running.errors.length,1);assert.equal(running.contexts[0].closed,1);
}
async function invalidMessageAndOverrunCloseGraph(){
 for(const data of [{type:'samples',samples:new Float32Array(2049),sequence:1,rate:48000,droppedSamples:0},{type:'samples',samples:new Float32Array(2048),sequence:1,rate:48000,droppedSamples:128},{type:'samples',samples:new Float32Array([NaN]),sequence:1,rate:48000,droppedSamples:0}]){
  const s=resources();await s.capture.start(s.media);s.nodes[0].port.onmessage({data});assert.equal(s.capture.active,false);assert.equal(s.errors.length,1);assert.equal(s.contexts[0].closed,1);assert.equal(s.waves.length,0);
 }
 const absent=new JarvisPcmCapture();await assert.rejects(absent.start({getAudioTracks:()=>[]}),/activated/);
 await assert.rejects(absent.start({getAudioTracks:()=>[{}]}),/AudioWorklet/);
}
function workletDownmixSilenceAndBackpressure(){
 let Processor;const posted=[];
 class Base{constructor(){this.port={onmessage:null,postMessage:data=>posted.push(data)};}}
 vm.runInNewContext(fs.readFileSync('jarvis/pcm_worklet.js','utf8'),{AudioWorkletProcessor:Base,sampleRate:48000,Float32Array,Number,Math,registerProcessor:(name,ctor)=>{assert.equal(name,'jarvis-pcm-capture');Processor=ctor;}});
 const processor=new Processor(),left=new Float32Array(128).fill(0.75),right=new Float32Array(128).fill(0.25),out=new Float32Array(128).fill(1);
 for(let i=0;i<16;i++)assert.equal(processor.process([[left,right]],[[out]]),true);
 assert.ok(out.every(x=>x===0));assert.equal(posted.length,1);assert.ok(posted[0].samples.every(x=>x===0.5));assert.equal(posted[0].droppedSamples,0);
 for(let i=0;i<16;i++)processor.process([[left,right]],[[out]]);assert.equal(posted.length,1);assert.equal(processor.size,2048);
 processor.port.onmessage({data:{type:'ack',sequence:1}});processor.process([[left,right]],[[out]]);assert.equal(posted.length,2);assert.equal(posted[1].droppedSamples,0);
 for(let i=0;i<32;i++)processor.process([[left,right]],[[out]]);assert.equal(posted.length,2);assert.ok(processor.dropped>0);
 processor.port.onmessage({data:{type:'ack',sequence:2}});processor.process([[left,right]],[[out]]);assert.equal(posted.length,3);assert.ok(posted[2].droppedSamples>0);
 processor.port.onmessage({data:{type:'stop'}});assert.equal(processor.process([[left]],[[out]]),false);
}
(async()=>{
 const tests=[wavHeadersAndBounds,resampleDurationFrequencyAndChunkBoundaries,noiseDoesNotEmitOrGrow,speechEndsAfterSilenceAndActivityIsThrottled,maximumAndCloseDiscard,resourceCleanupAndNoOwnershipOfStream,lateSetupCannotConnect,suspendedContextFailsClosed,invalidMessageAndOverrunCloseGraph,workletDownmixSilenceAndBackpressure];
 for(const test of tests)await test();console.log(tests.length+' PCM capture checks passed with deterministic samples/worklet/context (no real browser).');
})().catch(error=>{console.error(error);process.exitCode=1;});

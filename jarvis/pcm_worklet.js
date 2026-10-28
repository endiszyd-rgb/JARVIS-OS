/* Bounded mono worklet. One batch in flight plus one buffer; no audible output. */
'use strict';
class JarvisPcmProcessor extends AudioWorkletProcessor{
 constructor(){
  super();this.buffer=new Float32Array(2048);this.size=0;this.sequence=0;this.pending=null;this.dropped=0;this.alive=true;
  this.port.onmessage=event=>{const data=event.data;if(data?.type==='stop'){this.alive=false;this.buffer=null;}else if(data?.type==='ack'&&data.sequence===this.pending)this.pending=null;};
 }
 flush(){
  if(this.pending!==null||this.size!==this.buffer.length)return;
  const samples=this.buffer,sequence=++this.sequence;this.pending=sequence;
  this.port.postMessage({type:'samples',samples,sequence,rate:sampleRate,droppedSamples:this.dropped},[samples.buffer]);
  this.buffer=new Float32Array(2048);this.size=0;this.dropped=0;
 }
 process(inputs,outputs){
  for(const output of outputs)for(const channel of output)channel.fill(0);
  if(!this.alive)return false;
  const channels=inputs[0];if(!channels||!channels.length)return true;
  if(channels.length>8){this.port.postMessage({type:'error'});this.alive=false;return false;}
  const length=channels[0].length;this.flush();
  for(let index=0;index<length;index++){
   if(this.size===this.buffer.length){this.dropped=Math.min(Number.MAX_SAFE_INTEGER,this.dropped+length-index);break;}
   let value=0;for(const channel of channels)value+=channel[index]/channels.length;
   if(!Number.isFinite(value)){this.port.postMessage({type:'error'});this.alive=false;return false;}
   this.buffer[this.size++]=Math.max(-1,Math.min(1,value));this.flush();
  }
  return true;
 }
}
registerProcessor('jarvis-pcm-capture',JarvisPcmProcessor);

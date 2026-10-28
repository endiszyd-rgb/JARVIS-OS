// Voice panel defaults, review, request boundaries and abort cleanup (controlled DOM).
const assert=require('node:assert/strict');
const mount=require('../jarvis/voice_panel.js');
class Element{
 constructor(tag='div',text=''){this.tag=tag;this.children=[];this.textContent=text;this.value='';this.checked=false;this.hidden=false;}
 append(...n){this.children.push(...n);}
 replaceChildren(...n){this.children=n;}
 setAttribute(){}
 get firstChild(){return this.children[0];}
 removeChild(node){this.children.splice(this.children.indexOf(node),1);}
}
const all=n=>[n,...n.children.flatMap(all)];
function setup(enabled=true){
 const container=new Element(),errors=[],calls=[],instances=[];
 const el=(tag,text)=>new Element(tag,text),card=(title,text)=>{const n=el('article');n.append(el('h3',title),el('p',text));return n;};
 const button=(text,fn)=>{const n=el('button',text);n.onclick=async()=>{try{await fn();}catch(e){errors.push(e);}};return n;};
 class Conversation{
  constructor(options){this.options=options;this.active=false;instances.push(this);}
  async start(silence){assert.equal(silence,30);this.active=true;this.options.onState({active:true,stage:'listening'});}
  stop(){this.active=false;this.options.onState({active:false,stage:'stopped'});}
  cancel(){this.stop();}
  dispose(){this.disposed=true;this.stop();}
  interrupt(){this.interrupted=true;}
 }
 const panel=mount(container,{el,card,button,api:async()=>{},getKey:()=> 'owner-test-key',voiceStatus:{enabled,stt_configured:true,tts_configured:true},catalog:{models:[{provider:'demo',name:'demo'}],default_provider:'demo'},Conversation,
  fetch:async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>url.endsWith('/chat')?{reply:'OK',session_id:'voice-1'}:{text:'Transkrypcja'},blob:async()=>({size:44})};},URL:{createObjectURL:()=> 'blob:test',revokeObjectURL:()=>{}},stopPlayback:()=>{}});
 return {container,panel,errors,calls,instances,button:text=>all(container).find(n=>n.tag==='button'&&n.textContent===text)};
}
(async()=>{
 const disabled=setup(false);await disabled.button('Rozpocznij rozmowę głosową').onclick();assert.equal(disabled.instances.length,0);assert.ok(disabled.errors[0].message.includes('skonfiguruj'));
 const s=setup();assert.equal(s.instances.length,0);await s.button('Rozpocznij rozmowę głosową').onclick();
 const instance=s.instances[0];assert.equal(typeof instance.options.reviewTranscript,'function');
 const abort=new AbortController();const pending=instance.options.reviewTranscript('sprawdź mnie',abort.signal);
 const draft=all(s.container).find(n=>n.tag==='textarea');draft.value='Poprawiony tekst';
 await s.button('Wyślij tekst').onclick();assert.equal(await pending,'Poprawiony tekst');
 const cancelled=instance.options.reviewTranscript('pomijam',abort.signal);await s.button('Pomiń wypowiedź').onclick();assert.equal(await cancelled,null);
 const signal=new AbortController();const aborted=instance.options.reviewTranscript('anulowany',signal.signal);signal.abort();await assert.rejects(aborted,/Anulowano/);
 await instance.options.chat('ustaw imię Robert',null,abort.signal);
 let sent=s.calls.at(-1);const body=JSON.parse(sent.options.body);
 assert.equal(body.input_mode,'voice');assert.equal(body.do_not_remember,true);assert.equal(body.include_workshop_summary,undefined);assert.equal(body.session_id,undefined);assert.equal(sent.options.headers['X-Jarvis-Key'],'owner-test-key');
 await instance.options.chat('ciąg dalszy','voice-1',abort.signal);assert.equal(JSON.parse(s.calls.at(-1).options.body).session_id,'voice-1');
 await instance.options.transcribe(new ArrayBuffer(44),abort.signal);assert.equal(s.calls.at(-1).options.headers['Content-Type'],'audio/wav');
 for(let i=0;i<55;i++)instance.options.onReply({reply:'<script>unsafe()</script>',ai_generated:false},{truncated:false});
 assert.ok(all(s.container).some(n=>n.textContent==='DEMO: <script>unsafe()</script>'));
 assert.ok(!all(s.container).some(n=>n.tag==='script'));
 const review=all(s.container).find(n=>n.id==='voice-review');assert.equal(review.checked,true);
 instance.stop();review.checked=false;await s.button('Rozpocznij rozmowę głosową').onclick();assert.equal(s.instances[1].options.reviewTranscript,undefined);
 s.panel.dispose();assert.equal(s.instances[1].disposed,true);assert.equal(s.errors.length,0);
 console.log('Voice panel review/default/request/isolation/cleanup checks passed (controlled DOM/API).');
})().catch(error=>{console.error(error);process.exitCode=1;});

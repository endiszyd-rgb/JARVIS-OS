// App wiring test; microphone controller is a spy, no real browser/hardware.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(tag='div'){this.tag=tag;this.children=[];this.value='';this.textContent='';}
 append(...n){this.children.push(...n);}
 replaceChildren(...n){this.children=n;}
 setAttribute(){}
 querySelectorAll(){return [];}
}
const all=n=>[n,...n.children.flatMap(all)];
const nodes=Object.fromEntries(['#content','#error','#key','#connect','#logout','#connection'].map(k=>[k,new Element()]));
const controllers=[],events={};
class Controller{
 constructor(options){this.options=options;this.started=0;this.disposed=false;controllers.push(this);}
 async start(seconds){this.started++;assert.equal(seconds,30);this.options.onState({active:true,mic_active:true});}
 activity(){}
 stop(){this.options.onState({active:false,local_reason:'ended'});}
 cancel(){this.options.onState({active:false,local_reason:'cancelled'});}
 dispose(){this.disposed=true;this.options.stopPlayback();}
}
const context=vm.createContext({document:{createElement:t=>new Element(t),querySelector:s=>nodes[s],querySelectorAll:()=>[]},
 window:{mountJarvisVoicePanel:(container,options)=>{const controller=new Controller({onState:s=>container.append(new Element()),stopPlayback:options.stopPlayback});const start=options.button('Rozpocznij rozmowę głosową',async()=>controller.start(30));container.append(start);return controller;},addEventListener:(event,fn)=>events[event]=fn},
 fetch:async url=>({ok:true,json:async()=>url==='/api/status'?{counts:{}}:{enabled:false}}),console});
vm.runInContext(fs.readFileSync('jarvis/app.js','utf8'),context);
const button=text=>all(nodes['#content']).find(n=>n.tag==='button'&&n.textContent===text);
(async()=>{
 await vm.runInContext("view='voice';render()",context);
 assert.equal(controllers.length,1);assert.equal(controllers[0].started,0);
 await button('Rozpocznij rozmowę głosową').onclick();
 assert.equal(controllers[0].started,1);

 await vm.runInContext("view='overview';render()",context);assert.equal(controllers[0].disposed,true);
 await vm.runInContext("view='voice';render()",context);
 nodes['#logout'].onclick();assert.equal(controllers[1].disposed,true);
 await vm.runInContext("view='voice';render()",context);
 events.pagehide();assert.equal(controllers[2].disposed,true);
 assert.equal(nodes['#error'].textContent,'');
 console.log('Voice view start/navigation/logout/pagehide controlled behavior passed (no browser).');
})().catch(e=>{console.error(e);process.exitCode=1;});

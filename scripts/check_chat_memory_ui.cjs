// Private chat opt-out payload and result display, using controlled DOM/API.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(tag='div'){this.tag=tag;this.children=[];this.value='';this.textContent='';this.checked=false;}
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(...nodes){this.children=nodes;}
 setAttribute(){}
 get options(){return this.children;}
 querySelectorAll(selector){return all(this).slice(1).filter(n=>selector.split(',').includes(n.tag));}
}
function all(n){return [n,...n.children.flatMap(all)];}
const nodes=Object.fromEntries(['#content','#error','#key','#connect','#logout','#connection'].map(k=>[k,new Element()]));
const calls=[];
const context=vm.createContext({document:{createElement:t=>new Element(t),querySelector:s=>nodes[s],querySelectorAll:()=>[]},
 window:{},fetch:async(url,options)=>{
  const body=options.body?JSON.parse(options.body):null;calls.push({url,body});let data;
  if(url==='/api/chat/sessions')data=[];
  else if(url==='/api/models')data={models:[{provider:'demo',name:'demo'}],default_provider:'demo'};
  else if(url==='/api/chat'){assert.equal(body.do_not_remember,true);data={session_id:'chat-1',reply:'OK',memory_capture:{status:'request_excluded',saved:0}};}
  else if(url==='/api/chat/sessions/chat-1')data={id:'chat-1',title:'Rozmowa',provider:'demo',model_name:'demo',message_count:0};
  else if(url.startsWith('/api/chat/sessions/chat-1/messages'))data=[];
  else throw Error('Unexpected request '+url);
  return {ok:true,json:async()=>data};
 },console});
vm.runInContext(fs.readFileSync('jarvis/app.js','utf8'),context);
(async()=>{
 await vm.runInContext("view='chat';render()",context);
 const formNodes=all(nodes['#content']);
 const optout=formNodes.find(n=>n.id==='do-not-remember');assert.ok(optout);optout.checked=true;
 const input=formNodes.find(n=>n.tag==='textarea');input.value='Preferuję krótkie odpowiedzi.';
 await formNodes.find(n=>n.tag==='button'&&n.textContent==='Wyślij').onclick();
 assert.ok(calls.some(c=>c.url==='/api/chat'&&c.body.do_not_remember===true));
 assert.ok(all(nodes['#content']).some(n=>n.textContent.includes('wyłączona z automatycznej pamięci')));
 assert.equal(nodes['#error'].textContent,'');
 console.log('Chat memory opt-out controlled DOM/API behavior passed (no browser).');
})().catch(e=>{console.error(e);process.exitCode=1;});

// Controlled DOM/API checks for separate transport owner and caller channels.
'use strict';
const assert=require('node:assert/strict');
const mount=require('../jarvis/transport_panel.js');
class Element{
 constructor(tag='div',text=''){this.tag=tag;this.children=[];this.textContent=text;this.value='';this.disabled=false;}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=items;}
 setAttribute(name,value){this[name]=value;}
}
const all=node=>[node,...node.children.flatMap(all)];
const contents=node=>all(node).map(n=>n.textContent).join('\n');
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function setup(options={}){
 const container=new Element(),ownerCalls=[],callerCalls=[],errors=[];
 let serial=0,callerRevision=0,pendingGreeting=true,callerHook=null,ownerHook=null,removed=false;
 let owner={id:'transport-1',revision:0,state:'reception',attempt_id:null,owner_briefing:null,offer_delivered:false,attempts:0,simulated_cost_units:0,limits:{max_owner_attempts:1,max_cost_units:2},commands:[{id:'greeting',channel:'caller',kind:'say',status:'pending',payload:{text:'Publiczne powitanie'}}]};
 let publicView={id:'transport-1',revision:0,state:'reception',messages:[]};
 const snapshots=()=>({owner:structuredClone(owner),caller:structuredClone(publicView)});
 const el=(tag,text)=>new Element(tag,text),card=(title,text)=>{const n=el('article');n.append(el('h3',title),el('p',text));return n;};
 const button=(text,fn)=>{const n=el('button',text);n.onclick=async()=>{try{await fn();}catch(error){errors.push(error);}};return n;};
 const api=async(path,method='GET',body)=>{
  ownerCalls.push({path,method,body});if(ownerHook){const intercepted=ownerHook(path,method,body);if(intercepted!==undefined)return await intercepted;}
  if(path==='telephony/transport/calls'&&method==='GET')return removed?[]:[structuredClone(owner)];
  if(path==='telephony/transport/calls'&&method==='POST')return {...structuredClone(owner),caller_token:'caller-only-token'};
  if(method==='DELETE'){assert.equal(path,'telephony/transport/calls/transport-1');assert.equal(owner.state,'ended','Only an ended session may be deleted');removed=true;return {deleted:owner.id};}
  if(method==='GET')return structuredClone(owner);
  assert.ok(path.endsWith('/events'));
  if(body.action==='dispatch'){
   owner.revision++;for(const command of owner.commands)command.status='delivered';if(owner.state==='waiting_owner')owner.offer_delivered=true;
   if(pendingGreeting){publicView.messages.push({id:'greeting',text:'Publiczne powitanie'});pendingGreeting=false;}
   else if(owner.state==='connected_lab'){publicView.state='connected_lab';publicView.messages.push({id:'bridge',text:'Połączono laboratoryjnie'});}
  }else if(body.action==='accept'){
   assert.equal(body.attempt_id,'attempt-1');owner.revision++;owner.state='connected_lab';owner.commands.push({id:'bridge',channel:'caller',kind:'bridge',status:'pending',payload:{}});
  }else if(['decline','no_answer','finish'].includes(body.action)){
   owner.revision++;owner.state=body.action==='finish'?'ended':'reception';publicView.state=owner.state;
  }else if(body.action==='rotate_caller_token'){owner.revision++;return {...structuredClone(owner),caller_token:'rotated-caller-only-token'};}
  else throw Error('Unexpected owner action '+body.action);
  publicView.revision=owner.revision;return structuredClone(owner);
 };
 const fetch=async(url,init)=>{
  callerCalls.push({url,init});if(callerHook){const intercepted=callerHook(url,init);if(intercepted!==undefined)return await intercepted;}
  assert.equal(init.headers['X-Jarvis-Key'],undefined);
  assert.ok(['caller-only-token','rotated-caller-only-token'].includes(init.headers['X-Jarvis-Call-Token']));
  assert.ok(url.startsWith('/api/telephony/transport/caller/'));
  if(init.method==='POST'){
   const body=JSON.parse(init.body);assert.ok(!('scenario' in body)&&!('at' in body)&&!('facts' in body));
   assert.equal(body.revision,publicView.revision);
   owner.revision++;
   if(body.action==='turn'){
    owner.state='waiting_owner';owner.offer_delivered=false;owner.attempt_id='attempt-1';owner.owner_briefing={text:'PRIVATE BRIEFING SENTINEL',owner_number:'+48500123456'};owner.attempts=1;owner.simulated_cost_units=1;
    owner.commands.push({id:'briefing',channel:'owner',kind:'briefing',status:'pending',payload:{text:'PRIVATE BRIEFING SENTINEL'}});
    publicView.state='waiting';publicView.messages.push({id:'hold',text:'Proszę poczekać na decyzję.'});
   }else{assert.equal(body.action,'hangup');owner.state=publicView.state='ended';}
   publicView.revision=owner.revision;
  }
  // Deliberately include private extras: the caller UI must ignore unknown fields.
  return {ok:true,status:200,json:async()=>({...structuredClone(publicView),owner_briefing:'PRIVATE BRIEFING SENTINEL',owner_number:'+48500123456'})};
 };
 const panel=mount(container,{api,el,card,button,fetch,eventId:()=> 'event-'+(++serial),...options});
 const byText=text=>all(container).find(n=>n.tag==='button'&&n.textContent===text);
 return {container,panel,ownerCalls,callerCalls,errors,button:byText,snapshots,ownerHook:fn=>{ownerHook=fn;},callerHook:fn=>{callerHook=fn;},ownerCard:container.children[0],callerCard:container.children[1],commandCard:container.children[2]};
}
async function isolationAndFlow(){
 const s=setup();await s.panel.ready;assert.equal(s.callerCalls.length,0);
 await s.button('Utwórz rozmowę transportu').onclick();
 assert.ok(s.callerCalls.length>0);assert.ok(!contents(s.container).includes('caller-only-token'));
 assert.equal(s.button('Przyjmij rozmowę · właściciel').disabled,true);
 await s.button('Dostarcz komendy · symulacja').onclick();assert.ok(contents(s.callerCard).includes('Publiczne powitanie'));
 await s.button('Przykład: pierwsza prośba').onclick();
 const input=all(s.callerCard).find(n=>n.tag==='textarea');assert.equal(input.value,'Proszę o rozmowę z właścicielem.');
 await s.button('Wyślij tekst klienta').onclick();
 assert.equal(s.button('Przyjmij rozmowę · właściciel').disabled,true);
 await s.button('Dostarcz komendy · symulacja').onclick();
 assert.equal(s.button('Przyjmij rozmowę · właściciel').disabled,false);
 assert.ok(contents(s.ownerCard).includes('PRIVATE BRIEFING SENTINEL'));assert.ok(contents(s.commandCard).includes('PRIVATE BRIEFING SENTINEL'));
 assert.ok(!contents(s.callerCard).includes('PRIVATE BRIEFING SENTINEL'));assert.ok(!contents(s.callerCard).includes('+48500123456'));
 assert.equal(s.button('Wyślij tekst klienta').disabled,true);
 await s.button('Przyjmij rozmowę · właściciel').onclick();await s.button('Dostarcz komendy · symulacja').onclick();
 assert.ok(contents(s.callerCard).includes('Połączono laboratoryjnie'));
 const accepted=s.ownerCalls.find(c=>c.body?.action==='accept');assert.equal(accepted.body.attempt_id,'attempt-1');
 assert.ok(s.callerCalls.every(c=>c.init.headers['X-Jarvis-Key']===undefined));assert.ok(s.ownerCalls.every(c=>!c.path.includes('/caller/')));
 s.panel.dispose();assert.ok(!contents(s.container).includes('PRIVATE BRIEFING SENTINEL'));assert.ok(!contents(s.container).includes('+48500123456'));
 assert.equal(input.value,'');assert.equal(s.errors.length,0);
}
async function persistedSessionRequiresRotation(){
 const s=setup({id:'transport-1'});await s.panel.ready;
 assert.equal(s.callerCalls.length,0);assert.ok(contents(s.callerCard).includes('Brak tokenu'));
 await s.button('Odnów token klienta').onclick();assert.equal(s.callerCalls[0].init.headers['X-Jarvis-Call-Token'],'rotated-caller-only-token');
 assert.ok(!contents(s.container).includes('rotated-caller-only-token'));s.panel.dispose();
}
async function staleFetchAfterDispose(){
 const s=setup();await s.panel.ready;await s.button('Utwórz rozmowę transportu').onclick();
 const pending=deferred();let signal;
 s.callerHook((_url,init)=>{signal=init.signal;return pending.promise;});
 const request=s.button('Odśwież transport').onclick();await new Promise(resolve=>setImmediate(resolve));
 assert.ok(signal);s.panel.dispose();assert.equal(signal.aborted,true);
 pending.resolve({ok:true,json:async()=>({id:'transport-1',revision:9,state:'reception',messages:[{id:'late',text:'LATE PUBLIC MESSAGE'}]})});await request;
 assert.ok(!contents(s.callerCard).includes('LATE PUBLIC MESSAGE'));assert.ok(contents(s.callerCard).includes('Kanał klienta zamknięty'));
}
async function errorsDoNotLeakOrRetry(){
 const s=setup();await s.panel.ready;await s.button('Utwórz rozmowę transportu').onclick();
 s.callerHook(async()=>({ok:false,status:403,text:async()=> 'PRIVATE ERROR SENTINEL'}));
 const before=s.callerCalls.length;await s.button('Odśwież transport').onclick();
 assert.equal(s.callerCalls.length,before+1);assert.ok(!contents(s.container).includes('PRIVATE ERROR SENTINEL'));assert.ok(contents(s.callerCard).includes('wygasł'));
 assert.equal(s.button('Odśwież transport').disabled,false);s.panel.dispose();
 const owner=setup();await owner.panel.ready;owner.ownerHook((path,method)=>method==='POST'?Promise.reject(Error('controlled owner failure')):undefined);
 await owner.button('Utwórz rozmowę transportu').onclick();assert.ok(contents(owner.ownerCard).includes('Nie udało się'));assert.equal(owner.button('Utwórz rozmowę transportu').disabled,false);owner.panel.dispose();
}
async function textIsNeverHtml(){
 const s=setup();await s.panel.ready;s.callerHook(async()=>({ok:true,json:async()=>({id:'transport-1',revision:1,state:'reception',messages:[{id:'x',text:'<script>unsafe()</script>'}]})}));
 await s.button('Utwórz rozmowę transportu').onclick();assert.ok(contents(s.callerCard).includes('<script>unsafe()</script>'));assert.ok(!all(s.container).some(n=>n.tag==='script'));s.panel.dispose();
}
async function endedDeletionClearsChannelsAndUpdatesPicker(){
 const s=setup();await s.panel.ready;
 assert.equal(s.button('Usuń zakończony test').disabled,true);
 await s.button('Utwórz rozmowę transportu').onclick();
 assert.equal(s.button('Usuń zakończony test').disabled,true);
 const picker=all(s.ownerCard).find(n=>n.tag==='select');
 const selected=()=>picker.children.find(n=>n.value==='transport-1');
 assert.ok(selected().textContent.endsWith('Recepcja'));
 await s.button('Przykład: pierwsza prośba').onclick();await s.button('Wyślij tekst klienta').onclick();
 assert.ok(selected().textContent.endsWith('Oczekiwanie na właściciela'),'Picker must reflect current state rather than the stale list snapshot');
 assert.ok(contents(s.ownerCard).includes('PRIVATE BRIEFING SENTINEL'));
 await s.button('Zakończ transport · właściciel').onclick();
 assert.ok(selected().textContent.endsWith('Zakończono'));assert.equal(s.button('Usuń zakończony test').disabled,false);
 const text=all(s.callerCard).find(n=>n.tag==='textarea');text.value='UNSENT PRIVATE DRAFT';
 const before=s.callerCalls.length;
 await s.button('Usuń zakończony test').onclick();
 assert.equal(s.ownerCalls.filter(c=>c.method==='DELETE').length,1);
 assert.equal(s.callerCalls.length,before,'Successful deletion must clear caller token before any following refresh');
 assert.equal(picker.value,'');assert.equal(picker.children.length,1);assert.equal(picker.children[0].value,'');
 assert.equal(text.value,'');assert.equal(s.button('Usuń zakończony test').disabled,true);assert.equal(s.button('Wyślij tekst klienta').disabled,true);
 assert.ok(!contents(s.container).includes('PRIVATE BRIEFING SENTINEL'));assert.ok(!contents(s.container).includes('+48500123456'));
 assert.ok(contents(s.callerCard).includes('test usunięto'));
 s.callerHook(()=>{throw Error('Deleted caller token must never be reused');});await s.button('Odśwież transport').onclick();
 assert.equal(s.callerCalls.length,before);assert.equal(s.errors.length,0);s.panel.dispose();
}
(async()=>{for(const test of [isolationAndFlow,persistedSessionRequiresRotation,staleFetchAfterDispose,errorsDoNotLeakOrRetry,textIsNeverHtml,endedDeletionClearsChannelsAndUpdatesPicker])await test();console.log('6 transport panel source-isolation/flow/cleanup/error/deletion checks passed (controlled DOM/API).');})().catch(error=>{console.error(error);process.exitCode=1;});

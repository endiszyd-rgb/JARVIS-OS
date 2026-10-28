// Controlled DOM/API behavior check; no browser or hardware is simulated as real.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
 constructor(tag='div') {this.tag=tag;this.children=[];this.value='';this.textContent='';this.checked=false;}
 append(...children){this.children.push(...children);}
 replaceChildren(...children){this.children=children;}
 setAttribute(){}
}
const elements = Object.fromEntries(['#content','#connect','#logout','#key','#error','#connection'].map(id=>[id,new Element()]));
const requests=[];
let policy={enabled:true,mode:'manual',categories:['projects'],retention_days:null};
let note={id:'note-1',text:'Mam Saab',source:'owner_manual',category:'equipment',revision:3};
const context = vm.createContext({
 document:{querySelector:s=>elements[s],querySelectorAll:()=>[],createElement:tag=>new Element(tag)},
 window:{confirm:()=>true},
 fetch:async (url,options)=>{
  const body=options.body?JSON.parse(options.body):null;requests.push({url,method:options.method,body});
  let data;
  if(url==='/api/memory/policy') {if(body)policy=body.policy;data={revision:7,policy,automatic_extraction_active:false};}
  else if(url==='/api/memory')data=[note];
  else if(url==='/api/memory/note-1'&&options.method==='PUT'){note={...note,text:body.text,revision:4,source:'owner_correction'};data={id:note.id,revision:4};}
  else if(url==='/api/memory/note-1/history') data=[{text:'Mam Saab',revision:3}];
  else if(url==='/api/memory/note-1/origins') data=[{quote:'Używam Windows 11.',session_available:true}];
  else throw Error('Unexpected request: '+url);
  return {ok:true,json:async()=>data};
 },console
});
vm.runInContext(fs.readFileSync('jarvis/app.js','utf8'),context);
function all(node){return [node,...node.children.flatMap(all)];}
function button(text){const b=all(elements['#content']).find(n=>n.tag==='button'&&n.textContent===text);assert.ok(b,text);return b;}
(async()=>{
 await vm.runInContext("view='memory';render()",context);
 assert.ok(all(elements['#content']).some(n=>n.textContent.includes('owner_manual')));
 const textarea=all(elements['#content']).find(n=>n.tag==='textarea'&&n.value==='Mam Saab');
 textarea.value='Mam Opel';await button('Zapisz korektę').onclick();
 assert.deepEqual(requests.find(r=>r.url==='/api/memory/note-1').body,{text:'Mam Opel',category:'equipment',revision:3});
 assert.ok(all(elements['#content']).some(n=>n.textContent.includes('owner_correction')));
 await button('Źródła automatycznego zapisu').onclick();
 assert.ok(all(elements['#content']).some(n=>n.tag==='pre'&&n.textContent.includes('Używam Windows 11.')));
 await button('Historia korekt').onclick();
 assert.ok(all(elements['#content']).some(n=>n.tag==='pre'&&n.textContent.includes('Mam Saab')));
 const enabled=all(elements['#content']).find(n=>n.tag==='input'&&n.type==='checkbox');enabled.checked=false;
 await button('Zapisz zasady pamięci').onclick();
 const saved=requests.find(r=>r.url==='/api/memory/policy'&&r.method==='PUT');
 assert.equal(saved.body.revision,7);assert.equal(saved.body.policy.enabled,false);
 assert.equal(elements['#error'].textContent,'');
 console.log('Memory UI controlled DOM/API behavior passed (no browser).');
})().catch(e=>{console.error(e);process.exitCode=1;});

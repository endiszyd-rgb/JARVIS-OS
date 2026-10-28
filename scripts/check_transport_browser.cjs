/* Actual Chromium check of the local transport UI and strict caller-channel boundary.
 * The fixture uses a temporary database, synthetic schedule/numbers, and no carrier.
 */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const executable=process.env.JARVIS_BROWSER_EXECUTABLE||'/usr/bin/chromium';
const python=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
assert.ok(fs.existsSync(executable),'Set JARVIS_BROWSER_EXECUTABLE to an installed Chromium');
assert.ok(fs.existsSync(python),'Prepare the Python 3.12 .venv before the browser check');
const fixture=spawn(python,[path.join(__dirname,'browser_voice_fixture.py')],{cwd:root,stdio:['ignore','pipe','pipe']});
let browser=null,stderr='',output='';
fixture.stderr.on('data',chunk=>{stderr=(stderr+chunk.toString()).slice(-20000);});
function startup(){return new Promise((resolve,reject)=>{
 const timer=setTimeout(()=>reject(Error('Synthetic fixture startup timeout: '+stderr)),15000);
 fixture.stdout.on('data',chunk=>{output+=chunk.toString();const newline=output.indexOf('\n');if(newline>=0){clearTimeout(timer);try{resolve(JSON.parse(output.slice(0,newline)));}catch(error){reject(error);}}});
 fixture.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+': '+stderr));});
 fixture.once('error',error=>{clearTimeout(timer);reject(error);});
});}
async function cleanup(){
 if(browser){await browser.close();browser=null;}
 if(fixture.exitCode===null&&fixture.signalCode===null){
  fixture.kill('SIGTERM');let timer;
  await Promise.race([new Promise(resolve=>fixture.once('exit',resolve)),new Promise(resolve=>{timer=setTimeout(resolve,5000);})]);clearTimeout(timer);
  if(fixture.exitCode===null&&fixture.signalCode===null){fixture.kill('SIGKILL');await new Promise(resolve=>fixture.once('exit',resolve));}
 }
}
const PUBLIC=['calls_placed','carrier_connected','id','messages','mode','notifications_sent','replayed','revision','state'].sort();
(async()=>{
 const info=await startup(),issues=[],callerRequests=[],publicResponses=[],ownerResponses=[],pending=[],allURLs=[];
 const numbers={owner:'+48500999001',workshop:'+48500999002',caller:'+48500999003'};
 browser=await chromium.launch({executablePath:executable,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1280,height:1050}});
 const authenticated=async(pathname,method='GET',body)=>{
  const result=await context.request.fetch(info.url+pathname,{method,headers:{'X-Jarvis-Key':info.key},...(body?{data:body}:{})});
  assert.ok(result.ok(),method+' '+pathname+' '+result.status());return result.json();
 };
 const currentPolicy=await authenticated('/api/telephony/settings');
 await authenticated('/api/telephony/settings','PUT',{revision:currentPolicy.revision,policy:{
  ...currentPolicy.policy,enabled:true,owner_number:numbers.owner,workshop_number:numbers.workshop,dnd:false,dnd_until:null,exceptions:[],
  weekly:Array.from({length:7},(_,weekday)=>({weekday,windows:[{start:'00:00',end:'24:00'}]}))
 }});
 const page=await context.newPage();
 page.on('pageerror',error=>issues.push(error.message));
 page.on('console',message=>{if(message.type()==='error'&&!message.location().url.endsWith('/favicon.ico'))issues.push(message.text());});
 page.on('request',request=>{
  allURLs.push(request.url());
  if(new URL(request.url()).pathname.startsWith('/api/telephony/transport/caller/'))callerRequests.push({url:request.url(),method:request.method(),headers:request.headers(),body:request.postData()?request.postDataJSON():null});
 });
 page.on('response',response=>{
  const pathname=new URL(response.url()).pathname;
  if(pathname.startsWith('/api/telephony/transport/caller/'))pending.push(response.json().then(body=>publicResponses.push({status:response.status(),body})));
  else if(pathname.startsWith('/api/telephony/transport/calls/'))pending.push(response.json().then(body=>ownerResponses.push(body)));
 });
 await page.goto(info.url,{waitUntil:'networkidle'});
 await page.locator('#key').fill(info.key);await page.getByRole('button',{name:'Połącz',exact:true}).click();
 await page.getByRole('heading',{name:'Tryby integracji',exact:true}).waitFor();
 await page.getByRole('button',{name:'Transport · laboratorium',exact:true}).click();
 const owner=page.getByRole('heading',{name:'Transport · kanał właściciela',exact:true}).locator('..');
 const caller=page.getByRole('heading',{name:'Transport · kanał klienta',exact:true}).locator('..');
 const commands=page.getByRole('heading',{name:'Transport · komendy symulacji',exact:true}).locator('..');
 await owner.waitFor();
 await page.getByRole('textbox',{name:'Numer testowego klienta',exact:true}).fill(numbers.caller);
 const createdPromise=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/telephony/transport/calls'&&response.request().method()==='POST');
 await page.getByRole('button',{name:'Utwórz rozmowę transportu',exact:true}).click();
 const createdResponse=await createdPromise;assert.equal(createdResponse.status(),201);
 const created=await createdResponse.json(),token=created.caller_token;assert.equal(typeof token,'string');assert.ok(token.length>=24);
 const ownerState=state=>owner.getByText(new RegExp('^Stan właściciela: '+state+' · rewizja ')).waitFor();
 const callerState=state=>caller.getByText(new RegExp('^Stan klienta: '+state+' · rewizja ')).waitFor();
 await ownerState('Recepcja');await callerState('Recepcja');
 assert.equal(await page.getByRole('button',{name:'Przyjmij rozmowę · właściciel',exact:true}).isEnabled(),false);
 async function ownerEvent(button,action){
  const response=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/telephony/transport/calls/'+created.id+'/events'&&response.request().method()==='POST'&&response.request().postDataJSON().action===action);
  await page.getByRole('button',{name:button,exact:true}).click();const completed=await response;assert.equal(completed.status(),200);return completed.json();
 }
 const dispatch=()=>ownerEvent('Dostarcz komendy · symulacja','dispatch');
 await dispatch();await caller.getByText('Dzień dobry',{exact:false}).waitFor();
 await page.getByRole('button',{name:'Przykład: pierwsza prośba',exact:true}).click();
 assert.equal(await page.getByRole('textbox',{name:'Tekst klienta transportu',exact:true}).inputValue(),'Proszę o rozmowę z właścicielem.');
 await page.getByRole('button',{name:'Wyślij tekst klienta',exact:true}).click();await ownerState('Recepcja');
 assert.equal(await page.getByRole('button',{name:'Przyjmij rozmowę · właściciel',exact:true}).isEnabled(),false);
 await dispatch();
 await page.getByRole('button',{name:'Przykład: ponowienie i odmowa pomocy',exact:true}).click();
 assert.equal(await page.getByRole('textbox',{name:'Tekst klienta transportu',exact:true}).inputValue(),'Ponownie proszę o właściciela i odrzucam pomoc asystenta.');
 await page.getByRole('button',{name:'Wyślij tekst klienta',exact:true}).click();await ownerState('Oczekiwanie na właściciela');
 assert.equal(await page.getByRole('button',{name:'Przyjmij rozmowę · właściciel',exact:true}).isEnabled(),false);
 const offered=await dispatch();assert.equal(offered.offer_delivered,true);assert.ok(offered.owner_briefing);assert.equal(offered.owner_briefing.caller,numbers.caller);
 await owner.getByText(numbers.caller,{exact:false}).waitFor();
 assert.ok(!(await caller.innerText()).includes(numbers.caller));
 assert.ok(!(await caller.innerText()).includes('recent_customer_messages'));
 const accepted=await ownerEvent('Przyjmij rozmowę · właściciel','accept');assert.equal(accepted.state,'bridge_pending');
 const bridged=await dispatch();assert.equal(bridged.state,'bridged_lab');await callerState('Połączono w laboratorium');
 const hungupPromise=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/telephony/transport/caller/'+created.id+'/events'&&response.request().postDataJSON().action==='hangup');
 await page.getByRole('button',{name:'Rozłącz klienta · test',exact:true}).click();assert.equal((await hungupPromise).status(),200);
 await ownerState('Zakończono');await callerState('Zakończono');const ended=await dispatch();assert.equal(ended.state,'ended');
 await caller.getByText('Zakończono połączenie laboratoryjne.',{exact:true}).waitFor();
 await Promise.all(pending);
 assert.ok(callerRequests.length>=8);assert.ok(publicResponses.length>=8);
 for(const request of callerRequests){
  assert.equal(request.headers['x-jarvis-key'],undefined);assert.equal(request.headers['x-jarvis-call-token'],token);
  assert.ok(!request.url.includes(token));
  if(request.body)assert.deepEqual(Object.keys(request.body).sort(),request.body.action==='hangup'?['action','event_id','revision']:['action','event_id','revision','text']);
 }
 for(const {status,body} of publicResponses){
  assert.equal(status,200);assert.deepEqual(Object.keys(body).sort(),PUBLIC);
  assert.equal(body.mode,'transport_lab');assert.equal(body.carrier_connected,false);assert.equal(body.calls_placed,false);assert.equal(body.notifications_sent,false);
  for(const message of body.messages)assert.deepEqual(Object.keys(message).sort(),['id','text']);
  const serialized=JSON.stringify(body);for(const value of [token,numbers.owner,numbers.workshop,numbers.caller])assert.ok(!serialized.includes(value));
 }
 assert.ok(ownerResponses.some(body=>body.owner_briefing));assert.ok(ownerResponses.every(body=>body.calls_placed===false&&body.carrier_connected===false&&body.notifications_sent===false));
 const secrecy=await page.evaluate(secret=>({dom:document.documentElement.outerHTML.includes(secret),storage:JSON.stringify({...localStorage,...sessionStorage}).includes(secret),url:location.href.includes(secret)}),token);
 assert.deepEqual(secrecy,{dom:false,storage:false,url:false});assert.ok(allURLs.every(url=>!url.includes(token)));
 const fixtureState=await (await context.request.get(info.url+'/browser-fixture/state')).json();assert.equal(fixtureState.stt,0);assert.equal(fixtureState.tts,0);assert.equal(fixtureState.model_requests.length,0);
 const screenshot=process.env.JARVIS_TRANSPORT_SCREENSHOT||path.resolve(root,'../JARVIS-OS-transport-browser.png');await page.screenshot({path:screenshot,fullPage:true});
 await page.setViewportSize({width:390,height:900});
 const mobile=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll('main *')].map(node=>({tag:node.tagName,cls:node.className,right:Math.round(node.getBoundingClientRect().right),width:Math.round(node.getBoundingClientRect().width)})).filter(item=>item.right>innerWidth+1&&item.width>0).slice(0,12)}));
 const mobileScreenshot=path.resolve(root,'../JARVIS-OS-transport-browser-mobile.png');await page.screenshot({path:mobileScreenshot,fullPage:true});
 const removedPromise=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/telephony/transport/calls/'+created.id&&response.request().method()==='DELETE');
 await page.getByRole('button',{name:'Usuń zakończony test',exact:true}).click();assert.equal((await removedPromise).status(),200);
 await caller.getByText('Zakończony test usunięto razem z danymi recepcji i tokenem klienta.',{exact:true}).waitFor();
 await owner.getByText('Utwórz albo wybierz laboratoryjną rozmowę.',{exact:true}).waitFor();
 assert.ok(!(await page.locator('#content').innerText()).includes('recent_customer_messages'));
 assert.ok(!(await page.locator('#content').innerText()).includes(numbers.caller));
 const revoked=await context.request.get(info.url+'/api/telephony/transport/caller/'+created.id,{headers:{'X-Jarvis-Call-Token':token}});assert.equal(revoked.status(),401);
 await page.getByRole('button',{name:'Centrum dowodzenia',exact:true}).click();await page.getByRole('heading',{name:'Tryby integracji',exact:true}).waitFor();
 assert.equal(await page.getByRole('heading',{name:'Transport · kanał klienta',exact:true}).count(),0);
 await page.getByRole('button',{name:'Transport · laboratorium',exact:true}).click();
 await page.getByRole('heading',{name:'Transport · kanał klienta',exact:true}).waitFor();
 assert.ok(!(await page.locator('#content').innerText()).includes(numbers.caller));
 await page.getByRole('button',{name:'Wyloguj',exact:true}).click();assert.equal(await page.locator('#content').evaluate(node=>node.childElementCount),0);
 assert.ok(mobile.document<=mobile.viewport+1,'Mobile overflow: '+JSON.stringify(mobile));
 assert.deepEqual(issues,[]);
 console.log(JSON.stringify({check:'chromium_transport_channels',source:'actual_chromium_temporary_lab_no_carrier',passed:true,caller_requests:callerRequests.length,public_responses:publicResponses.length,public_fields:PUBLIC,mobile,screenshot,mobileScreenshot}));
 await cleanup();
})().catch(async error=>{
 console.error(error);
 try{const page=browser?.contexts()[0]?.pages()[0];if(page){console.error((await page.locator('body').innerText()).slice(-5000));await page.screenshot({path:'/tmp/jarvis-transport-browser-failure.png',fullPage:true});}}catch(_){}
 if(stderr.trim())console.error(stderr);await cleanup();process.exitCode=1;
});

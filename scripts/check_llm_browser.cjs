/* Actual Chromium/Core verification of the cloud-provider UI and wire protocol.
 * Uses disposable data, a synthetic loopback provider and no model inference.
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
assert.ok(fs.existsSync(path.join(root,'frontend','dist','index.html')),'Build frontend before checking conversations');
const fixture=spawn(python,[path.join(__dirname,'browser_llm_fixture.py')],{cwd:root,stdio:['ignore','pipe','pipe']});
let browser=null,stderr='',output='',secrets=[];
fixture.stderr.on('data',chunk=>{stderr=(stderr+chunk.toString()).slice(-12000);});
function sanitized(value){for(const secret of secrets)if(secret)value=value.split(secret).join('[REDACTED]');return value;}
function startup(){return new Promise((resolve,reject)=>{
 const timer=setTimeout(()=>reject(Error('Conversation fixture startup timeout')),15000);
 fixture.stdout.on('data',chunk=>{output+=chunk.toString();const newline=output.indexOf('\n');if(newline>=0){clearTimeout(timer);try{resolve(JSON.parse(output.slice(0,newline)));}catch(error){reject(error);}}});
 fixture.once('exit',code=>{clearTimeout(timer);reject(Error('Conversation fixture exited '+code));});
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
(async()=>{
 const info=await startup(),password='Synthetic-conversation-browser-password-123',requests=[],issues=[],assetFailures=[],foreign=[];
 secrets=[info.key,password,info.provider_secret];
 browser=await chromium.launch({executablePath:executable,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1440,height:1100},reducedMotion:'reduce'});
 const ownerRequest=async(route,method='GET',body,expected=200)=>{
  const response=await context.request.fetch(info.url+route,{method,headers:{'X-Jarvis-Key':info.key},...(body===undefined?{}:{data:body})});
  assert.equal(response.status(),expected,method+' '+route+' unexpected status');return response.json();
 };
 await ownerRequest('/api/v1/security/users','POST',{username:'conversation.owner',password,role:'owner'},201);
 await ownerRequest('/api/v1/security/users','POST',{username:'conversation.observer',password,role:'observer'},201);
 const page=await context.newPage();
 await page.addInitScript(()=>{window.__conversationCsp=[];window.__jarvisXss=false;addEventListener('securitypolicyviolation',event=>window.__conversationCsp.push({directive:event.violatedDirective,blocked:event.blockedURI}));});
 page.on('pageerror',error=>issues.push(error.message));
 page.on('request',request=>{const url=new URL(request.url());if(url.origin!==info.url)foreign.push(url.origin);requests.push({url:url.href,path:url.pathname,method:request.method()});});
 page.on('response',response=>{const url=new URL(response.url());if(url.pathname.startsWith('/control/assets/')&&!response.ok())assetFailures.push({path:url.pathname,status:response.status()});});
 page.on('requestfailed',request=>{const url=new URL(request.url());if(url.pathname.startsWith('/control/assets/'))assetFailures.push({path:url.pathname,status:'failed'});});
 const loginScreen=()=>page.getByRole('heading',{name:'Połącz się z JARVIS OS',exact:true}).waitFor();
 const heading=name=>page.getByRole('heading',{name,exact:true,level:1}).waitFor();
 const requestResponse=(pathname,method='POST')=>page.waitForResponse(response=>new URL(response.url()).pathname===pathname&&response.request().method()===method);
 const secretCheck=async()=>{
  const result=await page.evaluate(values=>{
   const visible=document.documentElement.outerHTML,storage=JSON.stringify({local:{...localStorage},session:{...sessionStorage},cookies:document.cookie});
   return {dom:values.some(value=>visible.includes(value)),storage:values.some(value=>storage.includes(value)),url:values.some(value=>location.href.includes(value))};
  },secrets);
  assert.deepEqual(result,{dom:false,storage:false,url:false});
  assert.ok((await context.cookies()).every(cookie=>!secrets.some(secret=>cookie.value.includes(secret))));
 };
 const openView=async name=>{
  const link=page.getByRole('link',{name,exact:true});
  if(!await link.isVisible())await page.getByRole('button',{name:'Otwórz menu',exact:true}).click();
  await link.click();await heading(name);
 };
 const screenshot=async filename=>{
  // Chromium fullPage can paint off-screen fixed elements into a scrolled capture.
  // Reset scroll without changing focus so the artifact matches the page at its top.
  await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:filename,fullPage:true});
 };
 const keyLogin=async()=>{
  await page.getByRole('button',{name:'Klucz właściciela',exact:true}).click();
  await page.getByLabel('Klucz dostępu',{exact:true}).fill(info.key);
  await page.getByRole('button',{name:'Połącz kluczem',exact:true}).click();await heading('Pulpit');
 };
 const accountLogin=async username=>{
  await page.getByRole('button',{name:'Konto',exact:true}).click();
  await page.getByLabel('Login',{exact:true}).fill(username);await page.getByLabel('Hasło',{exact:true}).fill(password);
  const logged=requestResponse('/api/v1/auth/login');await page.getByRole('button',{name:'Zaloguj się',exact:true}).click();
  const session=await(await logged).json();secrets.push(session.token);await heading('Pulpit');return session;
 };
 await page.goto(info.url+'/control/',{waitUntil:'networkidle'});await loginScreen();await keyLogin();
 await openView('Rozmowa');
 const model='gpt-5.4-mini-2026-03-17';
 await page.getByLabel('Model rozmowy',{exact:true}).selectOption(JSON.stringify({provider:'openai',name:model}));
 await page.getByText('Wiadomości i historia tej sesji trafią do chmury. Rozmowy tekstowe mogą zawierać pamięć osobistą.',{exact:true}).waitFor();
 const initial=await context.request.get(info.provider_origin+'/_fixture_status');assert.equal((await initial.json()).count,0);
 await page.getByLabel('Tytuł nowej rozmowy',{exact:true}).fill('Test dostawcy chmury');
 const creation=requestResponse('/api/v1/chat/sessions');await page.getByRole('button',{name:'Nowa rozmowa',exact:true}).click();
 const session=await(await creation).json();assert.equal(session.provider,'openai');
 await page.getByLabel('Wiadomość',{exact:true}).fill('Syntetyczny test bez płatnej inferencji');
 const generated=requestResponse('/api/v1/chat');await page.getByRole('button',{name:'Wyślij wiadomość',exact:true}).click();
 const reply=await(await generated).json();assert.equal(reply.model,'openai');assert.equal(reply.usage.estimated_cost_usd,'0.000045');
 assert.equal(reply.usage.reserved_cost_usd,'0.304608');assert.equal(reply.usage.billing_verified,false);
 await page.getByText(reply.reply,{exact:true}).waitFor();assert.equal(await page.locator('img[src=x]').count(),0);
 const remote=await(await context.request.get(info.provider_origin+'/_fixture_status')).json();assert.equal(remote.count,1);
 assert.deepEqual(remote.requests,[{path:'/v1/chat/completions',authorized:true,model,max_output:1024,store:false,stream:false,tools_sent:false}]);
 await secretCheck();const desktop=path.resolve(root,'../JARVIS-OS-llm-browser.png');await screenshot(desktop);
 await openView('Ustawienia');await page.getByLabel('Domyślny dostawca',{exact:true}).selectOption('openai');
 await page.getByRole('button',{name:'Podgląd zmiany',exact:true}).click();await page.getByRole('button',{name:'Zatwierdź zmianę',exact:true}).click();
 await page.getByText('Ustawienia zostały zapisane.',{exact:true}).waitFor();
 assert.equal((await ownerRequest('/api/v1/status')).settings.model,'openai');
 await page.setViewportSize({width:390,height:844});
 const menu=page.getByRole('button',{name:'Otwórz menu',exact:true});if(await menu.isVisible())await menu.click();
 await page.getByRole('link',{name:'Rozmowa',exact:true}).click();await heading('Rozmowa');
 await page.getByRole('button',{name:'Test dostawcy chmury',exact:true}).click();await page.getByText(reply.reply,{exact:true}).waitFor();
 const mobile=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));assert.equal(mobile.document,mobile.viewport);
 const mobileScreenshot=path.resolve(root,'../JARVIS-OS-llm-browser-mobile.png');await screenshot(mobileScreenshot);
 await secretCheck();assert.deepEqual(await page.evaluate(()=>window.__conversationCsp),[]);assert.deepEqual(issues,[]);assert.deepEqual(assetFailures,[]);assert.deepEqual(foreign,[]);
 await page.getByRole('button',{name:'Wyloguj',exact:true}).click();await loginScreen();assert.equal(await page.getByText(reply.reply,{exact:true}).count(),0);
 console.log(JSON.stringify({check:'chromium_llm_provider',passed:true,source:'temporary_core_genuine_loopback_synthetic_cloud_no_inference',checks:['configured_cloud_catalog','explicit_model_selection','cloud_context_notice','persisted_cloud_session_reply','preflight_reservation_usage','escaped_reply','cloud_default_settings_approval','privacy_csp_logout'],remote_requests:remote.count,mobile,screenshot:desktop,mobileScreenshot,real_inference:false}));
 await cleanup();
})().catch(async error=>{
 console.error(sanitized(error.stack||String(error)));
 try{const page=browser?.contexts()[0]?.pages()[0];if(page)await page.screenshot({path:'/tmp/jarvis-conversation-browser-failure.png',fullPage:true});}catch(_){}
 if(stderr.trim())console.error(sanitized(stderr));await cleanup();process.exitCode=1;
});

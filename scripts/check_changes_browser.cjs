/* Actual Chromium/Core verification for React conversations, settings and activity.
 * Uses only a disposable local database and DEMO replies; no models or devices.
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
const fixture=spawn(python,[path.join(__dirname,'browser_control_fixture.py')],{cwd:root,stdio:['ignore','pipe','pipe']});
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
 secrets=[info.key,password];
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
 await openView('Zmiany i zgody');
 const baseline=(await ownerRequest('/api/v1/status')).settings;
 const proposed=await ownerRequest('/api/v1/proposals','POST',{kind:'settings',payload:{...baseline,name:'Przegląd zmian'}},201);
 await page.getByRole('button',{name:'Odśwież propozycje',exact:true}).click();
 await page.getByRole('button',{name:'Przejrzyj zatwierdzenie',exact:true}).click();
 assert.deepEqual((await ownerRequest('/api/v1/status')).settings,baseline);
 assert.equal(await page.getByRole('heading',{name:'Potwierdzenie decyzji',exact:true}).evaluate(el=>el===document.activeElement),true);
 await page.getByRole('button',{name:'Potwierdź decyzję',exact:true}).click();
 await page.getByText('Zmiana została zatwierdzona.',{exact:true}).waitFor();
 assert.equal((await ownerRequest('/api/v1/status')).settings.name,'Przegląd zmian');
 await page.getByRole('button',{name:'Przejrzyj cofnięcie',exact:true}).click();
 await page.getByRole('button',{name:'Potwierdź decyzję',exact:true}).click();
 await page.getByText('Zmiana została cofnięta.',{exact:true}).waitFor();assert.deepEqual((await ownerRequest('/api/v1/status')).settings,baseline);
 await ownerRequest('/api/v1/proposals','POST',{kind:'code',payload:{description:'<img src=x onerror="window.__jarvisXss=true"> Opis bez wykonania'}},201);
 await page.getByRole('button',{name:'Odśwież propozycje',exact:true}).click();
 await page.getByRole('button',{name:'Przejrzyj zatwierdzenie',exact:true}).click();
 await page.getByRole('button',{name:'Potwierdź decyzję',exact:true}).click();
 await page.getByText('Opis skierowano do przeglądu. Nie wykonano kodu.',{exact:true}).waitFor();
 assert.equal(await page.locator('img[src=x]').count(),0);
 const screenshotPath=path.resolve(root,'../JARVIS-OS-changes-browser.png');await screenshot(screenshotPath);
 const views=['Pulpit','System','Rozmowa','Pamięć','Ustawienia','Historia działań','Pluginy','AutoLogika','Dom','Urządzenia','Automatyzacje','Telefonia','Powiadomienia','Zmiany i zgody','Bezpieczeństwo','Logi'];
 const structure=[];
 for(const view of views){
  await openView(view);await page.waitForLoadState('networkidle');
  const findings=await page.evaluate(()=>{
   const ids=[...document.querySelectorAll('[id]')].map(el=>el.id);
   const fields=[...document.querySelectorAll('main input,main select,main textarea')].filter(el=>!el.closest('details:not([open])'));
   return {main:document.querySelectorAll('main').length,h1:document.querySelectorAll('h1').length,duplicates:ids.filter((id,i)=>ids.indexOf(id)!==i),unlabelled:fields.filter(el=>!el.labels?.length&&!el.getAttribute('aria-label')&&!el.getAttribute('aria-labelledby')).map(el=>el.id)};
  });assert.deepEqual(findings,{main:1,h1:1,duplicates:[],unlabelled:[]});structure.push({view,...findings});
 }
 await page.setViewportSize({width:390,height:844});
 await page.getByRole('button',{name:'Otwórz menu',exact:true}).click();
 await page.waitForFunction(()=>document.activeElement?.getAttribute('href')==='#/dashboard',null,{timeout:3000});
 await page.keyboard.press('Shift+Tab');assert.equal(await page.getByRole('link',{name:'Dotychczasowy panel',exact:true}).evaluate(el=>el===document.activeElement),true);
 await page.keyboard.press('Escape');assert.equal(await page.getByRole('button',{name:'Otwórz menu',exact:true}).evaluate(el=>el===document.activeElement),true);
 await page.getByRole('button',{name:'Otwórz menu',exact:true}).click();await page.getByRole('link',{name:'Zmiany i zgody',exact:true}).click();await heading('Zmiany i zgody');
 assert.equal(await page.locator('main').evaluate(el=>el===document.activeElement),true);
 const mobile=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));assert.ok(mobile.document<=mobile.viewport+1);
 const mobileScreenshot=path.resolve(root,'../JARVIS-OS-changes-browser-mobile.png');await page.screenshot({path:mobileScreenshot,fullPage:true});
 await secretCheck();assert.deepEqual(await page.evaluate(()=>window.__conversationCsp),[]);assert.deepEqual(issues,[]);assert.deepEqual(assetFailures,[]);assert.deepEqual(foreign,[]);
 await page.getByRole('button',{name:'Wyloguj',exact:true}).click();await loginScreen();
 await accountLogin('conversation.observer');await page.evaluate(()=>{location.hash='#/changes'});await page.getByText('Dostęp właściciela',{exact:true}).waitFor();
 console.log(JSON.stringify({check:'chromium_changes_accessibility',passed:true,source:'actual_chromium_temporary_core',checks:['settings_separate_approval','rollback_actual_settings','code_review_no_execution','plain_text','confirmation_focus','mobile_menu_keyboard_trap_escape_focus','private_route_gate','privacy_csp'],structure,mobile,screenshot:screenshotPath,mobileScreenshot,limitations:'Structural and keyboard checks; not a complete WCAG audit, screen reader or Safari test'}));
 await cleanup();
})().catch(async error=>{
 console.error(sanitized(error.stack||String(error)));
 try{const page=browser?.contexts()[0]?.pages()[0];if(page)await page.screenshot({path:'/tmp/jarvis-conversation-browser-failure.png',fullPage:true});}catch(_){}
 if(stderr.trim())console.error(sanitized(stderr));await cleanup();process.exitCode=1;
});

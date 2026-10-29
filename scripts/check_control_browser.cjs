/* Actual Chromium against the built React UI and temporary Core. No models or devices. */
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
assert.ok(fs.existsSync(path.join(root,'frontend','dist','index.html')),'Build frontend before running this check');
const fixture=spawn(python,[path.join(__dirname,'browser_control_fixture.py')],{cwd:root,stdio:['ignore','pipe','pipe']});
let browser=null,stderr='',output='',secretValues=[];
fixture.stderr.on('data',chunk=>{stderr=(stderr+chunk.toString()).slice(-12000);});
function sanitized(value){for(const secret of secretValues)if(secret)value=value.split(secret).join('[REDACTED]');return value;}
function startup(){return new Promise((resolve,reject)=>{
 const timer=setTimeout(()=>reject(Error('Control fixture startup timeout')),15000);
 fixture.stdout.on('data',chunk=>{output+=chunk.toString();const newline=output.indexOf('\n');if(newline>=0){clearTimeout(timer);try{resolve(JSON.parse(output.slice(0,newline)));}catch(error){reject(error);}}});
 fixture.once('exit',code=>{clearTimeout(timer);reject(Error('Control fixture exited '+code));});
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
 const info=await startup(),password='Synthetic-control-browser-password-123',issues=[],requests=[],foreignRequests=[],assetFailures=[];
 secretValues=[info.key,password,'Synthetic-wrong-password-123'];
 browser=await chromium.launch({executablePath:executable,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 const ownerRequest=async(route,method='GET',body,expected=200)=>{
  const result=await context.request.fetch(info.url+route,{method,headers:{'X-Jarvis-Key':info.key},...(body?{data:body}:{})});
  assert.equal(result.status(),expected,method+' '+route+' unexpected status');return result.json();
 };
 const owner=await ownerRequest('/api/v1/security/users','POST',{username:'browser.owner',password,role:'owner'},201);
 await ownerRequest('/api/v1/security/users','POST',{username:'browser.observer',password,role:'observer'},201);
 await ownerRequest('/api/v1/memory','POST',{text:'Synthetic memory one, never shown as a private body'},201);
 await ownerRequest('/api/v1/memory','POST',{text:'Synthetic memory two'},201);
 const page=await context.newPage();
 await page.addInitScript(()=>{window.__controlCsp=[];addEventListener('securitypolicyviolation',event=>window.__controlCsp.push({directive:event.violatedDirective,blocked:event.blockedURI}));});
 page.on('pageerror',error=>issues.push(error.message));
 page.on('request',request=>{
  const url=new URL(request.url());if(url.origin!==info.url)foreignRequests.push(url.origin);
  requests.push({url:url.href,path:url.pathname,method:request.method()});
 });
 page.on('response',response=>{const url=new URL(response.url());if(url.pathname.startsWith('/control/assets/')&&!response.ok())assetFailures.push({path:url.pathname,status:response.status()});});
 page.on('requestfailed',request=>{const url=new URL(request.url());if(url.pathname.startsWith('/control/assets/'))assetFailures.push({path:url.pathname,status:'failed'});});
 const loginScreen=()=>page.getByRole('heading',{name:'Połącz się z JARVIS OS',exact:true}).waitFor();
 const dashboard=()=>page.getByRole('heading',{name:'Pulpit',exact:true,level:1}).waitFor();
 const secretCheck=async()=>{
  const state=await page.evaluate(secrets=>{
   const dom=document.documentElement.outerHTML,storage=JSON.stringify({local:{...localStorage},session:{...sessionStorage},cookie:document.cookie});
   return {dom:secrets.some(secret=>dom.includes(secret)),storage:secrets.some(secret=>storage.includes(secret)),url:secrets.some(secret=>location.href.includes(secret))};
  },secretValues);
  assert.deepEqual(state,{dom:false,storage:false,url:false},'Credentials must stay out of DOM, URL and web storage');
  assert.ok((await context.cookies()).every(cookie=>!secretValues.some(secret=>cookie.value.includes(secret))),'Credentials must stay out of browser cookies');
 };
 const accountLogin=async username=>{
  await page.getByRole('button',{name:'Konto',exact:true}).click();
  await page.getByLabel('Login',{exact:true}).fill(username);
  await page.getByLabel('Hasło',{exact:true}).fill(password);
  const logged=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/v1/auth/login'&&response.request().method()==='POST'&&response.status()===200);
  await page.getByRole('button',{name:'Zaloguj się',exact:true}).click();
  const session=await (await logged).json();secretValues.push(session.token);
  await dashboard();await secretCheck();return session;
 };
 await page.goto(info.url+'/control/',{waitUntil:'networkidle'});await loginScreen();
 // A failed login cannot leave the entered password or server error body behind.
 await page.getByLabel('Login',{exact:true}).fill('browser.owner');
 await page.getByLabel('Hasło',{exact:true}).fill('Synthetic-wrong-password-123');
 await page.getByRole('button',{name:'Zaloguj się',exact:true}).click();
 await page.getByRole('alert').waitFor();
 assert.equal(await page.getByLabel('Hasło',{exact:true}).inputValue(),'');
 await page.getByRole('button',{name:'Klucz właściciela',exact:true}).click();
 await page.getByLabel('Klucz dostępu',{exact:true}).fill(info.key);
 await page.getByRole('button',{name:'Połącz kluczem',exact:true}).click();await dashboard();
 const memory=page.locator('article').filter({has:page.getByRole('heading',{name:'Pamięć',exact:true})}).locator('.metric-value');
 await memory.waitFor();assert.equal((await memory.innerText()).trim(),'2');
 await secretCheck();
 const system=page.getByRole('link',{name:'System',exact:true});await system.focus();await page.keyboard.press('Enter');
 await page.getByRole('heading',{name:'System',exact:true,level:1}).waitFor();
 assert.equal(await system.getAttribute('aria-current'),'page');
 const legacy=page.getByRole('link',{name:'Dotychczasowy panel',exact:true});
 assert.equal(new URL(await legacy.getAttribute('href'),info.url).pathname,'/');
 await page.getByRole('link',{name:'Pulpit',exact:true}).click();await dashboard();
 const radar=page.getByRole('link',{name:'Otwórz stan rdzenia JARVIS',exact:true});
 assert.equal(await page.locator('.radar-orbit').evaluate(node=>getComputedStyle(node).animationName),'none');
 await radar.focus();await page.keyboard.press('Enter');
 await page.getByRole('heading',{name:'System',exact:true,level:1}).waitFor();
 await page.getByRole('link',{name:'Pulpit',exact:true}).click();await dashboard();
 const desktop=process.env.JARVIS_CONTROL_SCREENSHOT||path.resolve(root,'../JARVIS-OS-control-browser.png');
 await page.screenshot({path:desktop,fullPage:true});
 // Exercise a complete local DEMO conversation, including real saved messages.
 await page.getByRole('link',{name:'Rozpocznij rozmowę',exact:true}).click();
 await page.getByLabel('Tytuł nowej rozmowy',{exact:true}).fill('HUD browser DEMO');
 await page.getByRole('button',{name:'Nowa rozmowa',exact:true}).click();
 await page.getByLabel('Wiadomość',{exact:true}).fill('Test interfejsu HUD');
 await page.getByRole('button',{name:'Wyślij wiadomość',exact:true}).click();
 await page.locator('.chat-message.assistant').waitFor();
 assert.equal(await page.locator('.chat-message.user').count(),1);
 await page.screenshot({path:path.resolve(root,'docs/evals/control-hud-chat.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Chat must fit mobile viewport');
 await page.screenshot({path:path.resolve(root,'docs/evals/control-hud-chat-mobile.png'),fullPage:true});
 await page.setViewportSize({width:1440,height:1000});
 await page.getByRole('link',{name:'Pulpit',exact:true}).click();await dashboard();
 await page.setViewportSize({width:390,height:844});
 const openMenu=page.getByRole('button',{name:'Otwórz menu',exact:true});await openMenu.focus();await page.keyboard.press('Enter');
 const closeMenu=page.getByRole('button',{name:'Zamknij menu',exact:true});assert.equal(await closeMenu.getAttribute('aria-expanded'),'true');
 await page.keyboard.press('Escape');await openMenu.waitFor();assert.equal(await openMenu.getAttribute('aria-expanded'),'false');
 assert.equal(await openMenu.evaluate(node=>node===document.activeElement),true,'Escape returns keyboard focus to the menu trigger');
 const mobile=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
 assert.ok(mobile.document<=mobile.viewport+1,'Mobile viewport must not overflow');
 const mobileScreenshot=path.resolve(root,'../JARVIS-OS-control-browser-mobile.png');await page.screenshot({path:mobileScreenshot,fullPage:true});
 const beforeBootstrapLogout=requests.filter(item=>item.path==='/api/v1/auth/logout').length;
 await page.getByRole('button',{name:'Wyloguj',exact:true}).click();await loginScreen();
 assert.equal(requests.filter(item=>item.path==='/api/v1/auth/logout').length,beforeBootstrapLogout,'Bootstrap logout clears local state without the session-only endpoint');
 assert.equal(await page.locator('.metric-value').count(),0,'Logout removes authenticated dashboard');
 await secretCheck();
 const session=await accountLogin('browser.owner');
 const loggedOut=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/v1/auth/logout'&&response.request().method()==='POST');
 await page.getByRole('button',{name:'Wyloguj',exact:true}).click();assert.equal((await loggedOut).status(),200);await loginScreen();
 const stale=await context.request.get(info.url+'/api/v1/auth/me',{headers:{'X-Jarvis-Key':session.token}});assert.equal(stale.status(),401,'Session logout must revoke the server token');
 const revocable=await accountLogin('browser.owner');
 await ownerRequest('/api/v1/security/sessions/'+revocable.session_id,'DELETE');
 await page.getByRole('button',{name:'Odśwież dane',exact:true}).click();await loginScreen();
 assert.equal(await page.locator('.metric-value').count(),0,'401 clears old authenticated content');await secretCheck();
 const observerStart=requests.length,observer=await accountLogin('browser.observer');
 await openMenu.click();await page.getByRole('link',{name:'System',exact:true}).click();
 await page.getByRole('heading',{name:'System',exact:true,level:1}).waitFor();
 assert.equal(await page.locator('#main-content').evaluate(node=>node===document.activeElement),true,'Selecting a mobile destination moves focus into its visible content');
 await page.getByRole('button',{name:'Odśwież dane',exact:true}).click();
 await page.waitForLoadState('networkidle');
 const observerRequests=requests.slice(observerStart).filter(item=>item.path.startsWith('/api/'));
 const allowed=new Set(['/api/v1/auth/login','/api/v1/auth/me','/api/v1/status','/api/v1/ready']);
 assert.ok(observerRequests.every(item=>allowed.has(item.path)),'Observer UI must not request owner-only APIs');
 const privateAttempt=await context.request.get(info.url+'/api/v1/memory',{headers:{'X-Jarvis-Key':observer.token}});assert.equal(privateAttempt.status(),403);
 await secretCheck();
 assert.deepEqual(await page.evaluate(()=>window.__controlCsp),[],'Production UI must honor CSP');assert.deepEqual(issues,[]);assert.deepEqual(foreignRequests,[],'UI must not request external origins');assert.deepEqual(assetFailures,[],'Built UI assets must load successfully');
 assert.ok(await page.evaluate(()=>[...document.styleSheets].some(sheet=>sheet.href?.includes('/control/assets/')&&sheet.cssRules.length>0)),'Check uses a loaded production stylesheet');
 assert.ok(requests.some(item=>item.path.startsWith('/control/assets/')&&item.path.endsWith('.js')),'Check uses real built React JavaScript');
 assert.ok(requests.every(item=>{let url=item.url;try{url=decodeURIComponent(url);}catch(_){}return !secretValues.some(secret=>url.includes(secret));}),'Credentials must stay out of request URLs, including queries');
 console.log(JSON.stringify({check:'chromium_control_center',source:'actual_chromium_built_react_temporary_core_no_integrations',passed:true,checks:['bootstrap_login','account_login','wrong_password_cleanup','real_counts','keyboard_navigation','session_logout_revocation','external_revocation_401_cleanup','observer_scope','credentials_not_persisted','csp','mobile_menu','hud_radar_reduced_motion','demo_chat','mobile_chat'],mobile,api_requests:requests.filter(item=>item.path.startsWith('/api/')).length,screenshot:desktop,mobileScreenshot}));
 await cleanup();
})().catch(async error=>{
 console.error(sanitized(error.stack||String(error)));
 try{const page=browser?.contexts()[0]?.pages()[0];if(page)await page.screenshot({path:'/tmp/jarvis-control-browser-failure.png',fullPage:true});}catch(_){}
 if(stderr.trim())console.error(sanitized(stderr));await cleanup();process.exitCode=1;
});

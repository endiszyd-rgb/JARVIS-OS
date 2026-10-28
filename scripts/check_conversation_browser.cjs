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
 await openView('Rozmowa');
 const title='Rozmowa przeglądarkowa',text='<img src=x onerror="window.__jarvisXss=true"> Zwykły tekst & prywatna rozmowa.';
 await page.getByLabel('Tytuł nowej rozmowy',{exact:true}).fill(title);
 const model=page.getByLabel('Model rozmowy',{exact:true});
 await model.selectOption(JSON.stringify({provider:'demo',name:'demo'}));
 const created=requestResponse('/api/v1/chat/sessions');await page.getByRole('button',{name:'Nowa rozmowa',exact:true}).click();
 const createdResponse=await created;assert.equal(createdResponse.status(),201);const session=await createdResponse.json();
 await page.getByLabel('Wiadomość',{exact:true}).fill(text);
 const chatted=requestResponse('/api/v1/chat');await page.getByRole('button',{name:'Wyślij wiadomość',exact:true}).click();
 const chatResponse=await chatted;assert.equal(chatResponse.status(),200);
 const result=await chatResponse.json();assert.equal(result.session_id,session.id);
 assert.equal(chatResponse.request().postDataJSON().model,'demo');
 await page.getByText(text,{exact:true}).waitFor();
 assert.equal(await page.locator('img[src="x"]').count(),0);assert.equal(await page.evaluate(()=>window.__jarvisXss),false);
 const stored=await ownerRequest('/api/v1/chat/sessions/'+session.id+'/messages');
 assert.ok(stored.some(message=>message.role==='user'&&message.content===text));assert.ok(stored.some(message=>message.role==='assistant'&&message.state==='completed'));
 await secretCheck();
 // Reload proves the UI can recover a stored server session after reconnecting.
 await page.reload({waitUntil:'networkidle'});await loginScreen();await keyLogin();await openView('Rozmowa');
 await page.getByRole('button',{name:title,exact:true}).click();await page.getByText(text,{exact:true}).waitFor();
 const voice=await ownerRequest('/api/v1/chat','POST',{message:'Synthetic voice history','model':'demo','input_mode':'voice'});
 const voiceTitle='Głos tylko do odczytu';await ownerRequest('/api/v1/chat/sessions/'+voice.session_id,'PATCH',{title:voiceTitle});
 await openView('System');await openView('Rozmowa');await page.getByRole('button',{name:voiceTitle,exact:true}).click();
 await page.getByText('Otwarta sesja głosowa — tylko odczyt.',{exact:true}).waitFor();
 assert.equal(await page.getByLabel('Wiadomość',{exact:true}).isDisabled(),true);
 assert.equal(await page.getByRole('button',{name:'Wyślij wiadomość',exact:true}).isDisabled(),true);
 await page.getByRole('button',{name:title,exact:true}).click();await page.getByText(text,{exact:true}).waitFor();
 const desktop=path.resolve(root,'../JARVIS-OS-conversation-browser.png');await screenshot(desktop);
 await page.setViewportSize({width:390,height:844});
 const mobileWidths=[];
 const width=async view=>{const size=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));assert.ok(size.document<=size.viewport+1,view+' must not overflow');mobileWidths.push({view,...size});};
 await width('Rozmowa');
 const conversationMobileScreenshot=path.resolve(root,'../JARVIS-OS-conversation-browser-mobile.png');await screenshot(conversationMobileScreenshot);
 await openView('Ustawienia');
 const baseline=(await ownerRequest('/api/v1/status')).settings;
 const replacement='Andreas z przeglądarki';
 await page.getByLabel('Imię',{exact:true}).fill(replacement);
 await page.getByLabel('Styl odpowiedzi',{exact:true}).selectOption('formal');
 await page.getByLabel('Domyślny dostawca',{exact:true}).selectOption('demo');
 const proposed=requestResponse('/api/v1/proposals');await page.getByRole('button',{name:'Podgląd zmiany',exact:true}).click();
 const proposalResponse=await proposed;assert.equal(proposalResponse.status(),201);const proposal=await proposalResponse.json();
 await page.getByRole('button',{name:'Zatwierdź zmianę',exact:true}).waitFor();
 assert.deepEqual((await ownerRequest('/api/v1/status')).settings,baseline,'Preview must not modify current settings');
 const decided=requestResponse('/api/v1/proposals/'+proposal.id+'/decide');
 await page.getByRole('button',{name:'Zatwierdź zmianę',exact:true}).click();assert.equal((await decided).status(),200);
 await page.getByText('Ustawienia zostały zapisane.',{exact:true}).waitFor();
 assert.deepEqual((await ownerRequest('/api/v1/status')).settings,{name:replacement,tone:'formal',model:'demo'});
 await page.getByLabel('Imię',{exact:true}).fill('Odrzucona zmiana');
 const rejectedProposal=requestResponse('/api/v1/proposals');await page.getByRole('button',{name:'Podgląd zmiany',exact:true}).click();
 const rejection=await(await rejectedProposal).json();await page.getByRole('button',{name:'Odrzuć propozycję',exact:true}).waitFor();
 const rejected=requestResponse('/api/v1/proposals/'+rejection.id+'/decide');await page.getByRole('button',{name:'Odrzuć propozycję',exact:true}).click();assert.equal((await rejected).status(),200);
 assert.equal((await ownerRequest('/api/v1/status')).settings.name,replacement,'Rejection must preserve accepted settings');
 await width('Ustawienia');
 const settingsScreenshotState=await page.evaluate(()=>{
  const link=document.querySelector('.skip-link'),rect=link.getBoundingClientRect(),style=getComputedStyle(link),active=document.activeElement;
  return {scrollY,active:{tag:active.tagName,id:active.id,className:active.className},skipLink:{focused:active===link,x:rect.x,y:rect.y,width:rect.width,height:rect.height,position:style.position,transform:style.transform}};
 });
 assert.equal(settingsScreenshotState.skipLink.focused,false);
 assert.ok(settingsScreenshotState.skipLink.y+settingsScreenshotState.skipLink.height<=0,'Unfocused skip link stays outside the viewport');
 const mobileScreenshot=path.resolve(root,'../JARVIS-OS-settings-browser-mobile.png');await screenshot(mobileScreenshot);
 await openView('Historia działań');await page.getByRole('heading',{name:'Ostatnie zdarzenia',exact:true}).waitFor();
 await page.getByLabel('Filtruj zdarzenia',{exact:true}).fill('proposal.created');
 await page.getByText('proposal.created',{exact:true}).first().waitFor();
 const refreshed=requestResponse('/api/v1/audit','GET');await page.getByRole('button',{name:'Odśwież historię',exact:true}).click();assert.equal((await refreshed).status(),200);
 await width('Historia działań');await secretCheck();
 const activityMobileScreenshot=path.resolve(root,'../JARVIS-OS-activity-browser-mobile.png');await screenshot(activityMobileScreenshot);
 await page.getByRole('button',{name:'Wyloguj',exact:true}).click();await loginScreen();
 assert.equal(await page.getByText(text,{exact:true}).count(),0);
 const account=await accountLogin('conversation.owner');await openView('Rozmowa');await page.getByRole('button',{name:title,exact:true}).click();await page.getByText(text,{exact:true}).waitFor();
 const logout=requestResponse('/api/v1/auth/logout');await page.getByRole('button',{name:'Wyloguj',exact:true}).click();assert.equal((await logout).status(),200);await loginScreen();
 const revoked=await context.request.get(info.url+'/api/v1/auth/me',{headers:{'X-Jarvis-Key':account.token}});assert.equal(revoked.status(),401);
 assert.equal(await page.getByText(text,{exact:true}).count(),0);await secretCheck();
 const revocable=await accountLogin('conversation.owner');await openView('Rozmowa');await page.getByRole('button',{name:title,exact:true}).click();await page.getByText(text,{exact:true}).waitFor();
 await ownerRequest('/api/v1/security/sessions/'+revocable.session_id,'DELETE');
 await page.getByRole('button',{name:'Odśwież rozmowę',exact:true}).click();await loginScreen();
 assert.equal(await page.getByText(text,{exact:true}).count(),0,'401 must remove private conversation data');await secretCheck();
 const observerStart=requests.length;await accountLogin('conversation.observer');
 for(const name of ['Rozmowa','Ustawienia','Historia działań'])assert.equal(await page.getByRole('link',{name,exact:true}).count(),0);
 await page.evaluate(()=>{location.hash='#/settings';});
 await page.getByText('Dostęp właściciela',{exact:true}).waitFor();await page.waitForLoadState('networkidle');
 const allowed=new Set(['/api/v1/auth/login','/api/v1/auth/me','/api/v1/status','/api/v1/ready']);
 assert.ok(requests.slice(observerStart).filter(item=>item.path.startsWith('/api/')).every(item=>allowed.has(item.path)),'Observer must not request owner APIs');
 assert.deepEqual(await page.evaluate(()=>window.__conversationCsp),[]);assert.deepEqual(issues,[]);assert.deepEqual(assetFailures,[]);assert.deepEqual(foreign,[]);
 assert.ok(requests.every(item=>{let url=item.url;try{url=decodeURIComponent(url);}catch(_){}return !secrets.some(secret=>url.includes(secret));}));
 console.log(JSON.stringify({check:'chromium_conversation_settings_activity',passed:true,source:'actual_chromium_temporary_core_demo_no_models',checks:['persisted_demo_conversation','configured_model_selection','html_as_text','voice_history_readonly','settings_preview_separate_approval','settings_rejection','activity_filter_refresh','session_logout_revocation','private_view_401_cleanup','observer_owner_gate','credentials_not_persisted','csp'],mobile:mobileWidths,api_requests:requests.filter(item=>item.path.startsWith('/api/')).length,screenshot:desktop,mobileScreenshot,conversationMobileScreenshot,activityMobileScreenshot,settingsScreenshotState}));
 await cleanup();
})().catch(async error=>{
 console.error(sanitized(error.stack||String(error)));
 try{const page=browser?.contexts()[0]?.pages()[0];if(page)await page.screenshot({path:'/tmp/jarvis-conversation-browser-failure.png',fullPage:true});}catch(_){}
 if(stderr.trim())console.error(sanitized(stderr));await cleanup();process.exitCode=1;
});

/* Actual Chromium/Core smoke for the nine M2.4 modules.
 * Uses a synthetic offline workshop snapshot, temporary Core and guarded network.
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
assert.ok(fs.existsSync(python),'Prepare Python 3.12 .venv before this check');
assert.ok(fs.existsSync(path.join(root,'frontend','dist','index.html')),'Build frontend before checking modules');
const fixture=spawn(python,[path.join(__dirname,'browser_modules_fixture.py')],{cwd:root,stdio:['ignore','pipe','pipe']});
let browser=null,stderr='',output='',secrets=[];
fixture.stderr.on('data',chunk=>{stderr=(stderr+chunk.toString()).slice(-12000);});
function sanitized(value){for(const secret of secrets)if(secret)value=value.split(secret).join('[REDACTED]');return value;}
function startup(){return new Promise((resolve,reject)=>{
 const timer=setTimeout(()=>reject(Error('Modules fixture startup timeout')),15000);
 fixture.stdout.on('data',chunk=>{output+=chunk.toString();const newline=output.indexOf('\n');if(newline>=0){clearTimeout(timer);try{resolve(JSON.parse(output.slice(0,newline)));}catch(error){reject(error);}}});
 fixture.once('exit',code=>{clearTimeout(timer);reject(Error('Modules fixture exited '+code));});
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
 const info=await startup(),password='Synthetic-modules-browser-password-123',requests=[],issues=[],assetFailures=[],foreign=[];
 secrets=[info.key,password];
 browser=await chromium.launch({executablePath:executable,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1440,height:1100},reducedMotion:'reduce'});
 const ownerRequest=async(route,method='GET',body,expected=200)=>{
  const response=await context.request.fetch(info.url+route,{method,headers:{'X-Jarvis-Key':info.key},...(body===undefined?{}:{data:body})});
  assert.equal(response.status(),expected,method+' '+route+' unexpected status');return response.json();
 };
 for(const [username,role] of [['modules.home','home_reader'],['modules.workshop','workshop_reader']])await ownerRequest('/api/v1/security/users','POST',{username,password,role},201);
 const page=await context.newPage();
 await page.addInitScript(()=>{window.__modulesCsp=[];window.__memoryXss=false;addEventListener('securitypolicyviolation',event=>window.__modulesCsp.push({directive:event.violatedDirective,blocked:event.blockedURI}));});
 page.on('pageerror',error=>issues.push(error.message));
 page.on('request',request=>{const url=new URL(request.url());if(url.origin!==info.url)foreign.push(url.origin);requests.push({url:url.href,path:url.pathname,method:request.method()});});
 page.on('response',response=>{const url=new URL(response.url());if(url.pathname.startsWith('/control/assets/')&&!response.ok())assetFailures.push({path:url.pathname,status:response.status()});});
 page.on('requestfailed',request=>{const url=new URL(request.url());if(url.pathname.startsWith('/control/assets/'))assetFailures.push({path:url.pathname,status:'failed'});});
 const loginScreen=()=>page.getByRole('heading',{name:'Połącz się z JARVIS OS',exact:true}).waitFor();
 const heading=name=>page.getByRole('heading',{name,exact:true,level:1}).waitFor();
 const requestResponse=(pathname,method)=>page.waitForResponse(response=>new URL(response.url()).pathname===pathname&&response.request().method()===method);
 const secretCheck=async(allowedDomSecrets=[])=>{
  const state=await page.evaluate(({all,forbiddenDom})=>{
   const dom=document.documentElement.outerHTML,storage=JSON.stringify({local:{...localStorage},session:{...sessionStorage},cookies:document.cookie});
   return {dom:forbiddenDom.some(value=>dom.includes(value)),storage:all.some(value=>storage.includes(value)),url:all.some(value=>location.href.includes(value))};
  },{all:secrets,forbiddenDom:secrets.filter(value=>!allowedDomSecrets.includes(value))});
  assert.deepEqual(state,{dom:false,storage:false,url:false});
  assert.ok((await context.cookies()).every(cookie=>!secrets.some(secret=>cookie.value.includes(secret))));
 };
 const openView=async name=>{
  const link=page.getByRole('link',{name,exact:true});
  const menu=page.getByRole('button',{name:'Otwórz menu',exact:true});
  if(await menu.isVisible())await menu.click();
  await link.click();await heading(name);
 };
 const accountLogin=async username=>{
  await page.getByRole('button',{name:'Konto',exact:true}).click();
  await page.getByLabel('Login',{exact:true}).fill(username);await page.getByLabel('Hasło',{exact:true}).fill(password);
  const logged=requestResponse('/api/v1/auth/login','POST');await page.getByRole('button',{name:'Zaloguj się',exact:true}).click();
  const session=await(await logged).json();secrets.push(session.token);await heading('Pulpit');assert.equal(await page.evaluate(()=>location.hash),'#/dashboard');return session;
 };
 const screenshot=async filename=>{await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:filename,fullPage:true});};
 const countPath=route=>requests.filter(item=>item.path===route).length;
 await page.goto(info.url+'/control/',{waitUntil:'networkidle'});await loginScreen();
 await page.getByRole('button',{name:'Klucz właściciela',exact:true}).click();await page.getByLabel('Klucz dostępu',{exact:true}).fill(info.key);
 await page.getByRole('button',{name:'Połącz kluczem',exact:true}).click();await heading('Pulpit');

 // Remote readers require an explicit action. Snapshot reads use a real local copy.
 await openView('AutoLogika');await page.getByRole('heading',{name:'AutoLogika · kopia i odczyt',exact:true}).waitFor();await page.waitForLoadState('networkidle');
 assert.equal(countPath('/api/v1/autologika/snapshot'),0);assert.equal(countPath('/api/v1/autologika/snapshot/orders'),0);assert.equal(countPath('/api/v1/autologika/readonly/orders'),0);
 const snapshotInfo=requestResponse('/api/v1/autologika/snapshot','GET');await page.getByRole('button',{name:'Sprawdź kopię',exact:true}).click();
 const manifest=await(await snapshotInfo).json();assert.equal(manifest.live,false);assert.equal(manifest.domains.length,8);
 await page.getByLabel('Domena kopii',{exact:true}).selectOption('orders');
 const workshop=requestResponse('/api/v1/autologika/snapshot/orders','GET');await page.getByRole('button',{name:'Odczytaj domenę',exact:true}).click();
 const copied=await(await workshop).json();assert.equal(copied.mode,'snapshot_readonly');assert.ok(copied.data.items.some(item=>item.title==='Zlecenie syntetyczne'));
 await page.getByText('Zlecenie syntetyczne',{exact:true}).waitFor();
 assert.equal(await page.getByLabel('Domena kopii',{exact:true}).locator('option').count(),8);
 await openView('Dom');await page.getByRole('heading',{name:'Dom i czujniki',exact:true}).waitFor();await page.waitForLoadState('networkidle');assert.equal(countPath('/api/v1/home/states'),0);
 const home=requestResponse('/api/v1/home/states','GET');await page.getByRole('button',{name:'Odczytaj stany',exact:true}).click();assert.equal((await home).status(),503);
 await page.getByText('Odczyt Home Assistant jest wyłączony lub wymaga konfiguracji.',{exact:true}).waitFor();
 await openView('Urządzenia');await page.getByRole('heading',{name:'Urządzenia i możliwości',exact:true}).waitFor();await page.waitForLoadState('networkidle');assert.equal(countPath('/api/v1/integrations'),0);
 const devices=requestResponse('/api/v1/integrations','GET');await page.getByRole('button',{name:'Odczytaj konfigurację',exact:true}).click();assert.equal((await devices).status(),200);

 // Revision-aware personal memory: persist, correct, review history, confirm deletion.
 await openView('Pamięć');
 const note='<img src=x onerror="window.__memoryXss=true"> Syntetyczna notatka właściciela';
 await page.getByLabel('Nowa notatka',{exact:true}).fill(note);
 const createdNote=requestResponse('/api/v1/memory','POST');await page.getByRole('button',{name:'Dodaj notatkę',exact:true}).click();
 const noteResponse=await createdNote;assert.equal(noteResponse.status(),201);const memory=await noteResponse.json();
 await page.getByText(note,{exact:true}).waitFor();assert.equal(await page.locator('img[src="x"]').count(),0);assert.equal(await page.evaluate(()=>window.__memoryXss),false);
 const row=()=>page.getByRole('list',{name:'Pobrane notatki',exact:true}).getByRole('listitem').filter({has:page.locator('.memory-note-text').filter({hasText:note})});
 await row().getByRole('button',{name:'Edytuj notatkę',exact:true}).click();
 const corrected='Korekta syntetycznej notatki właściciela';await page.getByLabel('Treść korekty',{exact:true}).fill(corrected);
 const correction=requestResponse('/api/v1/memory/'+memory.id,'PUT');await page.getByRole('button',{name:'Zapisz korektę',exact:true}).click();
 const correctionResponse=await correction;assert.equal(correctionResponse.status(),200);assert.equal(correctionResponse.request().postDataJSON().revision,0);assert.equal((await correctionResponse.json()).revision,1);
 await page.getByText(corrected,{exact:true}).waitFor();
 const correctedRow=()=>page.getByRole('list',{name:'Pobrane notatki',exact:true}).getByRole('listitem').filter({has:page.locator('.memory-note-text').filter({hasText:corrected})});
 const history=requestResponse('/api/v1/memory/'+memory.id+'/history','GET');await correctedRow().getByRole('button',{name:'Historia korekt',exact:true}).click();
 const previous=await(await history).json();assert.equal(previous.length,1);assert.equal(previous[0].text,note);
 await page.getByRole('heading',{name:'Historia korekt notatki',exact:true}).waitFor();
 const memoryScreenshot=path.resolve(root,'../JARVIS-OS-modules-memory-browser.png');await screenshot(memoryScreenshot);
 await correctedRow().getByRole('button',{name:'Usuń notatkę',exact:true}).click();
 assert.ok((await ownerRequest('/api/v1/memory')).some(item=>item.id===memory.id),'Deletion preview must preserve the note');
 const deleted=requestResponse('/api/v1/memory/'+memory.id,'DELETE');await page.getByRole('button',{name:'Potwierdź usunięcie',exact:true}).click();assert.equal((await deleted).status(),200);
 assert.ok(!(await ownerRequest('/api/v1/memory')).some(item=>item.id===memory.id));

 // A genuine proposal/approval, then only the fixture's deadline is moved due.
 await openView('Automatyzacje');const reminder='Syntetyczne przypomnienie modułów',message='Lokalna wiadomość modułów bez wysyłki';
 await page.getByLabel('Tytuł przypomnienia',{exact:true}).fill(reminder);await page.getByLabel('Co ile minut',{exact:true}).fill('60');await page.getByLabel('Treść przypomnienia',{exact:true}).fill(message);
 const proposed=requestResponse('/api/v1/proposals','POST');await page.getByRole('button',{name:'Podgląd przypomnienia',exact:true}).click();
 const proposalResponse=await proposed;assert.equal(proposalResponse.status(),201);const proposal=await proposalResponse.json();assert.equal(proposal.kind,'automation');
 await page.getByRole('button',{name:'Zatwierdź przypomnienie',exact:true}).waitFor();assert.ok(!(await ownerRequest('/api/v1/automations')).some(item=>item.id===proposal.id),'Preview must not install a reminder');
 const accepted=requestResponse('/api/v1/proposals/'+proposal.id+'/decide','POST');await page.getByRole('button',{name:'Zatwierdź przypomnienie',exact:true}).click();assert.equal((await accepted).status(),200);
 await page.getByText('Przypomnienie zatwierdzone i zapisane.',{exact:true}).waitFor();assert.ok((await ownerRequest('/api/v1/automations')).some(item=>item.id===proposal.id));
 assert.equal((await ownerRequest('/_fixture_make_due/'+proposal.id,'POST')).fixture_clock_control,true);
 const tick=requestResponse('/api/v1/automations/tick','POST');await page.getByRole('button',{name:'Sprawdź terminy teraz',exact:true}).click();
 const fired=await(await tick).json();assert.deepEqual(fired.fired,[proposal.id]);assert.equal(fired.external_request_sent,false);
 await openView('Powiadomienia');await page.getByRole('heading',{name:'Ostatnie powiadomienia',exact:true}).waitFor();await page.getByText(message,{exact:true}).waitFor();
 await page.getByLabel('Filtruj powiadomienia',{exact:true}).fill('Lokalna wiadomość');
 const notified=requestResponse('/api/v1/notifications','GET');await page.getByRole('button',{name:'Odśwież powiadomienia',exact:true}).click();assert.equal((await notified).status(),200);

 // Carrier-free local policy and decision preview honor DND even in a crisis.
 await openView('Telefonia');const baseline=await ownerRequest('/api/v1/telephony/settings');
 await page.getByLabel('Numer właściciela',{exact:true}).fill('+12025550101');await page.getByLabel('Numer warsztatu',{exact:true}).fill('+12025550102');
 await page.getByLabel('Poniedziałek',{exact:true}).fill('09:00-17:00');await page.getByLabel('Zezwalaj na przekazywanie',{exact:true}).check();await page.getByLabel('Nie przeszkadzać',{exact:true}).check();
 const policy=requestResponse('/api/v1/telephony/settings','PUT');await page.getByRole('button',{name:'Zapisz zasady',exact:true}).click();
 const policyResponse=await policy;assert.equal(policyResponse.status(),200);assert.equal(policyResponse.request().postDataJSON().revision,baseline.revision);const savedPolicy=await policyResponse.json();assert.equal(savedPolicy.revision,baseline.revision+1);assert.equal(savedPolicy.executed,false);
 await page.getByText('Zapisano zasady. Nie wykonano połączenia.',{exact:true}).waitFor();
 await page.getByLabel('Termin podglądu ze strefą',{exact:true}).fill('2026-10-26T10:00:00+01:00');await page.getByLabel('Przykładowa sytuacja',{exact:true}).selectOption('crisis');
 const preview=requestResponse('/api/v1/telephony/preview','POST');await page.getByRole('button',{name:'Sprawdź decyzję',exact:true}).click();
 const decision=await(await preview).json();assert.equal(decision.executed,false);assert.equal(decision.eligible_for_owner_contact,false);assert.ok(decision.reasons.includes('do_not_disturb'));assert.equal(decision.notifications_sent,false);assert.equal(decision.carrier_connected,false);
 await page.getByText('Podgląd — nie wykonano połączenia ani wysyłki.',{exact:true}).waitFor();

 // Security uses real password hashing, login sessions, revocation and one-time tokens.
 await openView('Bezpieczeństwo');await page.locator('summary').filter({hasText:/^Utwórz konto$/}).click();
 await page.getByLabel('Login nowego konta',{exact:true}).fill('modules.created');await page.getByLabel('Hasło nowego konta',{exact:true}).fill(password);await page.getByLabel('Rola nowego konta',{exact:true}).selectOption('observer');
 const createdUser=requestResponse('/api/v1/security/users','POST');await page.getByRole('button',{name:'Utwórz konto',exact:true}).click();assert.equal((await createdUser).status(),201);
 assert.equal(await page.getByLabel('Hasło nowego konta',{exact:true}).inputValue(),'');
 const target=await ownerRequest('/api/v1/auth/login','POST',{username:'modules.created',password});secrets.push(target.token);
 const refreshedSessions=requestResponse('/api/v1/security/sessions','GET');await page.getByRole('button',{name:'Odśwież dostęp',exact:true}).click();assert.equal((await refreshedSessions).status(),200);
 await page.getByRole('button',{name:'Odwołaj sesję modules.created '+target.session_id,exact:true}).click();
 const revoked=requestResponse('/api/v1/security/sessions/'+target.session_id,'DELETE');await page.getByRole('button',{name:'Potwierdź odwołanie',exact:true}).click();assert.equal((await revoked).status(),200);
 const unauthorized=await context.request.get(info.url+'/api/v1/auth/me',{headers:{'X-Jarvis-Key':target.token}});assert.equal(unauthorized.status(),401);
 await page.locator('summary').filter({hasText:/^Utwórz token usługowy$/}).click();await page.getByLabel('Nazwa tokenu',{exact:true}).fill('Moduły browser status');await page.getByLabel('Ważność tokenu w godzinach',{exact:true}).fill('1');await page.getByRole('checkbox',{name:/status:read/}).check();
 const issued=requestResponse('/api/v1/security/tokens','POST');await page.getByRole('button',{name:'Utwórz token',exact:true}).click();const issuedResponse=await issued;assert.equal(issuedResponse.status(),201);const token=await issuedResponse.json();secrets.push(token.token);
 assert.equal(await page.getByLabel('Nowy token usługowy',{exact:true}).textContent(),token.token);await secretCheck([token.token]);
 await page.getByRole('button',{name:'Ukryj token',exact:true}).click();assert.equal(await page.getByLabel('Nowy token usługowy',{exact:true}).count(),0);await secretCheck();
 const securityScreenshot=path.resolve(root,'../JARVIS-OS-modules-security-browser.png');await screenshot(securityScreenshot);
 await openView('Logi');await page.getByRole('heading',{name:'Ostatnie zdarzenia',exact:true}).waitFor();await page.getByLabel('Filtruj zdarzenia',{exact:true}).fill('scheduler.tick');await page.getByText('scheduler.tick',{exact:true}).waitFor();

 // Every delivered module is reachable and fits an actual 390px viewport.
 const modules=[['workshop','AutoLogika'],['home','Dom'],['devices','Urządzenia'],['automations','Automatyzacje'],['memory','Pamięć'],['telephony','Telefonia'],['notifications','Powiadomienia'],['security','Bezpieczeństwo'],['logs','Logi']],mobile=[],screenshots=[];
 await page.setViewportSize({width:390,height:844});
 for(const [route,name] of modules){
  await openView(name);await page.waitForLoadState('networkidle');const size=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));assert.ok(size.document<=size.viewport+1,name+' must not overflow');mobile.push({view:name,...size});
  const filename=path.resolve(root,'../JARVIS-OS-modules-'+route+'-mobile.png');await screenshot(filename);screenshots.push(filename);await secretCheck();
 }
 await page.getByRole('button',{name:'Wyloguj',exact:true}).click();await loginScreen();assert.equal(await page.getByLabel('Nowy token usługowy',{exact:true}).count(),0);await secretCheck();

 // A Home reader has no workshop/private requests or navigation.
 const homeStart=requests.length;await accountLogin('modules.home');
 assert.equal(await page.getByRole('link',{name:'AutoLogika',exact:true}).count(),0);for(const name of ['Pamięć','Automatyzacje','Telefonia','Powiadomienia','Bezpieczeństwo','Logi'])assert.equal(await page.getByRole('link',{name,exact:true}).count(),0);
 await openView('Dom');const limitedHome=requestResponse('/api/v1/home/states','GET');await page.getByRole('button',{name:'Odczytaj stany',exact:true}).click();assert.equal((await limitedHome).status(),503);
 await page.evaluate(()=>{location.hash='#/memory';});await page.getByText('Dostęp właściciela',{exact:true}).waitFor();await page.waitForLoadState('networkidle');
 const homeAllowed=new Set(['/api/v1/auth/login','/api/v1/auth/me','/api/v1/status','/api/v1/home/states']);assert.ok(requests.slice(homeStart).filter(item=>item.path.startsWith('/api/')).every(item=>homeAllowed.has(item.path)));
 await page.getByRole('button',{name:'Wyloguj',exact:true}).click();await loginScreen();

 // A workshop reader sees exactly five permitted domains and no owner modules.
 const workshopStart=requests.length,workshopAccount=await accountLogin('modules.workshop');assert.equal(await page.getByRole('link',{name:'Dom',exact:true}).count(),0);assert.equal(await page.getByRole('link',{name:'Bezpieczeństwo',exact:true}).count(),0);
 await openView('AutoLogika');const domainSelect=page.getByLabel('Domena kopii',{exact:true});
 assert.deepEqual(await domainSelect.locator('option').evaluateAll(nodes=>nodes.map(node=>node.value)),['calendar','orders','vehicles','parts','customers']);
 for(const domain of ['calendar','orders','vehicles','parts','customers']){
  await domainSelect.selectOption(domain);const response=requestResponse('/api/v1/autologika/snapshot/'+domain,'GET');await page.getByRole('button',{name:'Odczytaj domenę',exact:true}).click();assert.equal((await response).status(),200);
 }
 await page.evaluate(()=>{location.hash='#/notifications';});await page.getByText('Dostęp właściciela',{exact:true}).waitFor();await page.waitForLoadState('networkidle');
 const workshopAllowed=new Set(['/api/v1/auth/login','/api/v1/auth/me','/api/v1/status',...['calendar','orders','vehicles','parts','customers'].map(domain=>'/api/v1/autologika/snapshot/'+domain)]);
 assert.ok(requests.slice(workshopStart).filter(item=>item.path.startsWith('/api/')).every(item=>workshopAllowed.has(item.path)));
 const deniedFinance=await context.request.get(info.url+'/api/v1/autologika/snapshot/finances',{headers:{'X-Jarvis-Key':workshopAccount.token}});assert.equal(deniedFinance.status(),403);
 const status=await ownerRequest('/_fixture_status');assert.deepEqual(status,{network_attempts:0,source_unchanged:true,snapshot_unchanged:true,synthetic_snapshot:true});
 await secretCheck();assert.deepEqual(await page.evaluate(()=>window.__modulesCsp),[]);assert.deepEqual(issues,[]);assert.deepEqual(assetFailures,[]);assert.deepEqual(foreign,[]);
 assert.ok(requests.every(item=>{let url=item.url;try{url=decodeURIComponent(url);}catch(_){}return !secrets.some(secret=>url.includes(secret));}));
 console.log(JSON.stringify({check:'chromium_modules',passed:true,source:'actual_chromium_temporary_core_synthetic_snapshot',checks:['nine_modules_navigation_mobile','explicit_remote_read_buttons','synthetic_snapshot_readonly','memory_crud_revision_history_confirmation','automation_proposal_separate_approval','scheduler_notification_with_fixture_due_time','telephony_policy_revision_dnd_preview_no_carrier','security_user_session_revocation','one_time_service_token_cleared','home_reader_scope','workshop_reader_five_domains','private_route_gates','credentials_not_persisted','csp'],fixture:status,mobile,api_requests:requests.filter(item=>item.path.startsWith('/api/')).length,screenshots:[memoryScreenshot,securityScreenshot,...screenshots]}));
 await cleanup();
})().catch(async error=>{
 console.error(sanitized(error.stack||String(error)));
 try{const page=browser?.contexts()[0]?.pages()[0];if(page)await page.screenshot({path:'/tmp/jarvis-modules-browser-failure.png',fullPage:true});}catch(_){}
 if(stderr.trim())console.error(sanitized(stderr));await cleanup();process.exitCode=1;
});

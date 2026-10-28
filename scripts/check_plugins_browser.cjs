/* Actual Chromium/Core Plugin Manager verification with a genuine localhost GET.
 * Temporary data and synthetic credentials only; no providers or devices.
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
assert.ok(fs.existsSync(python),'Prepare the Python 3.12 .venv before this check');
assert.ok(fs.existsSync(path.join(root,'frontend','dist','index.html')),'Build frontend before checking plugins');
const fixture=spawn(python,[path.join(__dirname,'browser_plugins_fixture.py')],{cwd:root,stdio:['ignore','pipe','pipe']});
let browser=null,stderr='',output='',secrets=[];
fixture.stderr.on('data',chunk=>{stderr=(stderr+chunk.toString()).slice(-12000);});
function sanitized(value){for(const secret of secrets)if(secret)value=value.split(secret).join('[REDACTED]');return value;}
function startup(){return new Promise((resolve,reject)=>{
 const timer=setTimeout(()=>reject(Error('Plugins fixture startup timeout')),15000);
 fixture.stdout.on('data',chunk=>{output+=chunk.toString();const newline=output.indexOf('\n');if(newline>=0){clearTimeout(timer);try{resolve(JSON.parse(output.slice(0,newline)));}catch(error){reject(error);}}});
 fixture.once('exit',code=>{clearTimeout(timer);reject(Error('Plugins fixture exited '+code));});
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
 const info=await startup(),password='Synthetic-plugin-browser-password-123',requests=[],issues=[],assetFailures=[],foreign=[];
 secrets=[info.key,info.plugin_secret,password];
 browser=await chromium.launch({executablePath:executable,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1440,height:1100},reducedMotion:'reduce'});
 const ownerRequest=async(route,method='GET',body,expected=200)=>{
  const response=await context.request.fetch(info.url+route,{method,headers:{'X-Jarvis-Key':info.key},...(body===undefined?{}:{data:body})});
  assert.equal(response.status(),expected,method+' '+route+' unexpected status');return response.json();
 };
 const remoteState=async()=>{
  const response=await context.request.get(info.plugin_origin+'/_fixture_status');assert.equal(response.status(),200);return response.json();
 };
 const pid='browser_openapi',name='Przeglądarkowy odczyt';
 const spec={openapi:'3.0.3',paths:{'/items/{item}':{get:{operationId:'read_item',summary:'Synthetic fixture item',parameters:[{name:'item',in:'path',required:true,schema:{type:'integer',minimum:1}}]}}}};
 await ownerRequest('/api/v1/plugins','POST',{id:pid,name,protocol:'openapi',description:'Genuine local HTTP fixture'},201);
 await ownerRequest('/api/v1/security/users','POST',{username:'plugins.observer',password,role:'observer'},201);
 const page=await context.newPage();
 await page.addInitScript(()=>{window.__pluginsCsp=[];window.__pluginXss=false;addEventListener('securitypolicyviolation',event=>window.__pluginsCsp.push({directive:event.violatedDirective,blocked:event.blockedURI}));});
 page.on('pageerror',error=>issues.push(error.message));
 page.on('request',request=>{const url=new URL(request.url());if(url.origin!==info.url)foreign.push(url.origin);requests.push({url:url.href,path:url.pathname,method:request.method()});});
 page.on('response',response=>{const url=new URL(response.url());if(url.pathname.startsWith('/control/assets/')&&!response.ok())assetFailures.push({path:url.pathname,status:response.status()});});
 page.on('requestfailed',request=>{const url=new URL(request.url());if(url.pathname.startsWith('/control/assets/'))assetFailures.push({path:url.pathname,status:'failed'});});
 const loginScreen=()=>page.getByRole('heading',{name:'Połącz się z JARVIS OS',exact:true}).waitFor();
 const heading=name=>page.getByRole('heading',{name,exact:true,level:1}).waitFor();
 const requestResponse=(pathname,method)=>page.waitForResponse(response=>new URL(response.url()).pathname===pathname&&response.request().method()===method);
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
 const mutations=()=>requests.filter(item=>item.path==='/api/v1/tools'||/\/plugins\/[^/]+\/(tools|invoke)$/.test(item.path));
 const assertRemoteCount=async count=>assert.equal((await remoteState()).count,count,'Remote fixture call count');
 const screenshot=async filename=>{await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:filename,fullPage:true});};
 await page.goto(info.url+'/control/',{waitUntil:'networkidle'});await loginScreen();
 await page.getByRole('button',{name:'Klucz właściciela',exact:true}).click();
 await page.getByLabel('Klucz dostępu',{exact:true}).fill(info.key);
 await page.getByRole('button',{name:'Połącz kluczem',exact:true}).click();await heading('Pulpit');
 assert.equal(await page.evaluate(()=>location.hash),'#/dashboard','Login route and URL must agree');
 await openView('Pluginy');await page.getByRole('button',{name,exact:true}).waitFor();
 await page.waitForLoadState('networkidle');assert.deepEqual(mutations(),[]);await assertRemoteCount(0);
 const loadedConfig=requestResponse('/api/v1/plugins/'+pid+'/config','GET');await page.getByRole('button',{name,exact:true}).click();
 assert.equal((await loadedConfig).status(),200);await page.getByLabel('Adres endpointu',{exact:true}).waitFor();
 assert.deepEqual(mutations(),[]);await assertRemoteCount(0);
 await page.getByLabel('Adres endpointu',{exact:true}).fill(info.plugin_origin);
 await page.getByLabel('Nazwa zmiennej sekretu',{exact:true}).fill(info.secret_env);
 await page.getByLabel('Zatwierdzone odczyty',{exact:true}).fill('read_item');
 await page.getByLabel('Specyfikacja OpenAPI JSON',{exact:true}).fill(JSON.stringify(spec,null,2));
 const saved=requestResponse('/api/v1/plugins/'+pid+'/config','PUT');await page.getByRole('button',{name:'Zapisz konfigurację',exact:true}).click();
 const saveResponse=await saved;assert.equal(saveResponse.status(),200);assert.deepEqual(await saveResponse.json(),{configured:true,enabled:false});
 await page.getByRole('button',{name:'Włącz plugin',exact:true}).waitFor();await assertRemoteCount(0);assert.deepEqual(mutations(),[]);
 const enabled=requestResponse('/api/v1/plugins/'+pid,'PUT');await page.getByRole('button',{name:'Włącz plugin',exact:true}).click();
 assert.equal((await enabled).status(),200);await page.getByRole('button',{name:'Wyłącz plugin',exact:true}).waitFor();await assertRemoteCount(0);assert.deepEqual(mutations(),[]);
 const catalog=requestResponse('/api/v1/plugins/'+pid+'/tools','GET');await page.getByRole('button',{name:'Odczytaj katalog',exact:true}).click();
 const catalogResponse=await catalog;assert.equal(catalogResponse.status(),200);const tools=await catalogResponse.json();assert.equal(tools.length,1);assert.equal(tools[0].name,'read_item');
 await page.getByText('Odczytano lokalny katalog OpenAPI z konfiguracji. Nie wykonano testu połączenia.',{exact:true}).waitFor();
 await page.getByLabel('Operacja odczytu',{exact:true}).selectOption('read_item');await assertRemoteCount(0);
 await page.getByLabel('Argumenty JSON',{exact:true}).fill('{"item":7}');
 const invoked=requestResponse('/api/v1/plugins/'+pid+'/invoke','POST');await page.getByRole('button',{name:'Wykonaj odczyt testowy',exact:true}).click();
 const invokeResponse=await invoked;assert.equal(invokeResponse.status(),200);const result=await invokeResponse.json();
 assert.equal(result.mode,'live_readonly');assert.equal(result.protocol,'openapi');assert.equal(result.data.item,7);assert.equal(result.data.source,'genuine_loopback_http');
 await page.getByRole('heading',{name:'Wynik odczytu',exact:true}).waitFor();await page.getByText('Synthetic read 7',{exact:false}).waitFor();
 assert.deepEqual(await remoteState(),{requests:[{method:'GET',path:'/items/7',authorized:true}],count:1});
 assert.equal(await page.locator('img[src="x"]').count(),0);assert.equal(await page.evaluate(()=>window.__pluginXss),false);await secretCheck();
 const audit=JSON.stringify(await ownerRequest('/api/v1/audit'));
 assert.ok(!secrets.some(secret=>audit.includes(secret)));assert.ok(!audit.includes(result.data.label),'Tool result must not be copied to audit');
 const desktop=path.resolve(root,'../JARVIS-OS-plugins-browser.png');await screenshot(desktop);
 const disabled=requestResponse('/api/v1/plugins/'+pid,'PUT');await page.getByRole('button',{name:'Wyłącz plugin',exact:true}).click();assert.equal((await disabled).status(),200);
 await page.getByRole('button',{name:'Włącz plugin',exact:true}).waitFor();await assertRemoteCount(1);
 const reenabled=requestResponse('/api/v1/plugins/'+pid,'PUT');await page.getByRole('button',{name:'Włącz plugin',exact:true}).click();assert.equal((await reenabled).status(),200);
 await page.getByRole('button',{name:'Wyłącz plugin',exact:true}).waitFor();
 await page.getByLabel('Adres endpointu',{exact:true}).fill(info.plugin_origin+'/');
 assert.equal(await page.getByRole('button',{name:'Odczytaj katalog',exact:true}).isDisabled(),true,'Unsaved configuration must block discovery');
 assert.equal(await page.getByRole('heading',{name:'Wynik odczytu',exact:true}).count(),0,'Configuration editing clears the previous result');
 const revokedActivation=requestResponse('/api/v1/plugins/'+pid+'/config','PUT');await page.getByRole('button',{name:'Zapisz konfigurację',exact:true}).click();
 assert.equal((await revokedActivation).status(),200);await page.getByRole('button',{name:'Włącz plugin',exact:true}).waitFor();
 const persisted=(await ownerRequest('/api/v1/plugins')).find(item=>item.id===pid);assert.equal(persisted.enabled,false);await assertRemoteCount(1);
 assert.equal(mutations().filter(item=>item.path.endsWith('/invoke')).length,1,'Only the deliberate read may invoke a tool');
 assert.equal(mutations().filter(item=>item.path.endsWith('/tools')).length,1,'Catalog requests require an explicit click');
 await page.setViewportSize({width:390,height:844});
 const mobile=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));assert.ok(mobile.document<=mobile.viewport+1,'Plugin view must not overflow on mobile');
 const mobileScreenshot=path.resolve(root,'../JARVIS-OS-plugins-browser-mobile.png');await screenshot(mobileScreenshot);await secretCheck();
 await page.getByRole('button',{name:'Wyloguj',exact:true}).click();await loginScreen();assert.equal(await page.getByLabel('Adres endpointu',{exact:true}).count(),0);
 const observerStart=requests.length;
 await page.getByRole('button',{name:'Konto',exact:true}).click();await page.getByLabel('Login',{exact:true}).fill('plugins.observer');await page.getByLabel('Hasło',{exact:true}).fill(password);
 const logged=requestResponse('/api/v1/auth/login','POST');await page.getByRole('button',{name:'Zaloguj się',exact:true}).click();const observer=await(await logged).json();secrets.push(observer.token);await heading('Pulpit');
 assert.equal(await page.evaluate(()=>location.hash),'#/dashboard','Reconnect clears the previous private route');
 assert.equal(await page.getByRole('link',{name:'Pluginy',exact:true}).count(),0);await page.evaluate(()=>{location.hash='#/plugins';});
 await page.getByText('Dostęp właściciela',{exact:true}).waitFor();await page.waitForLoadState('networkidle');
 const allowed=new Set(['/api/v1/auth/login','/api/v1/auth/me','/api/v1/status']);
 assert.ok(requests.slice(observerStart).filter(item=>item.path.startsWith('/api/')).every(item=>allowed.has(item.path)),'Observer must not request Plugin Manager APIs');
 await assertRemoteCount(1);await secretCheck();
 assert.deepEqual(await page.evaluate(()=>window.__pluginsCsp),[]);assert.deepEqual(issues,[]);assert.deepEqual(assetFailures,[]);assert.deepEqual(foreign,[]);
 assert.ok(requests.every(item=>{let url=item.url;try{url=decodeURIComponent(url);}catch(_){}return !secrets.some(secret=>url.includes(secret));}));
 console.log(JSON.stringify({check:'chromium_plugin_manager',passed:true,source:'actual_chromium_temporary_core_genuine_loopback_http',checks:['no_automatic_discovery_or_invocation','configuration_revokes_activation','unsaved_configuration_blocks_discovery','explicit_enable_disable','openapi_catalog_is_not_connection_test','genuine_reviewed_get_with_environment_secret','escaped_tool_result','audit_privacy','login_hash_matches_dashboard','observer_owner_gate','logout_private_cleanup','credentials_not_persisted','csp'],remote_requests:1,api_requests:requests.filter(item=>item.path.startsWith('/api/')).length,mobile,screenshot:desktop,mobileScreenshot}));
 await cleanup();
})().catch(async error=>{
 console.error(sanitized(error.stack||String(error)));
 try{const page=browser?.contexts()[0]?.pages()[0];if(page)await page.screenshot({path:'/tmp/jarvis-plugins-browser-failure.png',fullPage:true});}catch(_){}
 if(stderr.trim())console.error(sanitized(stderr));await cleanup();process.exitCode=1;
});

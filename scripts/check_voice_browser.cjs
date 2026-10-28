/* Actual Chromium/AudioWorklet check with synthetic microphone and local fixtures.
 * Requires Playwright and a Chromium executable; absence is an explicit failure.
 * No real microphone, model inference, carrier or user data is used.
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
fixture.stderr.on('data',chunk=>{stderr+=chunk.toString();if(stderr.length>20000)stderr=stderr.slice(-20000);});
function startup(){return new Promise((resolve,reject)=>{
 const timer=setTimeout(()=>reject(Error('Synthetic browser fixture startup timeout: '+stderr)),15000);
 fixture.stdout.on('data',chunk=>{output+=chunk.toString();const newline=output.indexOf('\n');if(newline>=0){clearTimeout(timer);try{resolve(JSON.parse(output.slice(0,newline)));}catch(error){reject(error);}}});
 fixture.once('exit',code=>{clearTimeout(timer);reject(Error('Synthetic fixture exited '+code+': '+stderr));});
 fixture.once('error',error=>{clearTimeout(timer);reject(error);});
});}
async function cleanup(){
 if(browser){await browser.close();browser=null;}
 if(fixture.exitCode===null&&fixture.signalCode===null){fixture.kill('SIGTERM');let timer;await Promise.race([new Promise(resolve=>fixture.once('exit',resolve)),new Promise(resolve=>{timer=setTimeout(resolve,5000);})]);clearTimeout(timer);if(fixture.exitCode===null&&fixture.signalCode===null){fixture.kill('SIGKILL');await new Promise(resolve=>fixture.once('exit',resolve));}}
}
(async()=>{
 const info=await startup(),issues=[],chats=[],requests=[];
 browser=await chromium.launch({executablePath:executable,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','--use-file-for-fake-audio-capture='+info.microphone,'--autoplay-policy=no-user-gesture-required']});
 const context=await browser.newContext({permissions:['microphone'],viewport:{width:1280,height:1100}});
 await context.addInitScript(()=>{
  window.__voiceTracks=[];window.__voiceContexts=[];window.__voiceSnapshots=[];
  const originalGet=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia=async constraints=>{const stream=await originalGet(constraints);window.__voiceTracks.push(...stream.getTracks());return stream;};
  const Context=window.AudioContext;
  window.AudioContext=class extends Context{constructor(...args){super(...args);window.__voiceContexts.push(this);}};
 });
 const page=await context.newPage();
 page.on('pageerror',error=>issues.push(error.message));
 page.on('console',msg=>{if(msg.type()==='error'&&!msg.location().url.endsWith('/favicon.ico'))issues.push(msg.text());});
 page.on('request',request=>{if(request.url().includes('/api/'))requests.push({url:request.url(),method:request.method()});if(request.url().endsWith('/api/chat')&&request.method()==='POST')chats.push({body:request.postDataJSON(),key:request.headers()['x-jarvis-key']});});
 await page.goto(info.url,{waitUntil:'networkidle'});
 await page.locator('#key').fill(info.key);await page.getByRole('button',{name:'Połącz',exact:true}).click();
 await page.getByText('Połączono · klucz tylko w pamięci tej karty').waitFor();
 await page.getByRole('heading',{name:'Tryby integracji',exact:true}).waitFor();
 await page.getByRole('button',{name:'Głos lokalny',exact:true}).click();
 await page.getByRole('heading',{name:'Rozmowa przez mikrofon',exact:true}).waitFor();
 assert.equal(await page.locator('#voice-review').isChecked(),true);
 assert.equal(await page.evaluate(()=>window.__voiceTracks.length),0,'No microphone before activation');
 const selects=page.locator('#content select');
 await selects.selectOption(JSON.stringify({provider:'ollama',name:'browser:synthetic'}));
 await page.getByRole('button',{name:'Rozpocznij rozmowę głosową',exact:true}).click();
 const draft=page.getByRole('textbox',{name:'Sprawdź rozpoznaną wypowiedź',exact:true});
 await draft.waitFor({state:'visible',timeout:20000});
 assert.equal(await draft.inputValue(),'Jak działasz?');assert.equal(chats.length,0,'Review must block chat');
 await draft.fill('Jak działasz po korekcie?');await page.getByRole('button',{name:'Wyślij tekst',exact:true}).click();
 await page.getByText('JARVIS: Kontrolowana odpowiedź przeglądarki 1.',{exact:true}).waitFor({timeout:15000});
 await draft.waitFor({state:'visible',timeout:20000});
 assert.equal(await draft.inputValue(),'Druga wypowiedź');
 await page.getByRole('button',{name:'Wyślij tekst',exact:true}).click();
 await page.getByText('JARVIS: Kontrolowana odpowiedź przeglądarki 2.',{exact:true}).waitFor({timeout:15000});
 await page.getByText('Sesja zakończona. Mikrofon wyłączony.',{exact:true}).waitFor({timeout:20000});
 assert.equal(chats.length,2);assert.ok(chats.every(item=>item.key===info.key&&item.body.input_mode==='voice'&&item.body.do_not_remember===true));
 assert.equal(chats[0].body.message,'Jak działasz po korekcie?');assert.equal(chats[0].body.session_id,undefined);assert.equal(typeof chats[1].body.session_id,'string');
 const fixtureState=await (await context.request.get(info.url+'/browser-fixture/state')).json();
 assert.equal(fixtureState.stt,3);assert.equal(fixtureState.tts,2);assert.equal(fixtureState.model_requests.length,2);assert.deepEqual(fixtureState.failures,[]);
 assert.equal(fixtureState.model_requests[0].messages.length,2);assert.equal(fixtureState.model_requests[1].messages.length,4);
 const resources=await page.evaluate(()=>({tracks:window.__voiceTracks.map(t=>t.readyState),contexts:window.__voiceContexts.map(c=>c.state)}));
 assert.ok(resources.tracks.length>=3);assert.ok(resources.tracks.every(state=>state==='ended'));assert.ok(resources.contexts.length>=3);assert.ok(resources.contexts.every(state=>state==='closed'));
 assert.deepEqual(issues,[]);
 const screenshot=process.env.JARVIS_BROWSER_SCREENSHOT||path.resolve(root,'../JARVIS-OS-voice-browser.png');
 await page.screenshot({path:screenshot,fullPage:true});
 console.log(JSON.stringify({check:'chromium_voice_chain',source:'actual_chromium_synthetic_microphone_services',passed:true,turns:chats.length,stt:fixtureState.stt,tts:fixtureState.tts,resources,screenshot}));
 await cleanup();
})().catch(async error=>{console.error(error);try{const page=browser?.contexts()[0]?.pages()[0];if(page){console.error((await page.locator('body').innerText()).slice(-5000));await page.screenshot({path:'/tmp/jarvis-browser-voice-failure.png',fullPage:true});}}catch(_){}if(stderr.trim())console.error(stderr);await cleanup();process.exitCode=1;});

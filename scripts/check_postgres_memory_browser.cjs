/* Standalone child of the guarded PostgreSQL runner, synthetic credentials on stdin. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const info=JSON.parse(fs.readFileSync(0,'utf8'));
 const browser=await chromium.launch({executablePath:process.env.JARVIS_BROWSER_EXECUTABLE||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844}}),page=await context.newPage(),issues=[],foreign=[];
  page.on('pageerror',e=>issues.push(e.message));page.on('request',r=>{if(new URL(r.url()).origin!==info.url)foreign.push('foreign');});
  await page.goto(info.url+'/control/');
  await page.getByRole('button',{name:'Konto',exact:true}).click();
  // Login using the already-created synthetic account (no token in DOM/URL/storage).
  await page.getByLabel('Login',{exact:true}).fill('browser.pg');
  await page.getByLabel('Hasło',{exact:true}).fill('synthetic-memory-owner-password-32chars');
  await page.getByRole('button',{name:'Zaloguj się',exact:true}).click();
  await page.getByRole('heading',{name:'Pulpit',exact:true,level:1}).waitFor();
  await page.getByRole('button',{name:'Otwórz menu',exact:true}).click();await page.getByRole('link',{name:'Pamięć',exact:true}).click();
  await page.getByRole('button',{name:'Pamięć i profile PostgreSQL',exact:true}).click();
  await page.getByRole('button',{name:'Notatki PostgreSQL',exact:true}).click();
  await page.getByLabel('Treść notatki PostgreSQL',{exact:true}).fill('BROWSER PG NOTE <img src=x onerror=bad()>');
  await page.getByRole('button',{name:'Dodaj rekord PostgreSQL',exact:true}).click();
  await page.getByText('BROWSER PG NOTE <img src=x onerror=bad()>',{exact:true}).waitFor();
  assert.equal(await page.locator('.memory-feature img').count(),0);
  await page.getByRole('button',{name:'Wybierz do rozmowy',exact:true}).click();
  await page.getByRole('button',{name:'Edytuj rekord',exact:true}).click();
  await page.getByLabel('Treść notatki PostgreSQL',{exact:true}).fill('BROWSER PG NOTE corrected');
  await page.getByRole('button',{name:'Zapisz korektę PostgreSQL',exact:true}).click();await page.getByText('BROWSER PG NOTE corrected',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Historia rewizji',exact:true}).click();await page.getByRole('heading',{name:'Historia zapisanych rewizji',exact:true}).waitFor();
  assert.equal(await page.locator('.memory-details blockquote').count(),2);
  await page.getByRole('button',{name:'Nowy wybór rozmowy',exact:true}).click();
  await page.getByRole('button',{name:'Wybierz do rozmowy',exact:true}).click();
  await page.getByRole('button',{name:'Profile odpowiedzi',exact:true}).click();
  await page.getByLabel('Nazwa profilu',{exact:true}).fill('Profil browser');await page.getByLabel('Instrukcje odpowiedzi',{exact:true}).fill('PROFILE BROWSER STYLE');
  await page.getByRole('button',{name:'Dodaj rekord PostgreSQL',exact:true}).click();await page.getByText('PROFILE BROWSER STYLE',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Wybierz do rozmowy',exact:true}).click();await page.getByRole('button',{name:'Utwórz rozmowę PostgreSQL',exact:true}).click();
  await page.getByLabel('Wiadomość z kontekstem PostgreSQL',{exact:true}).fill('Browser question');await page.getByRole('button',{name:'Wyślij z kontekstem PostgreSQL',exact:true}).click();
  await page.getByText('Synthetic private answer 1',{exact:true}).waitFor();
  await page.getByLabel('Wiadomość z kontekstem PostgreSQL',{exact:true}).fill('Follow-up');await page.getByRole('button',{name:'Wyślij z kontekstem PostgreSQL',exact:true}).click();await page.getByText('Synthetic private answer 2',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Edytuj rekord',exact:true}).click();await page.getByLabel('Instrukcje odpowiedzi',{exact:true}).fill('CHANGED PROFILE');await page.getByRole('button',{name:'Zapisz korektę PostgreSQL',exact:true}).click();await page.getByText('CHANGED PROFILE',{exact:true}).waitFor();
  await page.getByLabel('Wiadomość z kontekstem PostgreSQL',{exact:true}).fill('Must be refused');await page.getByRole('button',{name:'Wyślij z kontekstem PostgreSQL',exact:true}).click();await page.getByRole('alert').waitFor();assert.equal(await page.getByRole('button',{name:'Wyślij z kontekstem PostgreSQL',exact:true}).isDisabled(),true);
  await page.getByRole('button',{name:'Odśwież PostgreSQL',exact:true}).click();await page.getByText('CHANGED PROFILE',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Usuń rekord',exact:true}).click();await page.getByRole('button',{name:'Potwierdź usunięcie rekordu',exact:true}).click();await page.getByText('CHANGED PROFILE',{exact:true}).waitFor({state:'hidden'});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.equal(await page.evaluate(token=>JSON.stringify({l:{...localStorage},s:{...sessionStorage},url:location.href}).includes(token),info.token),false);
  await page.screenshot({path:'docs/evals/control-m34-mobile.png',fullPage:true});
  await page.setViewportSize({width:1440,height:1100});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.equal(await page.evaluate(()=>{const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);return new Set(ids).size===ids.length;}),true);
  await page.screenshot({path:'docs/evals/control-m34-desktop.png',fullPage:true});
  await page.getByRole('button',{name:'Wyloguj',exact:true}).click();await page.getByRole('heading',{name:'Połącz się z JARVIS OS',exact:true}).waitFor();assert.equal((await page.textContent('body')).includes('PROFILE BROWSER'),false);
  assert.deepEqual(issues,[]);assert.deepEqual(foreign,[]);console.log('PASS actual Chromium/Core/PG: CRUD/history/pin/two-turns/stale-profile/mobile/privacy');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});

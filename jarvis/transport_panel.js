/* Separate laboratory caller/owner channels. No carrier or external calls. */
(function(root){
'use strict';
function mountTransportPanel(container,options){
 const {api,el,card,button}=options;
 if(typeof api!=='function'||typeof el!=='function'||typeof card!=='function'||typeof button!=='function')throw Error('Transport panel UI dependencies are required');
 const fetcher=options.fetch||fetch,eventId=options.eventId||(()=>crypto.randomUUID());
 const base='telephony/transport/calls';
 let disposed=false,busy=false,generation=0,id=options.id||null,owner=null,caller=null,token=null,calls=[];
 const pendingFetches=new Set();
 const ownerCard=card('Transport · kanał właściciela','Laboratorium transportu: oddzielna decyzja właściciela i kanał klienta. Nie wykonuje prawdziwych połączeń, nie aktywuje Play i nie wysyła powiadomień.');
 const callerCard=card('Transport · kanał klienta','Ta część używa wyłącznie ograniczonego tokenu tej rozmowy. Nie otrzymuje klucza właściciela ani jego prywatnego podsumowania.');
 const commandCard=card('Transport · komendy symulacji','Widok właściciela. Dostarczenie komend symuluje osobne kanały i most rozmowy; nie łączy z operatorem.');
 const ownerNotice=el('p',''),callerNotice=el('p','Brak tokenu klienta. Utwórz rozmowę albo odnów token dla wybranej.'),ownerState=el('div'),callerState=el('div'),commandState=el('div');
 const picker=el('select');picker.setAttribute('aria-label','Rozmowa transportu');
 picker.setAttribute('class','transport-picker');
 const phone=el('input');phone.type='tel';phone.placeholder='Opcjonalny numer testowego klienta +48…';phone.setAttribute('aria-label','Numer testowego klienta');
 const text=el('textarea');text.maxLength=4000;text.placeholder='Wypowiedź testowego klienta';text.setAttribute('aria-label','Tekst klienta transportu');
 const clientLog=el('div');clientLog.setAttribute('aria-live','polite');
 const ownerPath=()=>base+'/'+encodeURIComponent(id);
 const alive=g=>!disposed&&g===generation;
 const waiting=()=>owner&&['waiting','owner_pending','waiting_owner'].includes(owner.state)&&owner.attempt_id&&owner.offer_delivered===true;
 const clientReady=()=>!!token&&!!caller&&caller.state==='reception';
 const labels={reception:'Recepcja',waiting:'Oczekiwanie na właściciela',owner_pending:'Oczekiwanie na właściciela',waiting_owner:'Oczekiwanie na właściciela',bridge_pending:'Oczekiwanie na most w symulacji',bridged_lab:'Połączono w laboratorium',connected_lab:'Połączono w laboratorium',ended:'Zakończono'};
 function data(value){return el('pre',JSON.stringify(value,null,2));}
 function setNotice(error){
  if(error?.name==='AbortError')return;
  if(error?.channel==='caller')callerNotice.textContent=error.status===401||error.status===403?'Token klienta jest niedostępny lub wygasł. Właściciel może go odnowić.':'Nie udało się wykonać operacji klienta. Odśwież stan; nie ponawiam automatycznie.';
  else ownerNotice.textContent='Nie udało się wykonać operacji właściciela. Odśwież stan i sprawdź konfigurację telefonii; nie ponawiam automatycznie.';
 }
 async function callerRequest(method='GET',body){
  if(!id||!token)throw Object.assign(Error('Caller token unavailable'),{channel:'caller',status:401});
  const abort=new AbortController();pendingFetches.add(abort);
  const callId=id,callToken=token;
  try{
   const response=await fetcher('/api/telephony/transport/caller/'+encodeURIComponent(callId)+(method==='POST'?'/events':''),{
    method,signal:abort.signal,headers:{'X-Jarvis-Call-Token':callToken,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})
   });
   if(!response.ok)throw Object.assign(Error('Caller request failed'),{channel:'caller',status:response.status});
   return await response.json();
  }finally{pendingFetches.delete(abort);}
 }
 async function refreshOwner(g){
  if(!id)return;
  const snapshot=await api(ownerPath());
  if(!alive(g))return;
  if(!snapshot||snapshot.id!==id||!Number.isInteger(snapshot.revision))throw Error('Invalid owner snapshot');
  owner=snapshot;
 }
 async function refreshCaller(g){
  if(!id||!token){caller=null;return;}
  const snapshot=await callerRequest();
  if(!alive(g))return;
  if(!snapshot||snapshot.id!==id||!Number.isInteger(snapshot.revision)||!Array.isArray(snapshot.messages))throw Object.assign(Error('Invalid public snapshot'),{channel:'caller'});
  // Retain only the public fields used by this card, even if a server fixture
  // accidentally sends extra internal fields.
  caller={id:snapshot.id,revision:snapshot.revision,state:snapshot.state,messages:snapshot.messages.filter(m=>m&&typeof m.text==='string').map(m=>({id:m.id,text:m.text}))};
  callerNotice.textContent='Token klienta jest tylko w pamięci tej karty. Kanał nie ma uprawnień właściciela.';
 }
 async function refresh(g){await refreshOwner(g);if(alive(g))await refreshCaller(g);}
 async function loadCalls(g){
  const result=await api(base);
  if(!alive(g))return;
  calls=Array.isArray(result)?result:result?.calls||[];
  picker.replaceChildren();
  const blank=el('option','Wybierz rozmowę');blank.value='';picker.append(blank);
  for(const call of calls){if(!call||typeof call.id!=='string')continue;const item=el('option',call.id+' · '+(labels[call.state]||'Stan laboratoryjny'));item.value=call.id;picker.append(item);}
  picker.value=id||'';
 }
 function render(){
  if(disposed)return;
  picker.disabled=phone.disabled=create.disabled=refreshButton.disabled=busy;
  rotate.disabled=busy||!owner||owner.state==='ended';
  finish.disabled=busy||!owner||owner.state==='ended';
  removeEnded.disabled=busy||!owner||owner.state!=='ended';
  accept.disabled=decline.disabled=noAnswer.disabled=busy||!waiting();
  dispatch.disabled=busy||!owner||!(owner.commands||[]).some(c=>c.status==='pending');
  text.disabled=send.disabled=busy||!clientReady();
  for(const preset of presets)preset.disabled=busy||!clientReady();
  hangup.disabled=busy||!token||!caller||caller.state==='ended';
  ownerState.replaceChildren();commandState.replaceChildren();callerState.replaceChildren();clientLog.replaceChildren();
  if(owner){
   for(const option of picker.children)if(option.value===owner.id)option.textContent=owner.id+' · '+(labels[owner.state]||'Stan laboratoryjny');
   ownerState.append(el('p','Stan właściciela: '+(labels[owner.state]||owner.state)+' · rewizja '+owner.revision));
   if(owner.state==='waiting_owner'&&!owner.offer_delivered)ownerState.append(el('p','Dostarcz komendy symulacji, aby przekazać właścicielowi prywatne podsumowanie przed decyzją.'));
   if(waiting())ownerState.append(el('p','Właściciel może przyjąć bieżącą próbę. Backend ponownie sprawdzi dostępność, limit i termin oczekiwania.'));
   else ownerState.append(el('p','Brak oczekującej decyzji. Jeżeli prośba jest zablokowana, sprawdź zapisane godziny, DND i wyjątki w Telefonii.'));
   ownerState.append(el('h4','Prywatne podsumowanie dla właściciela'),owner.owner_briefing?data(owner.owner_briefing):el('p','Nie ma prywatnego podsumowania.'));
   commandState.append(el('p','Próby kontaktu: '+String(owner.attempts??0)+' · koszt symulowany: '+String(owner.simulated_cost_units??0)+' jednostek. Nie naliczono opłat operatora.'),el('h4','Limity laboratorium'),data(owner.limits||{}));
   for(const command of (owner.commands||[]).slice(-100))commandState.append(el('p',String(command.channel)+' · '+String(command.kind)+' · '+String(command.status)),data(command.payload||{}));
  }else ownerState.append(el('p','Utwórz albo wybierz laboratoryjną rozmowę.'));
  if(caller){callerState.append(el('p','Stan klienta: '+(labels[caller.state]||'Stan laboratoryjny')+' · rewizja '+caller.revision));for(const message of caller.messages.slice(-100))clientLog.append(el('p',message.text));}
  else callerState.append(el('p','Kanał klienta nie został otwarty.'));
 }
 function perform(operation){return async()=>{
  if(disposed||busy)return;
  busy=true;const g=generation;ownerNotice.textContent='';render();
  try{await operation(g);}catch(error){if(alive(g))setNotice(error);}
  finally{if(alive(g)){busy=false;render();}}
 };}
 async function ownerAction(action,g){
  if(!id||!owner)throw Error('Select a call first');
  const body={event_id:eventId(),revision:owner.revision,action};
  if(['accept','decline','no_answer'].includes(action))body.attempt_id=owner.attempt_id;
  const snapshot=await api(ownerPath()+'/events','POST',body);
  if(!alive(g))return;
  owner=snapshot;
  if(typeof snapshot.caller_token==='string'&&snapshot.caller_token){token=snapshot.caller_token;caller=null;}
  else if(action==='rotate_caller_token'){token=null;caller=null;callerNotice.textContent='Token nie został zwrócony. Odśwież stan i odnów token ponownie, jeśli chcesz otworzyć kanał klienta.';}
  await refresh(g);
 }
 const create=button('Utwórz rozmowę transportu',perform(async g=>{
  const snapshot=await api(base,'POST',{event_id:eventId(),...(phone.value.trim()?{caller:phone.value.trim()}:{})});
  if(!alive(g))return;
  if(!snapshot||typeof snapshot.id!=='string'||!Number.isInteger(snapshot.revision))throw Error('Invalid created call');
  const next=g;id=snapshot.id;owner=snapshot;caller=null;token=typeof snapshot.caller_token==='string'?snapshot.caller_token:null;
  busy=true;callerNotice.textContent=token?'Token klienta jest tylko w pamięci tej karty.':'Odtworzono utworzenie bez zwracania tokenu. Odnów token, aby otworzyć kanał klienta.';
  await loadCalls(next);if(alive(next))await refresh(next);
  if(alive(next)){busy=false;render();}
 }));
 const refreshButton=button('Odśwież transport',perform(async g=>{await loadCalls(g);if(alive(g))await refresh(g);}));
 const rotate=button('Odnów token klienta',perform(g=>ownerAction('rotate_caller_token',g)));
 const accept=button('Przyjmij rozmowę · właściciel',perform(g=>ownerAction('accept',g)));
 const decline=button('Odmów rozmowy · właściciel',perform(g=>ownerAction('decline',g)));
 const noAnswer=button('Brak odpowiedzi · test',perform(g=>ownerAction('no_answer',g)));
 const finish=button('Zakończ transport · właściciel',perform(g=>ownerAction('finish',g)));
 const removeEnded=button('Usuń zakończony test',perform(async g=>{
  await api(ownerPath(),'DELETE');
  if(!alive(g))return;
  id=null;owner=caller=token=null;text.value='';
  callerNotice.textContent='Zakończony test usunięto razem z danymi recepcji i tokenem klienta.';
  render();
  await loadCalls(g);
 }));
 const dispatch=button('Dostarcz komendy · symulacja',perform(g=>ownerAction('dispatch',g)));
 const send=button('Wyślij tekst klienta',perform(async g=>{
  if(!caller||!text.value.trim())throw Object.assign(Error('Customer text required'),{channel:'caller'});
  await callerRequest('POST',{event_id:eventId(),revision:caller.revision,action:'turn',text:text.value});
  if(alive(g)){text.value='';await refresh(g);}
 }));
 const hangup=button('Rozłącz klienta · test',perform(async g=>{
  if(!caller)throw Object.assign(Error('Caller unavailable'),{channel:'caller'});
  await callerRequest('POST',{event_id:eventId(),revision:caller.revision,action:'hangup'});
  if(alive(g))await refresh(g);
 }));
 const presets=[
  ['Przykład: pierwsza prośba','Proszę o rozmowę z właścicielem.'],
  ['Przykład: ponowienie i odmowa pomocy','Ponownie proszę o właściciela i odrzucam pomoc asystenta.'],
  ['Przykład: kryzys po naprawie','Po naprawie nie działają hamulce.']
 ].map(([label,value])=>button(label,async()=>{if(!disposed&&!busy)text.value=value;}));
 picker.onchange=perform(async g=>{
  const selected=picker.value;const next=g;id=selected||null;owner=caller=token=null;
  callerNotice.textContent='Token klienta nie jest zapisany. Odnów token wybranej rozmowy, aby sprawdzić kanał klienta.';
  render();
  if(id)await refreshOwner(next);
  if(alive(next)){busy=false;render();}
 });
 ownerCard.append(phone,create,picker,refreshButton,rotate,ownerNotice,ownerState,accept,decline,noAnswer,finish,removeEnded);
 callerCard.append(callerNotice,callerState,clientLog,text,...presets,send,hangup);
 commandCard.append(dispatch,commandState);
 container.append(ownerCard,callerCard,commandCard);
 render();
 const ready=perform(async g=>{await loadCalls(g);if(alive(g)&&id)await refreshOwner(g);})();
 return {ready,dispose(){if(disposed)return;disposed=true;generation++;token=null;caller=owner=null;id=null;text.value='';phone.value='';for(const abort of pendingFetches)abort.abort();pendingFetches.clear();ownerState.replaceChildren();callerState.replaceChildren();clientLog.replaceChildren();commandState.replaceChildren();callerNotice.textContent='Kanał klienta zamknięty; token usunięto z pamięci panelu.';}};
}
if(typeof module!=='undefined'&&module.exports)module.exports=mountTransportPanel;
if(root)root.mountJarvisTransportPanel=mountTransportPanel;
})(typeof window!=='undefined'?window:null);

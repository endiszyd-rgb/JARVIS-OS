/* Owner-activated voice UI. Transcripts are reviewed by default. */
(function(root){
'use strict';
function mountVoicePanel(container,options){
 const {el,card,button,api,getKey,voiceStatus,catalog}=options;
 const fetcher=options.fetch||fetch,makeURL=options.URL||URL;
 const panel=card('Rozmowa przez mikrofon','Po uruchomieniu wypowiedzi trafiają do skonfigurowanego STT, potem do wybranego czatu i syntezy mowy. Domyślnie sprawdzasz tekst przed wysłaniem. Mikrofon jest wyłączany podczas przetwarzania i odtwarzania.');
 const seconds=el('input');seconds.type='number';seconds.min='5';seconds.max='300';seconds.value='30';seconds.setAttribute('aria-label','Koniec sesji po ciszy, sekundy');
 const threshold=el('input');threshold.type='number';threshold.min='0.001';threshold.max='0.5';threshold.step='0.001';threshold.value='0.015';threshold.setAttribute('aria-label','Próg głośności');
 const model=el('select');for(const item of catalog.models||[]){const o=el('option',item.provider==='demo'?'DEMO — odpowiedź testowa':item.name+(item.cloud?' · CHMURA':''));o.value=JSON.stringify({provider:item.provider,name:item.name});model.append(o);}
 const initial=(catalog.models||[]).find(m=>m.provider===catalog.default_provider&&(m.provider==='demo'||m.provider==='openai'||m.name===catalog.default_ollama_model))||(catalog.models||[])[0];
 if((catalog.models||[]).some(m=>m.cloud))panel.append(el('p','Model chmurowy wysyła transkrypcje i historię głosową do usługi zewnętrznej. Pamięć osobista nie jest dołączana do rozmów głosowych.'));
 if(initial)model.value=JSON.stringify({provider:initial.provider,name:initial.name});
 const review=el('input');review.type='checkbox';review.checked=true;review.id='voice-review';
 const reviewLabel=el('label','Sprawdzaj tekst przed wysłaniem (zalecane)');reviewLabel.htmlFor=review.id;
 const state=el('p','Mikrofon wyłączony.'),log=el('div'),reviewBox=el('div'),draft=el('textarea');reviewBox.hidden=true;
 draft.maxLength=8000;draft.setAttribute('aria-label','Sprawdź rozpoznaną wypowiedź');
 let conversation=null,pendingReview=null,disposed=false,player=null,playURL=null,playAbort=null;
 const current=()=>!disposed;
 function appendLog(node){log.append(node);while(log.children.length>50)log.removeChild(log.firstChild);}
 function settleReview(text,error){const pending=pendingReview;pendingReview=null;reviewBox.hidden=true;if(!pending)return;pending.signal.removeEventListener('abort',pending.abort);if(error)pending.reject(error);else pending.resolve(text);}
 function stopPlayback(){
  if(playAbort){const abort=playAbort;playAbort=null;abort();}
  if(player){player.pause();player.removeAttribute('src');player=null;}
  if(playURL){makeURL.revokeObjectURL(playURL);playURL=null;}
  options.stopPlayback?.();
 }
 async function response(path,init,signal){
  const r=await fetcher('/api/'+path,{...init,signal,headers:{'X-Jarvis-Key':getKey(),...(init.headers||{})}});
  if(!r.ok)throw Error('Nie powiodło się żądanie głosowe: '+r.status);
  return r;
 }
 function playback(blob,signal){return new Promise((resolve,reject)=>{
  stopPlayback();
  if(signal.aborted){reject(Object.assign(Error('Anulowano odtwarzanie'),{name:'AbortError'}));return;}
  if(!blob||!Number.isFinite(blob.size)||blob.size<44||blob.size>4*1024*1024+44){reject(Error('Niepoprawne nagranie odpowiedzi'));return;}
  const audio=el('audio');player=audio;playURL=makeURL.createObjectURL(blob);audio.src=playURL;
  let done=false;
  const finish=error=>{if(done)return;done=true;signal.removeEventListener('abort',aborted);if(playAbort===aborted)playAbort=null;audio.onended=audio.onerror=null;audio.pause();audio.removeAttribute('src');if(player===audio)player=null;if(playURL){makeURL.revokeObjectURL(playURL);playURL=null;}error?reject(error):resolve();};
  const aborted=()=>finish(Object.assign(Error('Anulowano odtwarzanie'),{name:'AbortError'}));playAbort=aborted;
  signal.addEventListener('abort',aborted,{once:true});audio.onended=()=>finish();audio.onerror=()=>finish(Error('Nie można odtworzyć odpowiedzi'));
  try{Promise.resolve(audio.play()).catch(error=>finish(error));}catch(error){finish(error);}
 });}
 function reviewTranscript(text,signal){return new Promise((resolve,reject)=>{
  if(disposed||signal.aborted){reject(Object.assign(Error('Anulowano sprawdzanie'),{name:'AbortError'}));return;}
  draft.value=text;reviewBox.hidden=false;
  const abort=()=>settleReview(null,Object.assign(Error('Anulowano sprawdzanie'),{name:'AbortError'}));
  pendingReview={resolve,reject,signal,abort};signal.addEventListener('abort',abort,{once:true});
 });}
 const stages={starting:'Uruchamianie sesji i mikrofonu…',listening:'Słucham. Możesz mówić.',processing:'Kończę nagranie…',transcribing:'Rozpoznaję wypowiedź…',reviewing:'Sprawdź tekst i wybierz „Wyślij tekst” albo „Pomiń”.',chatting:'Czekam na odpowiedź…',synthesizing:'Przygotowuję mowę…',speaking:'Odtwarzam odpowiedź. Możesz ją przerwać.',stopped:'Sesja zakończona. Mikrofon wyłączony.',error:'Sesja przerwana po błędzie. Mikrofon wyłączony.'};
 async function start(){
  if(disposed)return;
  if(conversation?.active)throw Error('Najpierw zakończ bieżącą rozmowę.');
  if(!voiceStatus.enabled||!voiceStatus.stt_configured||!voiceStatus.tts_configured)throw Error('Włącz i skonfiguruj lokalne STT oraz TTS przed rozmową.');
  const silence=Number(seconds.value),energy=Number(threshold.value);
  if(!Number.isInteger(silence)||silence<5||silence>300)throw Error('Wybierz od 5 do 300 sekund ciszy.');
  if(!Number.isFinite(energy)||energy<0.001||energy>0.5)throw Error('Wybierz próg głośności od 0.001 do 0.5.');
  const selected=JSON.parse(model.value),withReview=review.checked;
  conversation?.dispose();settleReview(null);stopPlayback();log.replaceChildren();
  const instance=new (options.Conversation||root.JarvisAudioConversation)({
   createController:o=>new root.JarvisAudioSession({...o,request:api}),
   createCapture:o=>new root.JarvisPcmCapture({...o,threshold:energy,activityIntervalMs:Math.min(1000,silence*1000/3)}),
   transcribe:async(wav,signal)=>(await response('voice/transcribe',{method:'POST',headers:{'Content-Type':'audio/wav'},body:wav},signal)).json(),
   chat:async(text,sessionId,signal)=>(await response('chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,input_mode:'voice',do_not_remember:true,model:selected.provider,model_name:selected.name,...(sessionId?{session_id:sessionId}:{})})},signal)).json(),
   synthesize:async(text,signal)=>(await response('voice/synthesize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})},signal)).blob(),
   play:playback,stopPlayback,
   ...(withReview?{reviewTranscript}:{}),
   onState:s=>{if(current()&&conversation===instance){state.textContent=stages[s.stage]||'Sesja głosowa.';if(!s.active){settleReview(null);model.disabled=seconds.disabled=threshold.disabled=review.disabled=false;}}},
   onTranscript:text=>{if(current()&&conversation===instance)appendLog(el('p','Rozpoznano: '+text));},
   onReply:(reply,meta)=>{if(current()&&conversation===instance){appendLog(el('p',(reply.ai_generated===false?'DEMO: ':'JARVIS: ')+reply.reply));if(meta.truncated)appendLog(el('p','Odczytuję pierwsze 1000 znaków; pełna odpowiedź jest powyżej.'));}},
   onError:error=>{if(current()&&conversation===instance)state.textContent='Rozmowa przerwana. '+(error.message.includes('timed out')?'Przekroczono czas oczekiwania. ':'')+'Sprawdź konfigurację usług i uprawnienia mikrofonu. Nie ponawiam żądania automatycznie.';}
  });
  conversation=instance;model.disabled=seconds.disabled=threshold.disabled=review.disabled=true;
  try{await instance.start(silence);}finally{if(!instance.active)model.disabled=seconds.disabled=threshold.disabled=review.disabled=false;}
 }
 reviewBox.append(draft,button('Wyślij tekst',async()=>{if(!draft.value.trim())throw Error('Wpisz treść albo wybierz Pomiń.');settleReview(draft.value);}),button('Pomiń wypowiedź',async()=>settleReview(null)));
 panel.append(el('label','Model rozmowy'),model,reviewLabel,review,el('p','Wyłączenie sprawdzania uruchamia eksperymentalne automatyczne wysyłanie rozpoznanej mowy. Transkrypcja może być błędna. Nie wykonuje poleceń ani nie zapisuje pamięci; historia rozmowy pozostaje.'),
  el('label','Koniec sesji po ciszy (sekundy)'),seconds,el('label','Próg głośności — wyżej oznacza mniej reakcji na szum'),threshold,
  state,button('Rozpocznij rozmowę głosową',start),button('Przerwij odpowiedź',async()=>{if(!conversation)throw Error('Najpierw rozpocznij rozmowę.');await conversation.interrupt();}),
  button('Zakończ rozmowę',async()=>conversation?.stop()),button('Anuluj rozmowę',async()=>conversation?.cancel()),
  el('p','Zakończ także słowami „koniec rozmowy”, „zakończ rozmowę” lub „stop Jarvis”. Poziom dźwięku może reagować na hałas warsztatu. Podczas odpowiedzi mikrofon jest wyłączony; przerwanie działa przyciskiem.'),reviewBox,log);
 container.append(panel);
 return {get active(){return !!conversation?.active;},dispose(){if(disposed)return;disposed=true;conversation?.dispose();settleReview(null,Object.assign(Error('Zamknięto widok'),{name:'AbortError'}));stopPlayback();}};
}
if(typeof module!=='undefined'&&module.exports)module.exports=mountVoicePanel;
if(root)root.mountJarvisVoicePanel=mountVoicePanel;
})(typeof window!=='undefined'?window:null);

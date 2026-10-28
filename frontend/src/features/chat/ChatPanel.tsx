import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { MessageSquare, Plus, RefreshCw, Send, Square } from 'lucide-react'
import { ApiError } from '../../api'
import { createSession, getMessages, getModels, getSession, getSessions, MESSAGE_PAGE, modelKey, sendMessage, SESSION_PAGE } from './api'
import type { ChatMessage, ChatSession, ModelCatalog } from './types'
import './chat.css'

export interface ChatPanelProps { credential: string; onUnauthorized: () => void }
function cancelled(error: unknown): boolean { return error instanceof DOMException && error.name === 'AbortError' }
function explanation(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) return 'Wybrany model jest niedozwolony lub limit kosztu nie pozwala na odpowiedź. Sprawdź konfigurację modelu.'
    if (error.status === 409) return 'W tej rozmowie trwa już odpowiedź lub stan rozmowy się zmienił. Odśwież rozmowę przed kolejną wiadomością.'
    if (error.status === 502) return 'Model lub usługa są niedostępne. Odśwież rozmowę, aby sprawdzić zapisany stan.'
    if (error.status === 504) return 'Upłynął limit czasu odpowiedzi. Odśwież rozmowę przed ponowną próbą.'
    return error.message
  }
  return 'Nie udało się odczytać rozmowy. Spróbuj odświeżyć jej stan.'
}

export function ChatPanel(props: ChatPanelProps) {
  return <ChatWorkspace key={props.credential} {...props} />
}

function ChatWorkspace({ credential, onUnauthorized }: ChatPanelProps) {
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null)
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [sessionOffset, setSessionOffset] = useState(0)
  const [listVersion, setListVersion] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selected, setSelected] = useState<ChatSession | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [messageOffset, setMessageOffset] = useState(0)
  const [detailVersion, setDetailVersion] = useState(0)
  const [choice, setChoice] = useState('')
  const [title, setTitle] = useState('')
  const [draft, setDraft] = useState('')
  const [doNotRemember, setDoNotRemember] = useState(false)
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [creating, setCreating] = useState(false)
  const [sending, setSending] = useState(false)
  const [needsSync, setNeedsSync] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const callback = useRef(onUnauthorized)
  callback.current = onUnauthorized
  const selectedRef = useRef(selectedId)
  selectedRef.current = selectedId
  const choiceRef = useRef(choice)
  choiceRef.current = choice
  const expired = useRef(false)
  const controllers = useRef(new Set<AbortController>())
  const write = useRef<AbortController | null>(null)
  const writeEpoch = useRef(0)
  const mounted = useRef(true)

  const handleFailure = useCallback((failure: unknown) => {
    if (cancelled(failure) || expired.current || !mounted.current) return
    if (failure instanceof ApiError && failure.status === 401) {
      expired.current = true
      controllers.current.forEach(controller => controller.abort())
      ++writeEpoch.current
      setSessions([]); setMessages([]); setSelected(null); setSelectedId(null); setCatalog(null)
      setDraft(''); setNotice(null); setError(null)
      callback.current()
    } else setError(explanation(failure))
  }, [])

  useEffect(() => {
    mounted.current = true; expired.current = false
    return () => {
      mounted.current = false; ++writeEpoch.current
      controllers.current.forEach(controller => controller.abort())
      controllers.current.clear(); write.current = null
    }
  }, [credential])

  useEffect(() => {
    const controller = new AbortController()
    controllers.current.add(controller)
    getModels(credential, controller.signal).then(result => {
      if (controller.signal.aborted || expired.current || !mounted.current) return
      setCatalog(result)
      if (!choiceRef.current) {
        const defaultModel = result.models.find(item => item.provider === result.default_provider && (item.provider === 'demo' || item.provider === 'openai' || item.name === result.default_ollama_model)) || result.models[0]
        if (defaultModel) setChoice(modelKey(defaultModel))
      }
    }).catch(failure => { if (!controller.signal.aborted) handleFailure(failure) }).finally(() => controllers.current.delete(controller))
    return () => controller.abort()
  }, [credential, handleFailure])

  useEffect(() => {
    const controller = new AbortController()
    controllers.current.add(controller); setLoadingList(true)
    getSessions(credential, sessionOffset, controller.signal).then(rows => {
      if (controller.signal.aborted || expired.current || !mounted.current) return
      setSessions(rows)
      if (!selectedRef.current && rows.length) setSelectedId(rows[0].id)
    }).catch(failure => { if (!controller.signal.aborted) handleFailure(failure) }).finally(() => {
      controllers.current.delete(controller)
      if (!controller.signal.aborted && mounted.current) setLoadingList(false)
    })
    return () => controller.abort()
  }, [credential, sessionOffset, listVersion, handleFailure])

  useEffect(() => {
    if (!selectedId) return
    const controller = new AbortController()
    controllers.current.add(controller); setLoadingDetail(true); setError(null)
    setSelected(null); setMessages([])
    Promise.all([getSession(credential, selectedId, controller.signal), getMessages(credential, selectedId, messageOffset, controller.signal)]).then(([session, rows]) => {
      if (controller.signal.aborted || expired.current || !mounted.current) return
      setSelected(session); setMessages(rows); setChoice(modelKey({ provider: session.provider, name: session.model_name })); setNeedsSync(false)
      if (session.active_turn) setNotice('Serwer nadal przetwarza odpowiedź. Sprawdź ponownie stan rozmowy; nie wysyłaj jej ponownie.')
    }).catch(failure => { if (!controller.signal.aborted) handleFailure(failure) }).finally(() => {
      controllers.current.delete(controller)
      if (!controller.signal.aborted && mounted.current) setLoadingDetail(false)
    })
    return () => controller.abort()
  }, [credential, selectedId, messageOffset, detailVersion, handleFailure])

  const selectedModel = catalog?.models.find(item => modelKey(item) === choice)
  const busy = sending || creating
  const readonly = selected?.input_mode === 'voice'
  const canSend = Boolean(selected && selectedModel && !readonly && !selected.active_turn && !needsSync && !loadingDetail && !busy && draft.trim() && draft.length <= 8000)

  function selectSession(id: string) {
    if (busy) return
    setSelected(null); setSelectedId(id); setMessageOffset(0); setDraft(''); setError(null); setNotice(null)
    setDetailVersion(value => value + 1)
  }
  async function newSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedModel || busy) return
    const controller = new AbortController(), id = ++writeEpoch.current
    controllers.current.add(controller); write.current = controller
    setCreating(true); setError(null)
    try {
      const session = await createSession(credential, title.trim() || 'Nowa rozmowa', selectedModel, controller.signal)
      if (controller.signal.aborted || id !== writeEpoch.current || !mounted.current || expired.current) return
      setTitle(''); setDraft(''); setSelectedId(session.id); setMessageOffset(0); setSessionOffset(0); setListVersion(value => value + 1)
      setNeedsSync(false); setNotice(null)
    } catch (failure) { handleFailure(failure) }
    finally {
      controllers.current.delete(controller)
      if (id === writeEpoch.current && mounted.current) { setCreating(false); write.current = null }
    }
  }
  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSend || !selected || !selectedModel) return
    const controller = new AbortController(), id = ++writeEpoch.current
    controllers.current.add(controller); write.current = controller
    setSending(true); setError(null); setNotice(null)
    try {
      const result = await sendMessage(credential, selected.id, draft, selectedModel, doNotRemember, controller.signal)
      if (controller.signal.aborted || id !== writeEpoch.current || !mounted.current || expired.current) return
      setDraft(''); setNeedsSync(false)
      if (result.proposal) setNotice('Utworzono propozycję zmiany. Wymaga osobnego zatwierdzenia w odpowiednim panelu.')
      else if (result.model === 'parser') setNotice('Wykonano lokalne polecenie tekstowe. Zapis pamięci i propozycje można sprawdzić w odpowiednich panelach.')
      else if (result.ai_generated === false || result.model === 'demo') setNotice('To odpowiedź demonstracyjna, bez inferencji modelu AI.')
      setMessageOffset(Math.floor(Math.max(0, (selected.message_count || 0) + 1) / MESSAGE_PAGE) * MESSAGE_PAGE)
      setDetailVersion(value => value + 1); setListVersion(value => value + 1)
    } catch (failure) {
      if (controller.signal.aborted || id !== writeEpoch.current || !mounted.current || expired.current) return
      setNeedsSync(true); handleFailure(failure)
    } finally {
      controllers.current.delete(controller)
      if (id === writeEpoch.current && mounted.current) { setSending(false); write.current = null }
    }
  }
  function stopWaiting() {
    if (!sending || !write.current) return
    write.current.abort(); write.current = null; ++writeEpoch.current
    setSending(false); setNeedsSync(true)
    setNotice('Przerwano oczekiwanie w tej karcie. Serwer mógł nadal przetwarzać wiadomość. Odśwież rozmowę, aby sprawdzić jej zapisany stan przed kolejną próbą.')
  }
  function refreshConversation() {
    if (busy) return
    setError(null); setNotice(null); setDetailVersion(value => value + 1); setListVersion(value => value + 1)
  }

  return <div className="chat-workspace">
    <section className="panel chat-sidebar" aria-labelledby="chat-sessions-title">
      <h2 id="chat-sessions-title"><MessageSquare aria-hidden="true" /> Historia rozmów</h2>
      <form className="chat-new" onSubmit={event => { void newSession(event) }}>
        <div><label htmlFor="chat-title">Tytuł nowej rozmowy</label><input id="chat-title" value={title} maxLength={120} onChange={event => setTitle(event.target.value)} disabled={busy} placeholder="Nowa rozmowa" /></div>
        <button className="button secondary" type="submit" disabled={!selectedModel || busy}><Plus aria-hidden="true" />Nowa rozmowa</button>
      </form>
      {loadingList && <p className="chat-load" role="status">Odczytywanie sesji…</p>}
      {!loadingList && sessions.length === 0 && <p className="chat-caption">Brak rozmów na tej stronie.</p>}
      <ul className="chat-session-list">{sessions.map(item => <li key={item.id}><button type="button" className="chat-session-button" aria-label={item.title} aria-current={item.id === selectedId ? 'true' : undefined} disabled={busy} onClick={() => selectSession(item.id)}><span className="chat-session-title">{item.title}</span><span className="chat-session-meta" aria-hidden="true">{item.input_mode === 'voice' ? 'Głos' : 'Tekst'} · {item.provider === 'demo' ? 'DEMO' : item.model_name}{item.active_turn ? ' · odpowiedź w toku' : ''}</span></button></li>)}</ul>
      <div className="chat-pagination"><button className="button subtle" type="button" disabled={busy || loadingList || sessionOffset === 0} onClick={() => setSessionOffset(value => Math.max(0, value - SESSION_PAGE))}>Poprzednie rozmowy</button><button className="button subtle" type="button" disabled={busy || loadingList || sessions.length < SESSION_PAGE} onClick={() => setSessionOffset(value => value + SESSION_PAGE)}>Następne rozmowy</button></div>
      <p className="chat-caption">Lista po {SESSION_PAGE} sesji. Sesje głosowe są dostępne tylko do odczytu.</p>
    </section>
    <section className="panel chat-thread" aria-label="Rozmowa tekstowa">
      <div className="chat-thread-heading"><div><h2>{selected?.title || (selectedId ? 'Odczytywanie rozmowy' : 'Wybierz rozmowę')}</h2><p className="chat-caption">Zapisana historia jednej sesji.</p></div><button className="button secondary" type="button" onClick={refreshConversation} disabled={busy || loadingDetail || !selectedId}><RefreshCw aria-hidden="true" />Odśwież rozmowę</button></div>
      <div className="chat-model"><label htmlFor="chat-model">Model rozmowy</label><select id="chat-model" value={choice} disabled={!catalog || busy || loadingDetail || readonly} onChange={event => setChoice(event.target.value)}>
        {!selectedModel && choice && <option value={choice} disabled>Model sesji poza bieżącym katalogiem</option>}
        {!catalog && <option value="">Odczytywanie katalogu…</option>}
        {catalog?.models.map(item => <option key={modelKey(item)} value={modelKey(item)}>{item.provider === 'demo' ? 'DEMO' : item.provider === 'openai' ? 'OpenAI' : 'Ollama'} · {item.name}{item.cloud ? ' · chmura' : ''}</option>)}
      </select><p className="chat-caption">Lista pochodzi z konfiguracji właściciela, nie potwierdza instalacji ani dostępności modeli. Wybór nie pobiera modelu. DEMO rozpoznaje także lokalne polecenia zapisu pamięci i tworzenia propozycji.</p></div>
      {selectedModel?.cloud && <p className="chat-notice">Wiadomości i historia tej sesji trafią do chmury. Rozmowy tekstowe mogą zawierać pamięć osobistą.</p>}
      {error && <div className="app-error" role="alert">{error}</div>}
      {notice && <p className="chat-notice" role="status">{notice}</p>}
      {readonly && <p className="chat-notice">Otwarta sesja głosowa — tylko odczyt.</p>}
      {needsSync && <p className="chat-notice">Przed następną wiadomością użyj „Odśwież rozmowę”. Nie ponawiam wysłania automatycznie.</p>}
      {loadingDetail ? <p className="chat-load" role="status">Odczytywanie historii…</p> : <ol className="chat-messages" aria-label="Wiadomości rozmowy">{messages.map(item => <li key={item.id} className={'chat-message ' + item.role}><div className="chat-message-meta"><strong>{item.role === 'user' ? 'Ty' : 'JARVIS'}</strong><span>{item.state === 'pending' ? 'W trakcie' : item.state === 'failed' ? 'Nieudana próba' : 'Zapisano'}</span></div><p className="chat-message-content">{item.content}</p></li>)}</ol>}
      {!selectedId && <p className="chat-empty">Utwórz nową rozmowę lub wybierz zapisaną sesję.</p>}
      {selected && <div className="chat-pagination"><button className="button subtle" type="button" disabled={busy || loadingDetail || messageOffset === 0} onClick={() => setMessageOffset(value => Math.max(0, value - MESSAGE_PAGE))}>Poprzednie wiadomości</button><p>{messages.length ? `${messageOffset + 1}–${messageOffset + messages.length}` : '0'} / {selected.message_count ?? '—'} wiadomości</p><button className="button subtle" type="button" disabled={busy || loadingDetail || messages.length < MESSAGE_PAGE} onClick={() => setMessageOffset(value => value + MESSAGE_PAGE)}>Kolejne wiadomości</button></div>}
      <form className="chat-compose" onSubmit={event => { void send(event) }}>
        <label htmlFor="chat-message">Wiadomość</label><textarea id="chat-message" value={draft} maxLength={8000} disabled={!selected || readonly || busy || loadingDetail} onChange={event => setDraft(event.target.value)} placeholder={readonly ? 'Sesja głosowa jest tylko do odczytu' : 'Napisz wiadomość…'} />
        <label className="chat-checkbox"><input type="checkbox" checked={doNotRemember} disabled={busy || readonly} onChange={event => setDoNotRemember(event.target.checked)} />Nie zapisuj w pamięci</label>
        <div className="chat-compose-actions"><small>{draft.length} / 8000 znaków</small>{sending ? <button className="button secondary" type="button" onClick={stopWaiting}><Square aria-hidden="true" />Przestań czekać</button> : <button className="button primary" type="submit" disabled={!canSend}><Send aria-hidden="true" />Wyślij wiadomość</button>}</div>
      </form>
    </section>
  </div>
}

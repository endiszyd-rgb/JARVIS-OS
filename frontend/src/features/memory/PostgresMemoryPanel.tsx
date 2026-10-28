import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, apiRequest } from '../../api'
import { base, messages, pgStatus, route, row, rows, sessionCreate, uuid, versions } from './postgresApi'
import type { Kind, RecordRow, Session, Version } from './postgresApi'
interface Props { credential: string; onUnauthorized: () => void }
function Editor({ credential, onUnauthorized }: Props) {
  const [status, setStatus] = useState<{ enabled: boolean; version: number | null } | null>(null)
  const [kind, setKind] = useState<Kind>('notes'), [scopeDraft, setScopeDraft] = useState(''), [scope, setScope] = useState('')
  const [offset, setOffset] = useState(0), [items, setItems] = useState<RecordRow[]>([])
  const [editing, setEditing] = useState<RecordRow | null>(null), [content, setContent] = useState(''), [name, setName] = useState('')
  const [history, setHistory] = useState<Version[] | null>(null), [deleting, setDeleting] = useState<RecordRow | null>(null)
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [uncertain, setUncertain] = useState(false)
  const [profile, setProfile] = useState<RecordRow | null>(null), [notes, setNotes] = useState<RecordRow[]>([])
  const [session, setSession] = useState<Session | null>(null), [model, setModel] = useState('ollama')
  const [chat, setChat] = useState<{ role: string; content: string }[]>([]), [question, setQuestion] = useState(''), [cloud, setCloud] = useState(false)
  const epoch = useRef(0), pending = useRef<AbortController | null>(null), active = useRef(false)
  const unauthorized = useRef(onUnauthorized); unauthorized.current = onUnauthorized
  function clearEditor() { setEditing(null); setContent(''); setName(''); setHistory(null); setDeleting(null) }
  function clearConversation() { setSession(null); setProfile(null); setNotes([]); setChat([]); setQuestion(''); setCloud(false) }
  async function run<T>(job: (signal: AbortSignal) => Promise<T>, apply: (value: T) => void, mutation = false) {
    if (active.current) return
    active.current = true; const id = ++epoch.current, c = new AbortController(); pending.current = c
    setBusy(true); setError('')
    try { const value = await job(c.signal); if (id === epoch.current && !c.signal.aborted) apply(value) }
    catch (e) {
      if (id !== epoch.current || c.signal.aborted) return
      if (e instanceof ApiError && e.status === 401) { setItems([]); clearEditor(); clearConversation(); setStatus(null); unauthorized.current() }
      else {
        if (mutation) setUncertain(true)
        setError((e instanceof ApiError && e.status === 409 ? 'Rewizja lub źródła rozmowy zmieniły się. Utwórz nową rozmowę albo odśwież dane.' : e instanceof ApiError ? e.message : 'Nie można odczytać danych.') + (mutation ? ' Sprawdź stan przed ponowieniem. Brak automatycznych powtórek.' : ''))
      }
    } finally { if (id === epoch.current) { active.current = false; setBusy(false); pending.current = null } }
  }
  useEffect(() => {
    void run(signal => pgStatus(credential, signal), setStatus)
    return () => { ++epoch.current; pending.current?.abort(); active.current = false }
  }, [credential])
  const ready = status?.enabled && (status.version ?? 0) >= 4
  const load = (signal: AbortSignal, k = kind, s = scope, page = offset) => rows(credential, signal, k, s, page)
  function refresh(k = kind, s = scope, page = offset) {
    setItems([]); clearEditor()
    void run(signal => load(signal, k, s, page), value => { setItems(value); setKind(k); setScope(s); setOffset(page); setUncertain(false) })
  }
  function submit(e: FormEvent) {
    e.preventDefault(); if (!content.trim() || uncertain || busy) return
    const body = kind === 'profiles' ? { name, instructions: content } : { content, category: editing?.category ?? 'note', source: editing?.source ?? 'manual', source_id: editing?.source_id ?? '' }
    void run(async signal => {
      row(await apiRequest(route(kind, editing?.id), signal, credential, { method: editing ? 'PATCH' : 'POST', body: { ...body, ...(editing ? { revision: editing.revision } : scope ? { workshop_id: scope } : {}) } }), kind)
      return load(signal)
    }, value => { setItems(value); clearEditor() }, true)
  }
  function start() {
    void run(signal => sessionCreate(credential, signal, { model, ...(scope ? { workshop_id: scope } : {}), ...(profile ? { profile_ref: { id: profile.id, revision: profile.revision } } : {}) }), value => { setSession(value); setChat([]); setCloud(false); setUncertain(false) }, true)
  }
  function ask(e: FormEvent) {
    e.preventDefault(); if (!session || busy || uncertain) return
    const s = session
    void run(async signal => {
      await apiRequest(base + '/conversations/' + s.id + '/turns', signal, credential, { method: 'POST', timeoutMs: 95_000, body: { revision: s.revision, message: question, memory_refs: notes.map(n => ({ id: n.id, revision: n.revision })), allow_cloud_context: cloud } })
      return messages(credential, signal, s)
    }, value => { setSession({ ...s, revision: value.revision }); setChat(value.messages); setQuestion(''); setCloud(false) }, true)
  }
  return <section className="panel memory-feature" aria-labelledby="pg-title" aria-busy={busy}>
    <h2 id="pg-title" className="panel-heading">Pamięć PostgreSQL i profile</h2>
    <p className="panel-description">Dane prywatne są przypisane do konta. Zakres warsztatowy wymaga członkostwa. Ten panel korzysta z osobnej pamięci i historii rozmów.</p>
    {error && <p role="alert" className="app-error">{error}</p>}
    {!status && <button className="button secondary" disabled={busy} onClick={() => { void run(signal => pgStatus(credential, signal), setStatus) }}>Sprawdź dostępność PostgreSQL</button>}
    {status && !ready && <p role="status">{status.enabled ? 'Panel wymaga aktualizacji schematu pamięci do wersji 4.' : 'Pamięć PostgreSQL jest wyłączona. Włączenie wymaga konfiguracji serwera.'}</p>}
    {ready && <>
      <form className="memory-note-form" onSubmit={e => { e.preventDefault(); if (!scopeDraft || uuid(scopeDraft)) { clearConversation(); refresh(kind, scopeDraft, 0) } }}>
        <div className="form-field"><label htmlFor="pg-scope">Zakres danych: UUID warsztatu</label><input id="pg-scope" value={scopeDraft} maxLength={36} disabled={busy} onChange={e => setScopeDraft(e.target.value)} /><small>Puste pole oznacza wyłącznie Twoje dane prywatne. Identyfikator warsztatu otrzymasz od administratora.</small></div>
        <button className="button secondary" disabled={busy || !!scopeDraft && !uuid(scopeDraft)}>Odczytaj zakres</button>
      </form>
      <p className="memory-caption">Aktualny zakres: {scope || 'Prywatny'}. Strona {offset / 20 + 1}, do 20 rekordów.</p>
      <div className="memory-actions"><button className="button secondary" disabled={busy} onClick={() => refresh('notes', scope, 0)}>Notatki PostgreSQL</button><button className="button secondary" disabled={busy} onClick={() => refresh('profiles', scope, 0)}>Profile odpowiedzi</button><button className="button subtle" disabled={busy} onClick={() => refresh()}>Odśwież PostgreSQL</button></div>
      <ol className="memory-list" aria-label={kind === 'notes' ? 'Notatki PostgreSQL' : 'Profile odpowiedzi'}>{items.map(item => <li key={item.id} className="memory-note">
        <p className="memory-note-text">{item.name ?? item.content}</p><p>Rewizja {item.revision}</p>{item.instructions && <p className="memory-note-text">{item.instructions}</p>}
        <div className="memory-actions">
          <button className="button secondary" disabled={busy || uncertain} onClick={() => { clearEditor(); setEditing(item); setContent(item.instructions ?? item.content ?? ''); setName(item.name ?? '') }}>Edytuj rekord</button>
          <button className="button subtle" disabled={busy} onClick={() => { clearEditor(); void run(signal => versions(credential, signal, kind, item.id), setHistory) }}>Historia rewizji</button>
          <button className="button subtle" disabled={busy || uncertain} onClick={() => setDeleting(item)}>Usuń rekord</button>
          <button className="button subtle" disabled={busy || !!session || (kind === 'notes' && notes.length >= 5)} onClick={() => kind === 'profiles' ? setProfile(item) : setNotes(prev => prev.some(n => n.id === item.id) ? prev : [...prev, item])}>Wybierz do rozmowy</button>
        </div>
      </li>)}</ol>
      <div className="memory-actions"><button className="button subtle" disabled={busy || offset === 0} onClick={() => refresh(kind, scope, offset - 20)}>Poprzednia strona</button><button className="button subtle" disabled={busy || items.length < 20} onClick={() => refresh(kind, scope, offset + 20)}>Następna strona</button></div>
      {history && <div className="memory-details"><h3>Historia zapisanych rewizji</h3><p>Do 100 wersji. Wcześniejsze wersje sprzed włączenia historii mogą być niedostępne.</p><ol>{history.map(v => <li key={v.revision}>Rewizja {v.revision}<blockquote>{v.name} {v.content ?? v.instructions}</blockquote></li>)}</ol></div>}
      {deleting && <div className="memory-confirm" role="group" aria-label="Potwierdzenie usunięcia PostgreSQL"><p>Usunąć rekord i treści jego historii? Kopie zapasowe i wcześniejsze odpowiedzi AI mogą nadal zawierać dane. Rozmowy korzystające ze źródła przestaną działać.</p><button className="button secondary" disabled={busy || uncertain} onClick={() => { const d = deleting; void run(async signal => { await apiRequest(route(kind, d.id) + '?revision=' + d.revision, signal, credential, { method: 'DELETE' }); return load(signal) }, value => { setItems(value); clearEditor() }, true) }}>Potwierdź usunięcie rekordu</button><button className="button subtle" disabled={busy} onClick={() => setDeleting(null)}>Zachowaj rekord</button></div>}
      <form className="memory-note-form" onSubmit={submit}><h3>{editing ? `Korekta, rewizja ${editing.revision}` : kind === 'notes' ? 'Nowa notatka PostgreSQL' : 'Nowy profil odpowiedzi'}</h3>
        {kind === 'profiles' && <div className="form-field"><label htmlFor="pg-name">Nazwa profilu</label><input id="pg-name" required maxLength={100} disabled={busy || uncertain} value={name} onChange={e => setName(e.target.value)} /></div>}
        <div className="form-field"><label htmlFor="pg-content">{kind === 'notes' ? 'Treść notatki PostgreSQL' : 'Instrukcje odpowiedzi'}</label><textarea id="pg-content" required maxLength={kind === 'notes' ? 8000 : 4000} disabled={busy || uncertain} value={content} onChange={e => setContent(e.target.value)} /></div>
        <div className="memory-actions"><button className="button primary" disabled={busy || uncertain || !content.trim()}>{editing ? 'Zapisz korektę PostgreSQL' : 'Dodaj rekord PostgreSQL'}</button><button className="button subtle" type="button" disabled={busy} onClick={clearEditor}>Wyczyść edytor</button></div>
      </form>
      <section aria-labelledby="pg-chat-title"><h3 id="pg-chat-title">Rozmowa z wybranym profilem i pamięcią</h3><p>Profil: {profile ? `${profile.name}, rewizja ${profile.revision}` : 'bez profilu'}. Wybranych notatek: {notes.length}/5. Profil i zakres są stałe w sesji. Korekta źródła wymaga nowej rozmowy.</p>
        {!session && <><div className="form-field"><label htmlFor="pg-model">Dostawca nowej rozmowy</label><select id="pg-model" value={model} disabled={busy} onChange={e => setModel(e.target.value)}><option value="ollama">Ollama — model skonfigurowany na serwerze</option><option value="openai">OpenAI — chmura, wymaga aktywacji i budżetu</option></select></div><button className="button primary" disabled={busy || uncertain} onClick={start}>Utwórz rozmowę PostgreSQL</button></>}
        <button className="button subtle" disabled={busy} onClick={() => { clearConversation(); setUncertain(false) }}>Nowy wybór rozmowy</button>
        {session && <><p className="memory-caption">Sesja {session.id}, rewizja {session.revision}. Domyślnie wygasa po 60 minutach.</p><button className="button subtle" disabled={busy} onClick={() => { void run(signal => messages(credential, signal, session), v => { setChat(v.messages); setSession({ ...session, revision: v.revision }); setUncertain(false) }) }}>Sprawdź historię rozmowy</button>
          <ol className="memory-list" aria-label="Rozmowa PostgreSQL">{chat.map((m, i) => <li key={i}><strong>{m.role === 'user' ? 'Ty' : 'JARVIS'}</strong><p className="memory-note-text">{m.content}</p></li>)}</ol>
          <form className="memory-note-form" onSubmit={ask}><div className="form-field"><label htmlFor="pg-question">Wiadomość z kontekstem PostgreSQL</label><textarea id="pg-question" required maxLength={8000} value={question} disabled={busy || uncertain} onChange={e => setQuestion(e.target.value)} /></div>
            {session.provider === 'openai' && <label className="memory-check"><input type="checkbox" checked={cloud} disabled={busy} onChange={e => setCloud(e.target.checked)} />Zgadzam się wysłać wybrany profil, notatki, historię i wiadomość do OpenAI w tej turze.</label>}
            <button className="button primary" disabled={busy || uncertain || !question.trim() || session.provider === 'openai' && !cloud}>Wyślij z kontekstem PostgreSQL</button>
          </form><button className="button subtle" disabled={busy} onClick={() => { void run(signal => apiRequest(base + '/conversations/' + session.id + '?revision=' + session.revision, signal, credential, { method: 'DELETE' }), clearConversation, true) }}>Usuń bieżącą sesję PostgreSQL</button>
        </>}
      </section>
    </>}
  </section>
}
export function PostgresMemoryPanel(props: Props) { return <Editor key={props.credential} {...props} /> }

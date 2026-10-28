import { PostgresMemoryPanel } from './PostgresMemoryPanel'
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { CircleAlert, Database, RefreshCw } from 'lucide-react'
import { ApiError } from '../../api'
import { addNote, CATEGORIES, correctNote, deleteNote, readHistory, readNotes, readOrigins, readPolicy, retention, savePolicy } from './api'
import type { Category, HistoryRow, MemoryNote, MemoryPolicy, OriginRow, PolicySnapshot, RetentionPreview } from './api'
import './memory.css'

interface Props { credential: string; onUnauthorized: () => void }
interface Editing { id: string; revision: number; text: string; category: Category; conflict: boolean }
const labels: Record<Category, string> = { preferences: 'Preferencje', equipment: 'Sprzęt', projects: 'Projekty', decisions: 'Decyzje', working_style: 'Sposób pracy', manual: 'Ręczne' }
const date = (value: number) => new Date(value * 1000).toLocaleString('pl-PL')
const clonePolicy = (policy: MemoryPolicy): MemoryPolicy => ({ ...policy, categories: [...policy.categories] })

function MemoryEditor({ credential, onUnauthorized }: Props) {
  const [notes, setNotes] = useState<MemoryNote[]>([])
  const [policy, setPolicy] = useState<PolicySnapshot | null>(null)
  const [draftPolicy, setDraftPolicy] = useState<MemoryPolicy | null>(null)
  const [policyConflict, setPolicyConflict] = useState(false)
  const [query, setQuery] = useState('')
  const [newText, setNewText] = useState('')
  const [newCategory, setNewCategory] = useState<Category>('manual')
  const [editing, setEditing] = useState<Editing | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [details, setDetails] = useState<{ id: string; kind: 'history'; rows: HistoryRow[] } | { id: string; kind: 'origins'; rows: OriginRow[] } | null>(null)
  const [preview, setPreview] = useState<{ value: RetentionPreview; revision: number } | null>(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const active = useRef(false)
  const epoch = useRef(0)
  const pending = useRef<AbortController | null>(null)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized

  function clearPrivate() {
    setNotes([]); setPolicy(null); setDraftPolicy(null); setEditing(null); setDeleting(null)
    setDetails(null); setPreview(null); setNewText(''); setQuery(''); setNotice(null)
  }
  function failed(failure: unknown, mutation: boolean) {
    if (failure instanceof ApiError && failure.status === 401) { clearPrivate(); unauthorized.current(); return }
    if (failure instanceof ApiError && failure.status === 409) {
      if (editing) setEditing({ ...editing, conflict: true })
      setPolicyConflict(true)
      setError('Nie zapisano zmiany: dane lub zasady zapisu zmieniły się. Odśwież pamięć i sprawdź bieżące wartości przed kolejną zmianą.')
      return
    }
    const message = failure instanceof ApiError ? failure.message : 'Nie udało się wykonać żądania.'
    setError(message + (mutation ? ' Wynik operacji może wymagać sprawdzenia. Odśwież pamięć przed ponowieniem; żądania nie są ponawiane automatycznie.' : ''))
  }
  async function run<T>(job: (signal: AbortSignal) => Promise<T>, apply: (result: T) => void, mutation = false) {
    if (active.current) return
    active.current = true
    const controller = new AbortController(), id = ++epoch.current
    pending.current = controller
    setBusy(true); setError(null); setNotice(null)
    try {
      const result = await job(controller.signal)
      if (id === epoch.current && !controller.signal.aborted) apply(result)
    } catch (failure) { if (id === epoch.current && !controller.signal.aborted) failed(failure, mutation) }
    finally {
      if (id === epoch.current && !controller.signal.aborted) { setBusy(false); active.current = false; pending.current = null }
    }
  }
  const load = (signal: AbortSignal) => Promise.all([readNotes(credential, signal), readPolicy(credential, signal)])
  const loaded = ([rows, saved]: [MemoryNote[], PolicySnapshot]) => {
    setNotes(rows); setPolicy(saved); setDraftPolicy(clonePolicy(saved.policy)); setPolicyConflict(false)
    setEditing(null); setDeleting(null); setDetails(null); setPreview(null)
  }

  useEffect(() => {
    void run(load, loaded)
    return () => { ++epoch.current; pending.current?.abort(); pending.current = null; active.current = false }
  }, [credential])

  function submitNew(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!newText.trim() || busy || !policy?.policy.enabled) return
    void run(async signal => { await addNote(credential, signal, { text: newText, category: newCategory }); return load(signal) }, result => {
      loaded(result); setNewText(''); setNotice('Notatka została zapisana.')
    }, true)
  }
  function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editing || !editing.text.trim() || editing.conflict || busy) return
    const changed = editing
    void run(async signal => { await correctNote(credential, signal, changed.id, { text: changed.text, category: changed.category, revision: changed.revision }); return load(signal) }, result => {
      loaded(result); setNotice('Korekta została zapisana z nową rewizją.')
    }, true)
  }
  function confirmDelete(id: string) {
    void run(async signal => { await deleteNote(credential, signal, id); return load(signal) }, result => {
      loaded(result); setNotice('Notatka oraz powiązana historia zostały usunięte. Starsze kopie zapasowe mogą nadal zawierać te dane.')
    }, true)
  }
  function changePolicy(next: MemoryPolicy) { setDraftPolicy(next); setPreview(null) }
  function submitPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!policy || !draftPolicy || policyConflict || busy) return
    void run(async signal => { await savePolicy(credential, signal, policy.revision, draftPolicy); return load(signal) }, result => {
      loaded(result); setNotice('Zasady pamięci zostały zapisane z nową rewizją.')
    }, true)
  }
  function previewRetention() {
    if (!policy || busy) return
    void run(async signal => {
      const latest = await readPolicy(credential, signal)
      return { value: await retention(credential, signal, true), revision: latest.revision }
    }, value => { setPreview(value) })
  }
  function executeRetention() {
    if (!preview || busy) return
    const expected = preview
    void run(async signal => {
      const latest = await readPolicy(credential, signal)
      if (latest.revision !== expected.revision) throw new ApiError(409)
      const result = await retention(credential, signal, false)
      return { result, state: await load(signal) }
    }, value => { loaded(value.state); setNotice(`Retencja zakończona. Usunięto ${value.result.count} notatek. Starsze kopie zapasowe mogą nadal zawierać usunięte dane.`) }, true)
  }

  const filtered = notes.filter(note => !query.trim() || note.text.toLocaleLowerCase('pl').includes(query.trim().toLocaleLowerCase('pl')))
  const policyDirty = !!policy && !!draftPolicy && JSON.stringify(policy.policy) !== JSON.stringify(draftPolicy)
  const categorySelect = (id: string, value: Category, change: (value: Category) => void, disabled = false) => <div className="form-field"><label htmlFor={id}>Kategoria</label><select id={id} value={value} disabled={busy || disabled} onChange={event => change(event.target.value as Category)}>{CATEGORIES.map(item => <option key={item} value={item}>{labels[item]}</option>)}</select></div>

  return <div className="memory-feature">
    {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div>}
    {notice && <p className="memory-notice" role="status">{notice}</p>}
    <section className="panel" aria-labelledby="memory-list-title" aria-busy={busy}>
      <div className="memory-toolbar"><div><h2 className="panel-heading" id="memory-list-title"><Database aria-hidden="true" />Notatki osobiste</h2><p className="panel-description">Do 100 najnowszych notatek w tej instalacji. Dane są wspólne dla kont właściciela.</p></div><button className="button secondary" type="button" disabled={busy} onClick={() => { void run(load, loaded) }}><RefreshCw aria-hidden="true" />Odśwież pamięć</button></div>
      <div className="form-field"><label htmlFor="memory-query">Filtruj notatki</label><input id="memory-query" maxLength={200} value={query} onChange={event => setQuery(event.target.value)} /><small>Filtr obejmuje wyłącznie pobrane notatki, maksymalnie 100. Wyszukiwanie semantyczne i indeksowanie pozostają dostępne w <a href="/">poprzednim panelu</a>.</small></div>
      <p className="memory-caption" aria-live="polite">{busy ? 'Odczytywanie pamięci…' : `Pokazano ${filtered.length} z ${notes.length} pobranych notatek.`}</p>
      {!busy && !filtered.length && <p className="memory-caption">Brak notatek pasujących do tego odczytu.</p>}
      <ol className="memory-list" aria-label="Pobrane notatki">{filtered.map(note => <li key={note.id} className="memory-note">
        <p className="memory-note-text">{note.text}</p><p className="memory-caption">{labels[note.category]} · Źródło: {note.source} · Rewizja: {note.revision} · {date(note.updated)}</p>
        {editing?.id === note.id ? <form className="memory-note-form" onSubmit={submitEdit}><div className="form-field"><label htmlFor="memory-edit">Treść korekty</label><textarea id="memory-edit" required maxLength={4000} disabled={busy || editing.conflict} value={editing.text} onChange={event => setEditing({ ...editing, text: event.target.value })} /></div>{categorySelect('memory-edit-category', editing.category, category => setEditing({ ...editing, category }), editing.conflict)}<div className="memory-actions"><button type="submit" className="button primary" disabled={busy || editing.conflict || !editing.text.trim()}>Zapisz korektę</button><button type="button" className="button subtle" disabled={busy} onClick={() => setEditing(null)}>Anuluj korektę</button></div></form> : <div className="memory-actions"><button type="button" className="button secondary" disabled={busy || !policy?.policy.enabled} onClick={() => { setEditing({ id: note.id, text: note.text, category: note.category, revision: note.revision, conflict: false }); setDeleting(null); setDetails(null) }}>Edytuj notatkę</button><button type="button" className="button subtle" disabled={busy} onClick={() => { void run(signal => readHistory(credential, signal, note.id), rows => setDetails({ id: note.id, kind: 'history', rows })) }}>Historia korekt</button><button type="button" className="button subtle" disabled={busy} onClick={() => { void run(signal => readOrigins(credential, signal, note.id), rows => setDetails({ id: note.id, kind: 'origins', rows })) }}>Źródła notatki</button><button type="button" className="button subtle" disabled={busy} onClick={() => { setDeleting(note.id); setEditing(null) }}>Usuń notatkę</button></div>}
        {deleting === note.id && <div className="memory-confirm" role="group" aria-label="Potwierdzenie usunięcia notatki"><p>Usunąć tę notatkę, historię korekt i źródła? Ta operacja nie usuwa starszych kopii zapasowych.</p><div className="memory-actions"><button type="button" className="button secondary" disabled={busy} onClick={() => confirmDelete(note.id)}>Potwierdź usunięcie</button><button type="button" className="button subtle" disabled={busy} onClick={() => setDeleting(null)}>Zachowaj notatkę</button></div></div>}
        {details?.id === note.id && <div className="memory-details"><h3>{details.kind === 'history' ? 'Historia korekt notatki' : 'Źródła automatycznego zapisu'}</h3>{!details.rows.length && <p className="memory-caption">Brak zapisanych szczegółów.</p>}<ol>{details.kind === 'history' ? details.rows.slice(0, 100).map(row => <li key={row.revision}>Rewizja {row.revision} · {date(row.created)} · {labels[row.category]} · {row.source}<blockquote>{row.text}</blockquote></li>) : details.rows.slice(0, 100).map(row => <li key={row.revision}>Rewizja {row.revision} · {date(row.created)} · {row.extractor}<blockquote>{row.quote}</blockquote>Sesja: {row.session_id} · Tura: {row.turn_id} · {row.session_available ? 'Sesja źródłowa dostępna' : 'Sesja źródłowa usunięta'}</li>)}</ol>{details.rows.length > 100 && <p className="memory-caption">Podgląd pokazuje pierwsze 100 z {details.rows.length} wpisów.</p>}</div>}
      </li>)}</ol>
    </section>
    <section className="panel" aria-labelledby="memory-add-title"><h2 className="panel-heading" id="memory-add-title">Dodaj do pamięci</h2><p className="panel-description">Zapis dotyczy Twojej osobistej notatki. Nie umieszczaj tu sekretów ani danych klientów.</p>{policy && !policy.policy.enabled && <p className="memory-caption">Zapis i korekty są wyłączone w zapisanych zasadach pamięci.</p>}<form className="memory-note-form" onSubmit={submitNew}><div className="form-field"><label htmlFor="memory-new">Nowa notatka</label><textarea id="memory-new" maxLength={4000} required disabled={busy || !policy?.policy.enabled} value={newText} onChange={event => setNewText(event.target.value)} /></div>{categorySelect('memory-new-category', newCategory, setNewCategory, !policy?.policy.enabled)}<div className="memory-actions"><button type="submit" className="button primary" disabled={busy || !policy?.policy.enabled || !newText.trim()}>Dodaj notatkę</button></div></form></section>
    {policy && draftPolicy && <section className="panel" aria-labelledby="memory-policy-title"><h2 className="panel-heading" id="memory-policy-title">Zasady pamięci</h2><p className="panel-description">Rewizja {policy.revision}. Automatyczny zapis rozpoznaje wybrane polskie deklaracje, bez skanowania historii. Dane recepcji pozostają osobno.</p><form className="memory-policy-form" onSubmit={submitPolicy}>
      <label className="memory-check"><input type="checkbox" checked={draftPolicy.enabled} disabled={busy} onChange={event => changePolicy({ ...draftPolicy, enabled: event.target.checked })} />Zezwalaj na zapis i korekty notatek</label>
      <div className="form-field"><label htmlFor="memory-policy-mode">Tryb pamięci</label><select id="memory-policy-mode" value={draftPolicy.mode} disabled={busy} onChange={event => changePolicy({ ...draftPolicy, mode: event.target.value as MemoryPolicy['mode'] })}><option value="manual">Ręczny</option><option value="auto">Automatyczny — wspierane deklaracje</option></select></div>
      <fieldset className="memory-categories"><legend>Kategorie automatycznej pamięci</legend>{CATEGORIES.map(item => <label className="memory-check" key={item}><input type="checkbox" checked={draftPolicy.categories.includes(item)} disabled={busy} onChange={event => changePolicy({ ...draftPolicy, categories: event.target.checked ? [...draftPolicy.categories, item] : draftPolicy.categories.filter(value => value !== item) })} />{labels[item]}</label>)}</fieldset>
      <div className="form-field"><label htmlFor="memory-retention-days">Retencja w dniach</label><input id="memory-retention-days" type="number" min={1} max={3650} step={1} disabled={busy} value={draftPolicy.retention_days ?? ''} onChange={event => changePolicy({ ...draftPolicy, retention_days: event.target.value === '' ? null : Number(event.target.value) })} /><small>Puste pole oznacza brak limitu. Zapis zasad nie usuwa notatek. Retencję uruchamiasz osobno.</small></div>
      <div className="memory-actions"><button className="button primary" type="submit" disabled={busy || policyConflict || !policyDirty}>Zapisz zasady pamięci</button></div>
    </form><p className="memory-caption">Aktualnie zapisany automatyczny zapis: {policy.automatic_extraction_active ? 'aktywny' : 'wyłączony'}. Zwrot „nie zapamiętuj” blokuje zapis. Sekrety, dane płatnicze i klientów są wykluczone z automatycznej ekstrakcji.</p>
    <div className="memory-actions"><button className="button secondary" type="button" disabled={busy || policyDirty || policyConflict} onClick={previewRetention}>Podgląd retencji</button></div>
    {preview && <div className="memory-confirm" role="group" aria-label="Podgląd retencji"><p>Podgląd: {preview.value.count} notatek starszych niż {preview.value.retention_days === null ? 'nieustawiony limit' : `${preview.value.retention_days} dni`}. Wykonanie ponownie przeliczy dane według zapisanych zasad; liczba może się zmienić. To nie jest rezerwacja tego zestawu danych.</p><p>Usunięte zostaną również powiązane historie i źródła. Starsze kopie zapasowe mogą zachować dane.</p><div className="memory-actions"><button type="button" className="button secondary" disabled={busy || policyDirty || policyConflict || preview.value.retention_days === null} onClick={executeRetention}>Wykonaj retencję</button><button type="button" className="button subtle" disabled={busy} onClick={() => setPreview(null)}>Zamknij podgląd retencji</button></div></div>}
    </section>}
  </div>
}

export function MemoryPanel(props: Props) { return <MemorySections key={props.credential} {...props} /> }
function MemorySections(props: Props) {
  const [pg, setPg] = useState(false)
  return <><div className="memory-actions"><button className="button secondary" onClick={() => setPg(false)}>Pamięć instalacji SQLite</button><button className="button secondary" onClick={() => setPg(true)}>Pamięć i profile PostgreSQL</button></div>{pg ? <PostgresMemoryPanel {...props} /> : <MemoryEditor {...props} />}</>
}

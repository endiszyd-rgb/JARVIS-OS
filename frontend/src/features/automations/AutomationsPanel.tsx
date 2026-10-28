import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Bell, Check, CircleAlert, Clock, Eye, RefreshCw, X } from 'lucide-react'
import { ApiError } from '../../api'
import { decideAutomation, proposeAutomation, readAutomations, tickAutomations } from './api'
import type { Automation, AutomationProposal } from './api'
import './automations.css'

export interface AutomationsPanelProps { credential: string; onUnauthorized: () => void }
export function AutomationsPanel(props: AutomationsPanelProps) { return <AutomationsWorkspace key={props.credential} {...props} /> }
const errorText = (failure: unknown) => failure instanceof ApiError && failure.status === 409 ? 'Ta propozycja została już rozstrzygnięta. Sprawdź zapisane przypomnienia i historię działań.' : failure instanceof ApiError ? failure.message : 'Nie udało się wykonać operacji. Sprawdź bieżący stan przed kolejną próbą.'
function AutomationsWorkspace({ credential, onUnauthorized }: AutomationsPanelProps) {
  const [rows, setRows] = useState<Automation[]>([]), [loaded, setLoaded] = useState(false)
  const [title, setTitle] = useState(''), [interval, setInterval] = useState('60'), [message, setMessage] = useState('')
  const [preview, setPreview] = useState<AutomationProposal | null>(null)
  const [busy, setBusy] = useState(false), [authorized, setAuthorized] = useState(true)
  const [error, setError] = useState<string | null>(null), [notice, setNotice] = useState<string | null>(null)
  const pending = useRef<AbortController | null>(null), epoch = useRef(0), callback = useRef(onUnauthorized), expired = useRef(false)
  callback.current = onUnauthorized
  function begin() { pending.current?.abort(); const controller = new AbortController(), id = ++epoch.current; pending.current = controller; setBusy(true); setError(null); setNotice(null); return { controller, id } }
  function valid(id: number, controller: AbortController) { return epoch.current === id && !controller.signal.aborted && !expired.current }
  function failed(failure: unknown, id: number, controller: AbortController) {
    if (!valid(id, controller)) return
    if (failure instanceof ApiError && failure.status === 401) {
      expired.current = true; ++epoch.current; controller.abort(); pending.current = null
      setRows([]); setPreview(null); setTitle(''); setMessage(''); setError(null); setNotice(null); setAuthorized(false); callback.current()
    } else setError(errorText(failure))
  }
  function finish(id: number, controller: AbortController) { if (valid(id, controller)) { setBusy(false); pending.current = null } }
  async function refresh() {
    if (busy) return
    const { controller, id } = begin()
    try { const next = await readAutomations(credential, controller.signal); if (valid(id, controller)) { setRows(next); setLoaded(true) } }
    catch (failure) { failed(failure, id, controller) }
    finally { finish(id, controller) }
  }
  useEffect(() => {
    expired.current = false; void refresh()
    return () => { ++epoch.current; pending.current?.abort(); pending.current = null }
    // The workspace is keyed by its authenticated credential.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credential])
  async function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy || preview) return
    const minutes = Number(interval)
    if (!title.trim() || !message.trim() || !Number.isSafeInteger(minutes) || minutes < 1 || minutes > 525600) { setError('Podaj tytuł, treść i pełną liczbę minut od1 do525600.'); return }
    const { controller, id } = begin()
    try { const proposal = await proposeAutomation(credential, { title: title.trim(), interval_minutes: minutes, message: message.trim() }, controller.signal); if (valid(id, controller)) setPreview(proposal) }
    catch (failure) { failed(failure, id, controller) }
    finally { finish(id, controller) }
  }
  async function decide(approve: boolean) {
    if (busy || !preview) return
    const staged = preview, { controller, id } = begin()
    try {
      await decideAutomation(credential, staged.id, approve, controller.signal)
      if (!valid(id, controller)) return
      setPreview(null)
      if (approve) { setTitle(''); setMessage('') }
      setNotice(approve ? 'Przypomnienie zatwierdzone i zapisane.' : 'Propozycja przypomnienia odrzucona. Nie utworzono automatyzacji.')
      const next = await readAutomations(credential, controller.signal)
      if (valid(id, controller)) { setRows(next); setLoaded(true) }
    } catch (failure) { failed(failure, id, controller) }
    finally { finish(id, controller) }
  }
  async function tick() {
    if (busy) return
    const { controller, id } = begin()
    try {
      const fired = await tickAutomations(credential, controller.signal)
      if (!valid(id, controller)) return
      setNotice(`Lokalne powiadomienia utworzone: ${fired.length}. Nie wysłano żądań zewnętrznych.`)
      const next = await readAutomations(credential, controller.signal)
      if (valid(id, controller)) { setRows(next); setLoaded(true) }
    } catch (failure) { failed(failure, id, controller) }
    finally { finish(id, controller) }
  }
  if (!authorized) return <p role="status">Sesja zakończona. Połącz się ponownie.</p>
  return <div className="automations-feature" aria-busy={busy}>
    {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}{loaded ? ' Lista zawiera poprzedni odczyt.' : ''}</span></div>}
    {notice && <p className="automations-notice" role="status"><Check aria-hidden="true" />{notice}</p>}
    <section className="panel" aria-labelledby="automation-create-title"><h2 className="panel-heading" id="automation-create-title"><Bell aria-hidden="true" />Nowe przypomnienie lokalne</h2><p className="panel-description">Najpierw podgląd, potem osobne zatwierdzenie. Przypomnienia tworzą wpisy w JARVIS; nie wysyłają wiadomości do telefonu ani nie sterują urządzeniami.</p>
      <form className="automations-form" onSubmit={event => { void prepare(event) }}>
        <div className="form-field"><label htmlFor="automation-title">Tytuł przypomnienia</label><input id="automation-title" value={title} maxLength={100} required disabled={busy || preview !== null} onChange={event => setTitle(event.target.value)} /></div>
        <div className="form-field"><label htmlFor="automation-interval">Co ile minut</label><input id="automation-interval" type="number" value={interval} min={1} max={525600} step={1} required disabled={busy || preview !== null} onChange={event => setInterval(event.target.value)} /></div>
        <div className="form-field automations-message"><label htmlFor="automation-message">Treść przypomnienia</label><textarea id="automation-message" value={message} maxLength={2000} required disabled={busy || preview !== null} onChange={event => setMessage(event.target.value)} /></div>
        <button className="button primary" type="submit" disabled={busy || preview !== null}><Eye aria-hidden="true" />Podgląd przypomnienia</button>
      </form>
    </section>
    {preview && <section className="panel automations-preview" aria-labelledby="automation-preview-title"><h2 className="panel-heading" id="automation-preview-title"><Eye aria-hidden="true" />Podgląd przypomnienia</h2><p className="panel-description">Propozycja została zapisana, ale przypomnienie zacznie obowiązywać dopiero po zatwierdzeniu.</p><dl className="automations-preview-list"><div><dt>Tytuł</dt><dd>{preview.payload.title}</dd></div><div><dt>Częstotliwość</dt><dd>Co {preview.payload.interval_minutes} min</dd></div><div><dt>Treść</dt><dd>{preview.payload.message}</dd></div></dl><div className="automations-actions"><button className="button primary" type="button" disabled={busy} onClick={() => { void decide(true) }}><Check aria-hidden="true" />Zatwierdź przypomnienie</button><button className="button secondary" type="button" disabled={busy} onClick={() => { void decide(false) }}><X aria-hidden="true" />Odrzuć przypomnienie</button></div></section>}
    <section className="panel" aria-labelledby="automation-list-title"><div className="automations-heading"><div><h2 className="panel-heading" id="automation-list-title"><Clock aria-hidden="true" />Zapisane przypomnienia</h2><p className="panel-description">Lista wszystkich lokalnych harmonogramów. Termin oznacza najwcześniejszy czas wykonania; potrzebne jest sprawdzenie terminów przez scheduler lub przycisk poniżej.</p></div><button className="button secondary" type="button" disabled={busy} onClick={() => { void refresh() }}><RefreshCw aria-hidden="true" />Odśwież automatyzacje</button></div>
      {!loaded ? <p className="automations-caption" role="status">{busy ? 'Odczytywanie przypomnień…' : 'Lista jest chwilowo niedostępna.'}</p> : rows.length ? <ul className="automations-list">{rows.map(row => <li key={row.id}><h3>{row.payload.title}</h3><p>{row.payload.message}</p><dl><div><dt>Powtarzanie</dt><dd>Co {row.payload.interval_minutes} min</dd></div><div><dt>Następny termin</dt><dd><time dateTime={new Date(row.next_run * 1000).toISOString()}>{new Date(row.next_run * 1000).toLocaleString('pl-PL')}</time></dd></div></dl></li>)}</ul> : <p className="automations-caption">Brak zapisanych przypomnień.</p>}
      <div className="automations-tick"><button className="button secondary" type="button" disabled={busy} onClick={() => { void tick() }}><Clock aria-hidden="true" />Sprawdź terminy teraz</button><p className="automations-caption">Sprawdzenie tworzy lokalne powiadomienia tylko dla terminów, które już upłynęły. Nie uruchamia n8n ani usług zewnętrznych. Ten panel nie potwierdza działania schedulera w tle.</p></div>
    </section>
  </div>
}

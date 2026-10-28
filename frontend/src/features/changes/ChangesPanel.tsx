import { useEffect, useRef, useState } from 'react'
import { ApiError } from '../../api'
import { readSettings, sameSettings } from '../settings/api'
import type { Settings } from '../settings/api'
import { decideProposal, readProposals, rollbackProposal } from './api'
import type { Proposal } from './api'
import './changes.css'
type Props = { credential: string; onUnauthorized: () => void; onStatusChanged?: () => void }
type Review = { row: Proposal; action: 'approve' | 'reject' | 'rollback'; before: Settings | null }
const kinds = { settings: 'Ustawienia', automation: 'Przypomnienie', code: 'Opis zmiany kodu' }
const statuses = { pending: 'Oczekuje na decyzję', applied: 'Zastosowano', rejected: 'Odrzucono', review_required: 'Wymaga przeglądu kodu', rolled_back: 'Cofnięto' }
export function ChangesPanel(props: Props) { return <Workspace key={props.credential} {...props} /> }
function Workspace({ credential, onUnauthorized, onStatusChanged }: Props) {
  const [rows, setRows] = useState<Proposal[]>([]), [busy, setBusy] = useState(false), [loaded, setLoaded] = useState(false)
  const [review, setReview] = useState<Review | null>(null), [filter, setFilter] = useState('all'), [sync, setSync] = useState(false)
  const [error, setError] = useState<string | null>(null), [notice, setNotice] = useState<string | null>(null), [expired, setExpired] = useState(false)
  const pending = useRef<AbortController | null>(null), epoch = useRef(0), mounted = useRef(true), ended = useRef(false)
  const callbacks = useRef({ onUnauthorized, onStatusChanged }); callbacks.current = { onUnauthorized, onStatusChanged }
  const reviewHeading = useRef<HTMLHeadingElement>(null), result = useRef<HTMLParagraphElement>(null)
  const origin = useRef<HTMLButtonElement | null>(null)
  useEffect(() => { if (review) reviewHeading.current?.focus(); else origin.current?.focus() }, [review])
  useEffect(() => { if (notice) result.current?.focus() }, [notice])
  function begin() { pending.current?.abort(); const controller = new AbortController(), id = ++epoch.current; pending.current = controller; setBusy(true); setError(null); setNotice(null); return { controller, id } }
  const valid = (id: number, c: AbortController) => mounted.current && !ended.current && epoch.current === id && !c.signal.aborted
  function fail(e: unknown, id: number, c: AbortController) {
    if (!valid(id, c)) return
    if (e instanceof ApiError && e.status === 401) { ended.current = true; ++epoch.current; c.abort(); setRows([]); setReview(null); setError(null); setNotice(null); setExpired(true); callbacks.current.onUnauthorized() }
    else setError(e instanceof ApiError && e.status === 409 ? 'Stan zmienił się. Odśwież propozycje przed kolejną decyzją.' : e instanceof ApiError ? e.message : 'Nie udało się odczytać propozycji. Odśwież ich stan.')
  }
  function finish(id: number, c: AbortController) { if (valid(id, c)) { setBusy(false); pending.current = null } }
  async function load() {
    const { controller: c, id } = begin(); setReview(null)
    try { const next = await readProposals(credential, c.signal); if (valid(id, c)) { setRows(next); setLoaded(true); setSync(false) } }
    catch (e) { fail(e, id, c) } finally { finish(id, c) }
  }
  useEffect(() => { mounted.current = true; ended.current = false; void load(); return () => { mounted.current = false; ++epoch.current; pending.current?.abort() } }, [credential])
  async function prepare(row: Proposal, action: Review['action']) {
    if (busy || sync) return
    const { controller: c, id } = begin()
    try {
      const latest = await readProposals(credential, c.signal)
      const fresh = latest.find(item => item.id === row.id)
      const before = row.kind === 'settings' ? await readSettings(credential, c.signal) : null
      if (!valid(id, c)) return
      setRows(latest)
      if (!fresh || JSON.stringify(fresh) !== JSON.stringify(row)) { setReview(null); setError('Propozycja zmieniła się. Sprawdź odświeżoną listę.'); return }
      setReview({ row: fresh, action, before })
    } catch (e) { fail(e, id, c) } finally { finish(id, c) }
  }
  async function confirm() {
    if (!review || busy || sync) return
    const staged = review, { controller: c, id } = begin()
    try {
      const latest = await readProposals(credential, c.signal)
      const fresh = latest.find(item => item.id === staged.row.id)
      const current = staged.before ? await readSettings(credential, c.signal) : null
      if (!valid(id, c)) return
      if (!fresh || JSON.stringify(fresh) !== JSON.stringify(staged.row) || staged.before && current && !sameSettings(staged.before, current)) {
        setRows(latest); setReview(null); setError('Stan zmienił się od podglądu. Nie wysłano decyzji; przygotuj nowy podgląd.'); return
      }
      if (staged.action === 'rollback') await rollbackProposal(credential, staged.row, c.signal)
      else await decideProposal(credential, staged.row, staged.action === 'approve', c.signal)
      if (!valid(id, c)) return
      setReview(null); setSync(true)
      const next = await readProposals(credential, c.signal)
      if (!valid(id, c)) return
      setRows(next); setSync(false)
      setNotice(staged.action === 'rollback' ? 'Zmiana została cofnięta.' : staged.action === 'reject' ? 'Propozycja została odrzucona.' : staged.row.kind === 'code' ? 'Opis skierowano do przeglądu. Nie wykonano kodu.' : 'Zmiana została zatwierdzona.')
      callbacks.current.onStatusChanged?.()
    } catch (e) { if (valid(id, c)) { setReview(null); setSync(true) }; fail(e, id, c) } finally { finish(id, c) }
  }
  if (expired) return <p role="status">Sesja zakończona. Połącz się ponownie.</p>
  return <div className="changes-feature" aria-busy={busy}>
    {error && <p className="app-error" role="alert">{error}</p>}
    {notice && <p className="changes-notice" role="status" ref={result} tabIndex={-1}>{notice}</p>}
    {sync && <p role="status">Wynik wymaga sprawdzenia. Odśwież listę; nie ponawiamy operacji automatycznie.</p>}
    {review && <section className="panel changes-review" aria-labelledby="changes-review-title">
      <h2 id="changes-review-title" ref={reviewHeading} tabIndex={-1}>Potwierdzenie decyzji</h2>
      <p>{review.action === 'rollback' ? 'Cofnięcie zastosowanej zmiany' : review.action === 'reject' ? 'Odrzucenie propozycji' : 'Zatwierdzenie propozycji'} · {kinds[review.row.kind]}</p>
      {review.before && <><h3>Bieżące ustawienia</h3><pre>{JSON.stringify(review.before, null, 2)}</pre></>}
      <h3>{review.action === 'rollback' ? 'Cofana zmiana' : 'Treść propozycji'}</h3><pre>{JSON.stringify(review.row.payload, null, 2)}</pre>
      {review.action === 'rollback' && review.row.kind === 'settings' && <><h3>Poprzednie ustawienia</h3><pre>{review.row.previous}</pre></>}
      <p>{review.row.kind === 'code' ? 'To wyłącznie opis. Zatwierdzenie skieruje go do przeglądu; kod nie będzie wykonany ani wdrożony.' : review.row.kind === 'automation' ? 'Przypomnienie tworzy lokalne powiadomienia. Cofnięcie usuwa harmonogram; dotychczasowe powiadomienia pozostają.' : 'Zmiana dotyczy pełnych ustawień asystenta. Sprawdzamy je ponownie przed decyzją; kontrola nie jest atomową rewizją serwera.'}</p>
      <div className="changes-actions"><button className="button primary" disabled={busy || sync} onClick={() => { void confirm() }}>Potwierdź decyzję</button><button className="button secondary" disabled={busy} onClick={() => setReview(null)}>Anuluj decyzję</button></div>
    </section>}
    <section className="panel" aria-labelledby="changes-title"><div className="changes-actions"><h2 id="changes-title">Propozycje zmian</h2><button className="button secondary" disabled={busy} onClick={() => { void load() }}>Odśwież propozycje</button></div>
      <p className="panel-description">Do100 ostatnich propozycji, od najnowszej. To ustawienia, lokalne przypomnienia i opisy kodu; nie obejmuje wszystkich zmian kont, pamięci i pluginów. Ich decyzje pozostają w odpowiednich modułach.</p>
      <div className="form-field"><label htmlFor="changes-filter">Status propozycji</label><select id="changes-filter" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">Wszystkie w odczycie</option>{Object.entries(statuses).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div>
      {!loaded && <p role="status">{busy ? 'Odczytywanie propozycji…' : 'Lista jest chwilowo niedostępna.'}</p>}
      {loaded && !rows.length && <p>Brak zapisanych propozycji.</p>}
      <ul className="changes-list">{rows.filter(row => filter === 'all' || row.status === filter).map(row => <li key={row.id}>
        <h3>{kinds[row.kind]}</h3><p className="badge">{statuses[row.status]}</p><details><summary>Treść propozycji {row.id}</summary><pre>{JSON.stringify(row.payload, null, 2)}</pre></details>
        {row.kind === 'code' && <p>Opis do przeglądu, bez wykonania kodu.</p>}
        <div className="changes-actions">{row.status === 'pending' && <><button className="button secondary" disabled={busy || sync || !!review} onClick={event => { origin.current = event.currentTarget; void prepare(row, 'approve') }}>Przejrzyj zatwierdzenie</button><button className="button subtle" disabled={busy || sync || !!review} onClick={event => { origin.current = event.currentTarget; void prepare(row, 'reject') }}>Przejrzyj odrzucenie</button></>}{row.status === 'applied' && row.kind !== 'code' && <button className="button secondary" disabled={busy || sync || !!review} onClick={event => { origin.current = event.currentTarget; void prepare(row, 'rollback') }}>Przejrzyj cofnięcie</button>}</div>
      </li>)}</ul>
    </section>
  </div>
}

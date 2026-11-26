import { useCallback, useEffect, useRef, useState } from 'react'
import { CalendarCheck, CircleAlert, PackageSearch, RefreshCw, Save, Settings2, Wrench } from 'lucide-react'
import { ApiError, apiRequest } from '../../api'
import { FieldLabel } from '../../components/HelpTip'

interface OrderSummary { id: number; title: string | null; status: string; status_label: string; wait_state: string | null; due_at: string | null; plate: string | null; make: string | null; model: string | null; customer: string | null }
interface PartItem { order_id: number; plate: string | null; name: string | null; part_no: string | null; qty: number | null; status: string; supplier: string | null; expected_at: string | null }
export interface Brief {
  mode: 'live_readonly'; date: string; open_orders: number; by_status: Record<string, number>
  due_today: OrderSummary[]; overdue: OrderSummary[]; ready: OrderSummary[]; waiting_customer: OrderSummary[]
  waiting_parts_orders: number; to_order: PartItem[]; on_order: PartItem[]; partial: boolean
}
interface Connection { enabled: boolean; url: string; pin: string; pin_set: boolean }

const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const invalid = (): never => { throw new ApiError(null, 'response') }
const list = (value: unknown) => Array.isArray(value) && value.every(object)

export async function readBrief(credential: string, signal: AbortSignal): Promise<Brief> {
  const value = await apiRequest('/api/v1/autologika/today', signal, credential, { timeoutMs: 30000 })
  if (!object(value) || value.mode !== 'live_readonly' || !Number.isSafeInteger(value.open_orders) || !object(value.by_status)
    || !['due_today', 'overdue', 'ready', 'waiting_customer', 'to_order', 'on_order'].every(key => list(value[key]))) return invalid()
  return value as unknown as Brief
}

const vehicle = (item: { make: string | null; model: string | null; plate: string | null }) => [item.make, item.model].filter(Boolean).join(' ') + (item.plate ? ' · ' + item.plate : '')
const problem = (error: unknown) => error instanceof ApiError
  ? error.status === 503 ? 'Połączenie z AutoLogiką nie jest skonfigurowane.' : error.status === 502 ? 'AutoLogika nie odpowiada albo odrzuciła PIN. Sprawdź, czy program działa z włączonym serwerem mobilnym.' : error.message
  : 'Nie udało się odczytać AutoLogiki.'

function Orders({ title, items, empty }: { title: string; items: OrderSummary[]; empty: string }) {
  return <div className="today-group"><h3>{title} <span className="badge">{items.length}</span></h3>
    {items.length === 0 ? <p className="workshop-caption">{empty}</p> : <ul>{items.slice(0, 8).map(item => <li key={item.id}><strong>{vehicle(item) || item.title}</strong><span>{item.title}{item.customer ? ' · ' + item.customer : ''} · {item.status_label}</span></li>)}</ul>}
  </div>
}

function Parts({ title, items, empty }: { title: string; items: PartItem[]; empty: string }) {
  return <div className="today-group"><h3>{title} <span className="badge">{items.length}</span></h3>
    {items.length === 0 ? <p className="workshop-caption">{empty}</p> : <ul>{items.slice(0, 10).map((item, index) => <li key={item.order_id + ':' + index}><strong>{item.name || item.part_no || 'Część'}</strong><span>{[item.part_no, item.plate || 'zlecenie ' + item.order_id, item.supplier, item.expected_at ? 'oczekiwana ' + item.expected_at.slice(0, 10) : null].filter(Boolean).join(' · ')}</span></li>)}</ul>}
  </div>
}

/** Today's workshop from the live read-only AutoLogika API (orders due, ready, waiting, parts). */
export function TodayCard({ credential, onUnauthorized, compact = false, refreshKey = 0, autoLoad = false }: { credential: string; onUnauthorized: () => void; compact?: boolean; refreshKey?: number; autoLoad?: boolean }) {
  const [brief, setBrief] = useState<Brief | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized
  const load = useCallback((signal: AbortSignal) => {
    setBusy(true); setError(null)
    readBrief(credential, signal).then(value => { if (!signal.aborted) setBrief(value) })
      .catch(failure => { if (signal.aborted) return; if (failure instanceof ApiError && failure.status === 401) unauthorized.current(); else { setBrief(null); setError(problem(failure)) } })
      .finally(() => { if (!signal.aborted) setBusy(false) })
  }, [credential])
  // Like the rest of this view, nothing is read until asked (or a saved connection asks for a refresh).
  useEffect(() => { if (!autoLoad && refreshKey === 0) return; const controller = new AbortController(); load(controller.signal); return () => controller.abort() }, [load, refreshKey, autoLoad])
  return <section className="panel today-card" aria-labelledby="today-title" aria-busy={busy}>
    <div className="today-head"><h2 className="panel-heading" id="today-title"><CalendarCheck aria-hidden="true" />Dziś w warsztacie</h2>
      <button type="button" className="button subtle" disabled={busy} onClick={() => load(new AbortController().signal)}><RefreshCw className={busy ? 'spin' : ''} aria-hidden="true" />{brief || error ? 'Odśwież' : 'Pokaż dziś'}</button></div>
    {error && <p className="today-problem" role="status"><CircleAlert aria-hidden="true" />{error}</p>}
    {!brief && !error && <p className="workshop-caption" role="status">{busy ? 'Odczytywanie AutoLogiki…' : 'Zlecenia z terminem na dziś, gotowe do odbioru i części do zamówienia — na żywo z AutoLogiki. Albo powiedz „Jarvis, co dziś?”.'}</p>}
    {brief && <>
      <p className="today-summary"><Wrench aria-hidden="true" />Otwartych zleceń: <strong>{brief.open_orders}</strong>{brief.overdue.length > 0 && <> · po terminie: <strong>{brief.overdue.length}</strong></>} · na żywo z AutoLogiki (tylko odczyt)</p>
      <div className="today-grid">
        <Orders title="Termin dziś" items={brief.due_today} empty="Brak zleceń z terminem na dziś." />
        <Orders title="Gotowe do odbioru" items={brief.ready} empty="Nic nie czeka na odbiór." />
        {!compact && <Orders title="Czeka na klienta" items={brief.waiting_customer} empty="Brak zleceń czekających na decyzję." />}
        {!compact && <Orders title="Po terminie" items={brief.overdue} empty="Brak zaległości." />}
        <Parts title="Części do zamówienia" items={brief.to_order} empty="Nic do zamówienia." />
        <Parts title="Części w drodze" items={brief.on_order} empty="Brak oczekiwanych dostaw." />
      </div>
      {brief.partial && <p className="workshop-caption">Lista może być niepełna (limit 100 zleceń / 15 zleceń z częściami).</p>}
    </>}
  </section>
}

/** Owner-only: address and PIN of the AutoLogika mobile server, kept in JARVIS (PIN never shown again). */
export function ConnectionSettings({ credential, onUnauthorized, onSaved }: { credential: string; onUnauthorized: () => void; onSaved: () => void }) {
  const [config, setConfig] = useState<Connection | null>(null)
  const [revision, setRevision] = useState(0)
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    apiRequest('/api/v1/autologika/connection', controller.signal, credential).then(value => {
      if (!object(value) || !object(value.config) || !Number.isSafeInteger(value.revision)) return invalid()
      setConfig(value.config as unknown as Connection); setRevision(value.revision as number)
    }).catch(failure => { if (!controller.signal.aborted) { if (failure instanceof ApiError && failure.status === 401) onUnauthorized(); else setMessage(problem(failure)) } })
    return () => controller.abort()
  }, [credential, onUnauthorized])
  async function save(test: boolean) {
    if (!config || busy) return
    setBusy(true); setMessage(null)
    try {
      const value = await apiRequest('/api/v1/autologika/connection', new AbortController().signal, credential, { method: 'PUT', body: { revision, config: { enabled: config.enabled, url: config.url.trim(), pin: pin || config.pin } } })
      if (!object(value) || !object(value.config) || !Number.isSafeInteger(value.revision)) return invalid()
      setConfig(value.config as unknown as Connection); setRevision(value.revision as number); setPin('')
      if (test) {
        const result = await apiRequest('/api/v1/autologika/connection/test', new AbortController().signal, credential, { body: {}, timeoutMs: 20000 })
        setMessage(object(result) && result.status === 'connected' ? `Połączono. Otwartych zleceń: ${String(result.open_orders)}.` : 'Zapisano.')
      } else setMessage('Zapisano.')
      onSaved()
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) onUnauthorized()
      else setMessage(failure instanceof ApiError && failure.status === 422 ? 'Sprawdź adres (np. http://127.0.0.1:8787) i PIN (6–12 cyfr).' : problem(failure))
    } finally { setBusy(false) }
  }
  return <div className="settings-block" aria-labelledby="autologika-connection-title">
    <h2 className="panel-heading" id="autologika-connection-title"><Settings2 aria-hidden="true" />AutoLogika</h2>
    <p className="panel-description">JARVIS tylko odczytuje zlecenia i części z AutoLogiki — nic w niej nie zmienia.</p>
    {(config ? <div className="today-form">
      <label className="voice-check"><input type="checkbox" checked={config.enabled} onChange={event => setConfig({ ...config, enabled: event.target.checked })} />Połączenie na żywo włączone</label>
      <div className="form-field"><FieldLabel htmlFor="autologika-url" help={<>Gdy AutoLogika działa na tym samym komputerze: <code>http://127.0.0.1:8787</code>. Port widać w AutoLogice: Ustawienia → serwer mobilny (musi być włączony).</>}>Adres AutoLogiki</FieldLabel><input id="autologika-url" value={config.url} onChange={event => setConfig({ ...config, url: event.target.value })} placeholder="http://127.0.0.1:8787" /></div>
      <div className="form-field"><FieldLabel htmlFor="autologika-pin" help="6-cyfrowy PIN serwera mobilnego z AutoLogiki (Ustawienia → serwer mobilny). Po zapisaniu nie jest pokazywany.">PIN</FieldLabel><input id="autologika-pin" type="password" inputMode="numeric" value={pin} onChange={event => setPin(event.target.value)} placeholder={config.pin_set ? 'zapisany — zostaw puste, aby nie zmieniać' : '6 cyfr z AutoLogiki'} autoComplete="off" /></div>
      <div className="camera-actions"><button type="button" className="button primary" disabled={busy} onClick={() => { void save(true) }}><PackageSearch aria-hidden="true" />Zapisz i sprawdź połączenie</button>
        <button type="button" className="button secondary" disabled={busy} onClick={() => { void save(false) }}><Save aria-hidden="true" />Tylko zapisz</button></div>
    </div> : <p role="status">Odczytywanie ustawień…</p>)}
    {message && <p className="workshop-caption" role="status">{message}</p>}
  </div>
}

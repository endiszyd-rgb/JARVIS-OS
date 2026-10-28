import { useEffect, useRef, useState } from 'react'
import { Bell, CircleAlert, RefreshCw, Search } from 'lucide-react'
import { ApiError } from '../../api'
import { readNotifications } from './api'
import type { Notification } from './api'
import './notifications.css'

export interface NotificationsPanelProps { credential: string; onUnauthorized: () => void }
export function NotificationsPanel(props: NotificationsPanelProps) { return <NotificationsWorkspace key={props.credential} {...props} /> }
function NotificationsWorkspace({ credential, onUnauthorized }: NotificationsPanelProps) {
  const [rows, setRows] = useState<Notification[]>([]), [loaded, setLoaded] = useState(false), [busy, setBusy] = useState(false)
  const [query, setQuery] = useState(''), [error, setError] = useState<string | null>(null), [authorized, setAuthorized] = useState(true), [loadedAt, setLoadedAt] = useState<number | null>(null)
  const pending = useRef<AbortController | null>(null), epoch = useRef(0), callback = useRef(onUnauthorized), expired = useRef(false)
  callback.current = onUnauthorized
  async function refresh() {
    pending.current?.abort(); const controller = new AbortController(), id = ++epoch.current; pending.current = controller
    setBusy(true); setError(null)
    try {
      const next = await readNotifications(credential, controller.signal)
      if (epoch.current === id && !controller.signal.aborted && !expired.current) { setRows(next); setLoaded(true); setLoadedAt(Date.now()) }
    } catch (failure) {
      if (epoch.current !== id || controller.signal.aborted || expired.current) return
      if (failure instanceof ApiError && failure.status === 401) {
        expired.current = true; ++epoch.current; controller.abort(); setRows([]); setQuery(''); setLoadedAt(null); setAuthorized(false); callback.current()
      } else setError(failure instanceof ApiError ? failure.message : 'Nie udało się odczytać powiadomień. Spróbuj ponownie.')
    } finally { if (epoch.current === id && !controller.signal.aborted) { setBusy(false); pending.current = null } }
  }
  useEffect(() => {
    expired.current = false; void refresh()
    return () => { ++epoch.current; pending.current?.abort(); pending.current = null }
    // The keyed workspace cannot retain another identity's rows or filter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credential])
  if (!authorized) return <p role="status">Sesja zakończona. Połącz się ponownie.</p>
  const filtered = rows.filter(row => row.message.toLocaleLowerCase('pl').includes(query.trim().toLocaleLowerCase('pl')))
  return <section className="panel notifications-panel" aria-labelledby="notifications-title" aria-busy={busy}>
    <div className="notifications-heading"><div><h2 className="panel-heading" id="notifications-title"><Bell aria-hidden="true" />Ostatnie powiadomienia</h2><p className="panel-description">Do100 najnowszych lokalnych wpisów, od najnowszego. Ten widok nie wysyła powiadomień push, SMS ani wiadomości WhatsApp.</p></div><button className="button secondary" type="button" disabled={busy} onClick={() => { void refresh() }}><RefreshCw aria-hidden="true" />Odśwież powiadomienia</button></div>
    <div className="form-field notifications-filter"><label htmlFor="notifications-filter"><Search aria-hidden="true" />Filtruj powiadomienia</label><input id="notifications-filter" value={query} onChange={event => setQuery(event.target.value)} placeholder="Szukaj w ostatnich wpisach" autoComplete="off" /></div>
    {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}{loaded ? ' Wyświetlany jest poprzedni odczyt.' : ''}</span></div>}
    <p className="notifications-caption" role="status">{busy ? 'Odczytywanie powiadomień…' : loaded ? `Wyświetlono ${filtered.length} z ${rows.length} pobranych wpisów.` : 'Powiadomienia są chwilowo niedostępne.'}</p>
    {loaded && !rows.length && <p className="notifications-caption">Brak zapisanych powiadomień.</p>}
    {loaded && rows.length > 0 && !filtered.length && <p className="notifications-caption">Brak powiadomień pasujących do filtra.</p>}
    <ol className="notifications-list">{filtered.map(row => <li key={row.id}><p>{row.message}</p><time dateTime={new Date(row.created * 1000).toISOString()}>{new Date(row.created * 1000).toLocaleString('pl-PL')}</time></li>)}</ol>
    {loadedAt && <p className="notifications-caption">Odczyt: <time dateTime={new Date(loadedAt).toISOString()}>{new Date(loadedAt).toLocaleTimeString('pl-PL')}</time>. Filtr dotyczy wyłącznie ostatnich100 wpisów, bez pełnego archiwum.</p>}
  </section>
}

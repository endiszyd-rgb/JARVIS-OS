import { useCallback, useEffect, useRef, useState } from 'react'
import { CircleAlert, History, RefreshCw, Search } from 'lucide-react'
import { ApiError } from '../../api'
import { readActivity } from './api'
import type { AuditEvent } from './api'
import './activity.css'

interface Props { credential: string; onUnauthorized: () => void }
interface State {
  credential: string
  rows: AuditEvent[]
  loading: boolean
  error: string | null
  loadedAt: number | null
}

function detailsText(detail: string): { text: string; shortened: boolean } {
  let text = detail
  try { text = JSON.stringify(JSON.parse(detail), null, 2) } catch { /* Historical non-JSON details remain readable text. */ }
  return { text: text.slice(0, 16000), shortened: text.length > 16000 }
}

function EventDetails({ detail, id }: { detail: string; id: number }) {
  const formatted = detailsText(detail)
  return <details className="activity-details">
    <summary>Szczegóły zdarzenia {id}</summary>
    <pre>{formatted.text}</pre>
    {formatted.shortened && <p className="activity-caption">Podgląd skrócono do 16 000 znaków.</p>}
  </details>
}

export function ActivityPanel({ credential, onUnauthorized }: Props) {
  const [state, setState] = useState<State>({ credential, rows: [], loading: true, error: null, loadedAt: null })
  const [filter, setFilter] = useState({ credential, value: '' })
  const request = useRef<AbortController | null>(null)
  const generation = useRef(0)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized

  const refresh = useCallback(async () => {
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    const id = ++generation.current
    setState(previous => ({ credential, rows: previous.credential === credential ? previous.rows : [],
      loading: true, error: null, loadedAt: previous.credential === credential ? previous.loadedAt : null }))
    try {
      const rows = await readActivity(credential, controller.signal)
      if (generation.current === id && !controller.signal.aborted)
        setState({ credential, rows, loading: false, error: null, loadedAt: Date.now() })
    } catch (failure) {
      if (generation.current !== id || controller.signal.aborted) return
      if (failure instanceof ApiError && failure.status === 401) {
        setState({ credential, rows: [], loading: false, error: null, loadedAt: null })
        unauthorized.current()
      } else {
        setState(previous => ({ ...previous, loading: false,
          error: failure instanceof ApiError ? failure.message : 'Nie udało się pobrać historii. Spróbuj ponownie.' }))
      }
    } finally {
      if (request.current === controller) request.current = null
    }
  }, [credential])

  useEffect(() => {
    setFilter({ credential, value: '' })
    void refresh()
    return () => { ++generation.current; request.current?.abort(); request.current = null }
  }, [refresh])

  // A different identity never gets a frame containing the previous identity's rows.
  const visibleState = state.credential === credential ? state : { credential, rows: [], loading: true, error: null, loadedAt: null }
  const visibleFilter = filter.credential === credential ? filter.value : ''
  const query = visibleFilter.trim().toLocaleLowerCase('pl')
  const visible = visibleState.rows.filter(row => !query || (row.event + '\n' + row.detail).toLocaleLowerCase('pl').includes(query))

  return <section className="panel activity-panel" aria-labelledby="activity-title" aria-busy={visibleState.loading}>
    <div className="activity-toolbar">
      <div><h2 className="panel-heading" id="activity-title"><History aria-hidden="true" />Ostatnie zdarzenia</h2>
        <p className="panel-description">Do 100 najnowszych zapisanych zdarzeń, od najnowszego. To podgląd ostatnich działań, a nie pełne archiwum.</p></div>
      <button className="button secondary" type="button" onClick={() => { void refresh() }} disabled={visibleState.loading}>
        <RefreshCw className={visibleState.loading ? 'spin' : ''} aria-hidden="true" />Odśwież historię
      </button>
    </div>
    <div className="form-field activity-filter"><label htmlFor="activity-filter"><Search aria-hidden="true" />Filtruj zdarzenia</label>
      <input id="activity-filter" value={visibleFilter} maxLength={200} onChange={event => setFilter({ credential, value: event.target.value })} placeholder="Nazwa zdarzenia lub treść szczegółów" />
      <small>Filtr działa wyłącznie w pobranych zdarzeniach, maksymalnie 100.</small>
    </div>
    {visibleState.error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{visibleState.error}{visibleState.loadedAt ? ' Wyświetlany jest poprzedni odczyt.' : ''}</span></div>}
    <p className="activity-caption" aria-live="polite">{visibleState.loading ? 'Pobieranie historii…' : visibleState.error && visibleState.loadedAt === null ? 'Brak aktualnego odczytu historii.' : `Pokazano ${visible.length} z ${visibleState.rows.length} pobranych zdarzeń.`}
      {visibleState.loadedAt !== null && <> Odczyt: <time dateTime={new Date(visibleState.loadedAt).toISOString()}>{new Date(visibleState.loadedAt).toLocaleTimeString('pl-PL')}</time>.</>}
    </p>
    {!visibleState.loading && !visibleState.error && !visible.length && <p className="activity-empty">{query ? 'Brak zdarzeń pasujących do filtra w tym odczycie.' : 'Nie ma zapisanych zdarzeń w tym odczycie.'}</p>}
    <ol className="activity-events" aria-label="Pobrane zdarzenia">
      {visible.map(row => <li key={row.id} className="activity-event">
        <div className="activity-event-heading"><strong>{row.event}</strong><time dateTime={new Date(row.created * 1000).toISOString()}>{new Date(row.created * 1000).toLocaleString('pl-PL')}</time></div>
        <EventDetails detail={row.detail} id={row.id} />
      </li>)}
    </ol>
  </section>
}

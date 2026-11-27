import { useCallback, useEffect, useRef, useState } from 'react'
import { Check, CircleAlert, DoorOpen, Lock, Octagon, Radar, RefreshCw, Unlock, X } from 'lucide-react'
import { ApiError } from '../../api'
import { driverLabels, readGate, sendCommand } from './api'
import type { CommandResult, GateAction, GateEvent, GateOverview, GateStatus } from './api'
import './gate.css'

interface Props { credential: string; onUnauthorized: () => void; owner?: boolean }
const message = (error: unknown) => error instanceof ApiError ? error.message : 'Nie udało się wykonać żądania. Spróbuj ponownie.'
const actionLabel: Record<string, string> = { open: 'Otwarcie', close: 'Zamknięcie', stop: 'Zatrzymanie', toggle: 'Brama (impuls)', status: 'Odczyt stanu' }
const sourceLabel: Record<string, string> = { panel: 'panel', voice: 'głos', chat: 'rozmowa', api: 'API' }

export function stateTone(state: GateStatus['state']): string {
  return state === 'open' || state === 'opening' ? 'is-open' : state === 'closed' || state === 'closing' ? 'is-closed' : 'is-unknown'
}

export function GatePanel(props: Props) { return <GateWorkspace key={props.credential} {...props} /> }

function GateWorkspace({ credential, onUnauthorized, owner = true }: Props) {
  const [overview, setOverview] = useState<GateOverview | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [pending, setPending] = useState<Extract<CommandResult, { status: 'confirmation_required' }> | null>(null)
  const controller = useRef<AbortController | null>(null)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized

  const begin = (label: string) => {
    controller.current?.abort()
    const current = new AbortController()
    controller.current = current
    setBusy(label); setError(null); setNotice(null)
    return current
  }
  const fail = (failure: unknown, current: AbortController) => {
    if (current.signal.aborted) return
    if (failure instanceof ApiError && failure.status === 401) { unauthorized.current(); return }
    setError(message(failure))
  }
  const finish = (current: AbortController) => { if (!current.signal.aborted) { setBusy(null); controller.current = null } }

  const load = useCallback(async (quiet = false) => {
    const current = begin(quiet ? 'refresh' : 'load')
    try {
      const next = await readGate(credential, current.signal)
      if (current.signal.aborted) return
      setOverview(next)
    } catch (failure) { fail(failure, current) }
    finally { finish(current) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credential])

  useEffect(() => { void load(); return () => controller.current?.abort() }, [load])

  async function command(action: GateAction, confirmToken?: string) {
    const current = begin(action)
    try {
      const result = await sendCommand(credential, current.signal, action, 'panel', confirmToken)
      if (current.signal.aborted) return
      if (result.status === 'confirmation_required') { setPending(result); return }
      setPending(null)
      setOverview(previous => previous ? { ...previous, gate: result.gate } : previous)
      setNotice(action === 'status' ? `Stan: ${result.gate.state_label}.` : result.action === 'toggle' ? `Brama: impuls wysłany${result.external_request_sent ? ' do sterownika' : ' (symulator)'}.` : `${actionLabel[result.action] ?? actionLabel[action]} wysłane${result.external_request_sent ? ' do sterownika' : ' (symulator)'}.`)
      const refreshed = await readGate(credential, current.signal)
      if (!current.signal.aborted) setOverview(refreshed)
    } catch (failure) { fail(failure, current) }
    finally { finish(current) }
  }

  const gate = overview?.gate
  const disabled = busy !== null
  return <div className="gate-feature">
    {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div>}
    {notice && <p className="gate-notice" role="status"><Check aria-hidden="true" />{notice}</p>}

    <section className="panel gate-control" aria-labelledby="gate-title" aria-busy={disabled}>
      <div className="gate-head">
        <div><h2 className="panel-heading" id="gate-title"><DoorOpen aria-hidden="true" />{gate?.name ?? 'Brama'}</h2>
          <p className="panel-description">{gate?.driver === 'simulator' ? 'Symulator: polecenia są zapisywane, ale nic fizycznego się nie dzieje.' : gate?.driver === 'disabled' ? 'Sterowanie wyłączone w konfiguracji.' : `Sterownik: ${gate ? driverLabels[gate.driver] : '—'}. Każde polecenie trafia do audytu.`}</p></div>
        <button type="button" className="button subtle" disabled={disabled} onClick={() => { void load(true) }}><RefreshCw aria-hidden="true" className={busy === 'refresh' ? 'spin' : ''} />Odśwież</button>
      </div>
      <div className={'gate-readout ' + (gate ? stateTone(gate.state) : 'is-unknown')} role="status" aria-live="polite">
        <span className="gate-readout-icon" aria-hidden="true">{gate?.state === 'open' || gate?.state === 'opening' ? <Unlock /> : gate?.state === 'closed' || gate?.state === 'closing' ? <Lock /> : <Radar />}</span>
        <div><p className="gate-readout-label">STAN BRAMY</p><p className="gate-readout-value">{gate ? gate.state_label.toUpperCase() : '—'}</p>
          <p className="gate-readout-meta">{gate?.changed ? 'Ostatnie polecenie: ' + new Date(gate.changed * 1000).toLocaleTimeString('pl-PL') : 'Brak poleceń w tym uruchomieniu'}{gate?.require_confirmation ? ' · wymaga potwierdzenia' : ''}{gate?.live ? ' · sprzęt' : ''}</p></div>
      </div>
      {pending ? <div className="gate-confirm" role="alertdialog" aria-labelledby="gate-confirm-title">
        <p id="gate-confirm-title"><CircleAlert aria-hidden="true" />{pending.prompt}</p>
        <div className="gate-actions"><button type="button" className="button primary" disabled={disabled} onClick={() => { void command(pending.action, pending.confirm_token) }}><Check aria-hidden="true" />Tak, wykonaj</button>
          <button type="button" className="button secondary" disabled={disabled} onClick={() => setPending(null)}><X aria-hidden="true" />Anuluj</button></div>
      </div> : <div className="gate-actions">
        {gate?.pulse ? <button type="button" className="button primary gate-open gate-toggle" disabled={disabled || gate?.driver === 'disabled'} onClick={() => { void command('toggle') }}><DoorOpen aria-hidden="true" />Brama</button> : <>
          <button type="button" className="button primary gate-open" disabled={disabled || gate?.driver === 'disabled'} onClick={() => { void command('open') }}><Unlock aria-hidden="true" />Otwórz</button>
          <button type="button" className="button secondary" disabled={disabled || gate?.driver === 'disabled'} onClick={() => { void command('close') }}><Lock aria-hidden="true" />Zamknij</button>
          <button type="button" className="button secondary" disabled={disabled || gate?.driver === 'disabled'} onClick={() => { void command('stop') }}><Octagon aria-hidden="true" />Stop</button></>}
        <button type="button" className="button subtle" disabled={disabled || gate?.driver === 'disabled'} onClick={() => { void command('status') }}><Radar aria-hidden="true" />Odczytaj stan</button>
      </div>}
      <p className="gate-caption">{gate?.pulse ? <>Jeden przycisk jak pilot: każde naciśnięcie otwiera, zatrzymuje albo zamyka bramę. Komenda głosowa: „Jarvis, brama”</> : <>Komenda głosowa: „Jarvis, otwórz bramę” / „zamknij bramę” / „brama stop”</>} — w widoku <a href="#/voice">Głos</a>.{owner && <> Sterownik i hasła: <a href="#/settings/gate">Ustawienia → Brama</a>.</>}</p>
    </section>

    <section className="panel" aria-labelledby="gate-events-title">
      <h2 className="panel-heading" id="gate-events-title"><Radar aria-hidden="true" />Ostatnie polecenia</h2>
      {overview && overview.events.length === 0 ? <p className="gate-caption">Brak zapisanych poleceń.</p> : <ul className="gate-events">{overview?.events.map((event: GateEvent) => <li key={event.id} className={event.result === 'ok' ? '' : 'is-error'}>
        <span className="gate-event-time">{new Date(event.created * 1000).toLocaleString('pl-PL')}</span>
        <strong>{actionLabel[event.action] ?? event.action}</strong>
        <span>{sourceLabel[event.source] ?? event.source} · {String(event.detail.driver ?? '')}</span>
        <span className={'badge ' + (event.result === 'ok' ? 'tone-good' : 'tone-warning')}>{event.result === 'ok' ? 'OK' : 'Błąd'}</span>
      </li>)}</ul>}
    </section>
  </div>
}

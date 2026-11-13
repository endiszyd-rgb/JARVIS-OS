import { useEffect, useRef, useState } from 'react'
import { AudioLines, DoorOpen, Lock, RefreshCw, Unlock } from 'lucide-react'
import { ApiError } from '../../api'
import { readGate, sendCommand } from './api'
import type { GateStatus } from './api'
import { stateTone } from './GatePanel'
import './gate.css'

interface Props { credential: string; onUnauthorized: () => void }

/** Dashboard shortcut: current gate state and one-tap open/close. Confirmation-required gates redirect to the gate view. */
export function GateTile({ credential, onUnauthorized }: Props) {
  const [gate, setGate] = useState<GateStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized

  useEffect(() => {
    const controller = new AbortController()
    readGate(credential, controller.signal).then(overview => { if (!controller.signal.aborted) setGate(overview.gate) })
      .catch(failure => { if (!controller.signal.aborted && failure instanceof ApiError && failure.status === 401) unauthorized.current() })
    return () => controller.abort()
  }, [credential])

  async function act(action: 'open' | 'close') {
    setBusy(true); setNote(null)
    try {
      const result = await sendCommand(credential, new AbortController().signal, action, 'panel')
      if (result.status === 'confirmation_required') { setNote('Ta brama wymaga potwierdzenia — użyj widoku Brama lub Głos.'); return }
      setGate(result.gate); setNote(action === 'open' ? 'Polecenie otwarcia wysłane.' : 'Polecenie zamknięcia wysłane.')
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) unauthorized.current()
      else setNote(failure instanceof ApiError ? failure.message : 'Nie udało się wysłać polecenia.')
    } finally { setBusy(false) }
  }

  const disabled = busy || !gate || gate.driver === 'disabled'
  return <section className="panel gate-tile" aria-labelledby="gate-tile-title">
    <h2 className="panel-heading" id="gate-tile-title"><DoorOpen aria-hidden="true" />{gate?.name ?? 'Brama'}</h2>
    <p className="panel-description">{gate ? gate.driver === 'simulator' ? 'Symulator — bez fizycznego sterowania.' : gate.driver === 'disabled' ? 'Sterowanie wyłączone.' : 'Sterownik sprzętowy.' : 'Odczyt stanu…'}</p>
    <div className={'gate-readout ' + (gate ? stateTone(gate.state) : 'is-unknown')} role="status">
      <span className="gate-readout-icon" aria-hidden="true">{gate?.state === 'open' || gate?.state === 'opening' ? <Unlock /> : gate?.state === 'closed' || gate?.state === 'closing' ? <Lock /> : <RefreshCw />}</span>
      <div><p className="gate-readout-label">STAN</p><p className="gate-readout-value">{gate ? gate.state_label.toUpperCase() : '—'}</p>{note && <p className="gate-readout-meta">{note}</p>}</div>
    </div>
    <div className="gate-actions">
      <button type="button" className="button primary" disabled={disabled} onClick={() => { void act('open') }}><Unlock aria-hidden="true" />Otwórz</button>
      <button type="button" className="button secondary" disabled={disabled} onClick={() => { void act('close') }}><Lock aria-hidden="true" />Zamknij</button>
      <a className="button subtle" href="#/voice"><AudioLines aria-hidden="true" />Głos</a>
    </div>
  </section>
}

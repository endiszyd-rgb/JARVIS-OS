import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Check, CircleAlert, DoorOpen, Lock, Octagon, Radar, RefreshCw, Save, Settings2, Unlock, X } from 'lucide-react'
import { ApiError } from '../../api'
import { DRIVERS, driverLabels, emptyHomeAssistant, emptyHttp, emptyTuya, readGate, saveGateConfig, sendCommand, testGate } from './api'
import type { CommandResult, GateAction, GateConfig, GateDriver, GateEvent, GateOverview, GateStatus } from './api'
import './gate.css'

interface Props { credential: string; onUnauthorized: () => void; owner?: boolean }
const message = (error: unknown) => error instanceof ApiError ? error.message : 'Nie udało się wykonać żądania. Spróbuj ponownie.'
const actionLabel: Record<string, string> = { open: 'Otwarcie', close: 'Zamknięcie', stop: 'Zatrzymanie', status: 'Odczyt stanu' }
const sourceLabel: Record<string, string> = { panel: 'panel', voice: 'głos', chat: 'rozmowa', api: 'API' }

export function stateTone(state: GateStatus['state']): string {
  return state === 'open' || state === 'opening' ? 'is-open' : state === 'closed' || state === 'closing' ? 'is-closed' : 'is-unknown'
}

export function GatePanel(props: Props) { return <GateWorkspace key={props.credential} {...props} /> }

function GateWorkspace({ credential, onUnauthorized, owner = true }: Props) {
  const [overview, setOverview] = useState<GateOverview | null>(null)
  const [draft, setDraft] = useState<GateConfig | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [pending, setPending] = useState<Extract<CommandResult, { status: 'confirmation_required' }> | null>(null)
  const [showConfig, setShowConfig] = useState(false)
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
      setOverview(next); setDraft(structuredClone(next.config))
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
      setNotice(action === 'status' ? `Stan: ${result.gate.state_label}.` : `${actionLabel[action]} wysłane${result.external_request_sent ? ' do sterownika' : ' (symulator)'}.`)
      const refreshed = await readGate(credential, current.signal)
      if (!current.signal.aborted) setOverview(refreshed)
    } catch (failure) { fail(failure, current) }
    finally { finish(current) }
  }

  async function test() {
    const current = begin('test')
    try {
      const gate = await testGate(credential, current.signal)
      if (current.signal.aborted) return
      setOverview(previous => previous ? { ...previous, gate } : previous)
      setNotice(`Sterownik odpowiada. Stan: ${gate.state_label}.`)
    } catch (failure) { fail(failure, current) }
    finally { finish(current) }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draft || !overview) return
    const current = begin('save')
    try {
      const saved = await saveGateConfig(credential, current.signal, overview.revision, draft)
      if (current.signal.aborted) return
      setNotice('Konfiguracja bramy zapisana.')
      const refreshed = await readGate(credential, current.signal)
      if (!current.signal.aborted) { setOverview(refreshed); setDraft(structuredClone(saved.config)) }
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 409) { setError('Konfiguracja zmieniła się w międzyczasie. Odświeżono bieżące wartości.'); void load(true) }
      else if (failure instanceof ApiError && failure.status === 422) setError('Serwer odrzucił konfigurację. Sprawdź adresy URL, identyfikatory i wymagane pola wybranego sterownika.')
      else fail(failure, current)
    }
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
        <button type="button" className="button primary gate-open" disabled={disabled || gate?.driver === 'disabled'} onClick={() => { void command('open') }}><Unlock aria-hidden="true" />Otwórz</button>
        <button type="button" className="button secondary" disabled={disabled || gate?.driver === 'disabled'} onClick={() => { void command('close') }}><Lock aria-hidden="true" />Zamknij</button>
        <button type="button" className="button secondary" disabled={disabled || gate?.driver === 'disabled'} onClick={() => { void command('stop') }}><Octagon aria-hidden="true" />Stop</button>
        <button type="button" className="button subtle" disabled={disabled || gate?.driver === 'disabled'} onClick={() => { void command('status') }}><Radar aria-hidden="true" />Odczytaj stan</button>
      </div>}
      <p className="gate-caption">Komenda głosowa: „Jarvis, otwórz bramę” / „zamknij bramę” / „brama stop” — w widoku <a href="#/voice">Głos</a>.</p>
    </section>

    {owner && <section className="panel" aria-labelledby="gate-config-title">
      <div className="gate-head"><div><h2 className="panel-heading" id="gate-config-title"><Settings2 aria-hidden="true" />Konfiguracja sterownika</h2>
        <p className="panel-description">Zapisywana lokalnie w JARVIS. Hasła i klucze nie są pokazywane po zapisaniu; puste pole zachowuje poprzednią wartość.</p></div>
        <button type="button" className="button subtle" onClick={() => setShowConfig(value => !value)} aria-expanded={showConfig}>{showConfig ? 'Zwiń' : 'Edytuj'}</button></div>
      {showConfig && draft && <form className="gate-form" onSubmit={event => { void save(event) }} aria-busy={disabled}>
        <div className="gate-grid">
          <div className="form-field"><label htmlFor="gate-driver">Sterownik</label>
            <select id="gate-driver" value={draft.driver} disabled={disabled} onChange={event => {
              const driver = event.target.value as GateDriver
              setDraft({ ...draft, driver, http: driver === 'http' ? draft.http ?? { ...emptyHttp } : draft.http, tuya: driver === 'tuya_cloud' ? draft.tuya ?? { ...emptyTuya } : draft.tuya, home_assistant: driver === 'home_assistant' ? draft.home_assistant ?? { ...emptyHomeAssistant } : draft.home_assistant })
            }}>{DRIVERS.map(item => <option key={item} value={item}>{driverLabels[item]}</option>)}</select></div>
          <div className="form-field"><label htmlFor="gate-name">Nazwa</label><input id="gate-name" value={draft.name} maxLength={80} disabled={disabled} onChange={event => setDraft({ ...draft, name: event.target.value })} /></div>
          <div className="form-field"><label htmlFor="gate-cooldown">Odstęp między poleceniami (s)</label><input id="gate-cooldown" type="number" min={0} max={120} value={draft.cooldown_seconds} disabled={disabled} onChange={event => setDraft({ ...draft, cooldown_seconds: Number(event.target.value) })} /></div>
          <div className="form-field"><label htmlFor="gate-travel">Czas pełnego ruchu bramy (s)</label><input id="gate-travel" type="number" min={1} max={300} value={draft.travel_seconds} disabled={disabled} onChange={event => setDraft({ ...draft, travel_seconds: Number(event.target.value) })} /></div>
        </div>
        <label className="gate-check"><input type="checkbox" checked={draft.require_confirmation} disabled={disabled} onChange={event => setDraft({ ...draft, require_confirmation: event.target.checked })} />Wymagaj potwierdzenia („tak”) przed otwarciem, zamknięciem i zatrzymaniem</label>
        <label className="gate-check"><input type="checkbox" checked={draft.pulse} disabled={disabled} onChange={event => setDraft({ ...draft, pulse: event.target.checked })} />Brama impulsowa — jeden przycisk otwiera i zamyka (zamknięcie wysyła polecenie otwarcia)</label>

        {draft.driver === 'http' && draft.http && <fieldset className="gate-fieldset"><legend>Lokalne HTTP</legend>
          <p className="gate-caption">Przykład Shelly: <code>http://192.168.1.50/relay/0?turn=on</code>. Tasmota: <code>http://192.168.1.51/cm?cmnd=Power%20On</code>. Adres sterownika musi mieścić się w <code>JARVIS_NETWORK_ALLOWLIST</code> (np. <code>192.168.1.0/24</code>).</p>
          <div className="gate-grid">
            {(['open_url', 'close_url', 'stop_url', 'status_url'] as const).map(field => <div className="form-field" key={field}><label htmlFor={'http-' + field}>{{ open_url: 'URL otwarcia', close_url: 'URL zamknięcia', stop_url: 'URL zatrzymania', status_url: 'URL stanu (opcjonalnie)' }[field]}</label>
              <input id={'http-' + field} value={draft.http![field]} maxLength={500} disabled={disabled} placeholder="http://192.168.1.50/…" onChange={event => setDraft({ ...draft, http: { ...draft.http!, [field]: event.target.value } })} /></div>)}
            <div className="form-field"><label htmlFor="http-method">Metoda</label><select id="http-method" value={draft.http.method} disabled={disabled} onChange={event => setDraft({ ...draft, http: { ...draft.http!, method: event.target.value as 'GET' | 'POST' } })}><option>GET</option><option>POST</option></select></div>
            <div className="form-field"><label htmlFor="http-match">Fragment odpowiedzi oznaczający OTWARTA</label><input id="http-match" value={draft.http.status_open_match} maxLength={120} disabled={disabled} placeholder={'"ison":true'} onChange={event => setDraft({ ...draft, http: { ...draft.http!, status_open_match: event.target.value } })} /></div>
            <div className="form-field"><label htmlFor="http-user">Użytkownik (opcjonalnie)</label><input id="http-user" value={draft.http.username} maxLength={120} disabled={disabled} autoComplete="off" onChange={event => setDraft({ ...draft, http: { ...draft.http!, username: event.target.value } })} /></div>
            <div className="form-field"><label htmlFor="http-pass">Hasło {draft.http.password_set ? '(zapisane)' : ''}</label><input id="http-pass" type="password" value={draft.http.password} maxLength={200} disabled={disabled} autoComplete="new-password" onChange={event => setDraft({ ...draft, http: { ...draft.http!, password: event.target.value } })} /></div>
          </div></fieldset>}

        {draft.driver === 'tuya_cloud' && draft.tuya && <fieldset className="gate-fieldset"><legend>Tuya / Smart Life</legend>
          <p className="gate-caption">Załóż projekt w Tuya IoT Platform (iot.tuya.com), połącz konto Smart Life i odczytaj Access ID, Access Secret oraz Device ID bramy. Kody poleceń znajdziesz w zakładce „Device Debugging” (zwykle <code>switch_1</code>).</p>
          <div className="gate-grid">
            <div className="form-field"><label htmlFor="tuya-endpoint">Region</label><select id="tuya-endpoint" value={draft.tuya.endpoint} disabled={disabled} onChange={event => setDraft({ ...draft, tuya: { ...draft.tuya!, endpoint: event.target.value } })}>
              <option value="https://openapi.tuyaeu.com">Europa Centralna (tuyaeu)</option><option value="https://openapi-weaz.tuyaeu.com">Europa Zachodnia (weaz)</option><option value="https://openapi.tuyaus.com">USA (tuyaus)</option><option value="https://openapi-ueaz.tuyaus.com">USA Wschód (ueaz)</option><option value="https://openapi.tuyacn.com">Chiny</option><option value="https://openapi.tuyain.com">Indie</option></select></div>
            <div className="form-field"><label htmlFor="tuya-id">Access ID</label><input id="tuya-id" value={draft.tuya.access_id} maxLength={64} disabled={disabled} autoComplete="off" onChange={event => setDraft({ ...draft, tuya: { ...draft.tuya!, access_id: event.target.value } })} /></div>
            <div className="form-field"><label htmlFor="tuya-secret">Access Secret {draft.tuya.access_secret_set ? '(zapisany)' : ''}</label><input id="tuya-secret" type="password" value={draft.tuya.access_secret} maxLength={128} disabled={disabled} autoComplete="new-password" onChange={event => setDraft({ ...draft, tuya: { ...draft.tuya!, access_secret: event.target.value } })} /></div>
            <div className="form-field"><label htmlFor="tuya-device">Device ID</label><input id="tuya-device" value={draft.tuya.device_id} maxLength={64} disabled={disabled} autoComplete="off" onChange={event => setDraft({ ...draft, tuya: { ...draft.tuya!, device_id: event.target.value } })} /></div>
            <div className="form-field"><label htmlFor="tuya-open">Kod otwarcia</label><input id="tuya-open" value={draft.tuya.open_code} maxLength={64} disabled={disabled} onChange={event => setDraft({ ...draft, tuya: { ...draft.tuya!, open_code: event.target.value } })} /></div>
            <div className="form-field"><label htmlFor="tuya-close">Kod zamknięcia</label><input id="tuya-close" value={draft.tuya.close_code} maxLength={64} disabled={disabled} onChange={event => setDraft({ ...draft, tuya: { ...draft.tuya!, close_code: event.target.value } })} /></div>
            <div className="form-field"><label htmlFor="tuya-stop">Kod zatrzymania (opcjonalnie)</label><input id="tuya-stop" value={draft.tuya.stop_code} maxLength={64} disabled={disabled} onChange={event => setDraft({ ...draft, tuya: { ...draft.tuya!, stop_code: event.target.value } })} /></div>
            <div className="form-field"><label htmlFor="tuya-status">Kod stanu (opcjonalnie, np. doorcontact_state)</label><input id="tuya-status" value={draft.tuya.status_code} maxLength={64} disabled={disabled} onChange={event => setDraft({ ...draft, tuya: { ...draft.tuya!, status_code: event.target.value } })} /></div>
          </div></fieldset>}

        {draft.driver === 'home_assistant' && draft.home_assistant && <fieldset className="gate-fieldset"><legend>Home Assistant</legend>
          <p className="gate-caption">Puste URL/token używają wartości <code>HA_URL</code> / <code>HA_TOKEN</code> z pliku .env.</p>
          <div className="gate-grid">
            <div className="form-field"><label htmlFor="ha-url">URL Home Assistant</label><input id="ha-url" value={draft.home_assistant.url} maxLength={300} disabled={disabled} placeholder="http://192.168.1.10:8123" onChange={event => setDraft({ ...draft, home_assistant: { ...draft.home_assistant!, url: event.target.value } })} /></div>
            <div className="form-field"><label htmlFor="ha-token">Token {draft.home_assistant.token_set ? '(zapisany)' : ''}</label><input id="ha-token" type="password" value={draft.home_assistant.token} disabled={disabled} autoComplete="new-password" onChange={event => setDraft({ ...draft, home_assistant: { ...draft.home_assistant!, token: event.target.value } })} /></div>
            <div className="form-field"><label htmlFor="ha-entity">Encja</label><input id="ha-entity" value={draft.home_assistant.entity_id} maxLength={120} disabled={disabled} placeholder="cover.brama" onChange={event => setDraft({ ...draft, home_assistant: { ...draft.home_assistant!, entity_id: event.target.value } })} /></div>
            <div className="form-field"><label htmlFor="ha-open">Usługa otwarcia</label><input id="ha-open" value={draft.home_assistant.open_service} disabled={disabled} onChange={event => setDraft({ ...draft, home_assistant: { ...draft.home_assistant!, open_service: event.target.value } })} /></div>
            <div className="form-field"><label htmlFor="ha-close">Usługa zamknięcia</label><input id="ha-close" value={draft.home_assistant.close_service} disabled={disabled} onChange={event => setDraft({ ...draft, home_assistant: { ...draft.home_assistant!, close_service: event.target.value } })} /></div>
            <div className="form-field"><label htmlFor="ha-stop">Usługa zatrzymania</label><input id="ha-stop" value={draft.home_assistant.stop_service} disabled={disabled} onChange={event => setDraft({ ...draft, home_assistant: { ...draft.home_assistant!, stop_service: event.target.value } })} /></div>
          </div></fieldset>}

        <div className="gate-actions"><button type="submit" className="button primary" disabled={disabled}><Save aria-hidden="true" />Zapisz konfigurację</button>
          <button type="button" className="button secondary" disabled={disabled || overview?.config.driver === 'disabled'} onClick={() => { void test() }}><Radar aria-hidden="true" />Testuj połączenie (bez ruchu bramy)</button>
          <button type="button" className="button subtle" disabled={disabled} onClick={() => overview && setDraft(structuredClone(overview.config))}>Przywróć</button></div>
      </form>}
    </section>}

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

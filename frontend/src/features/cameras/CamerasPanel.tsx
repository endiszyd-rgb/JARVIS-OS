import { useEffect, useRef, useState } from 'react'
import { Camera as CameraIcon, CircleAlert, Maximize2, Pause, Play, Plus, Save, Search, Trash2 } from 'lucide-react'
import { ApiError, apiRequest } from '../../api'
import { FieldLabel } from '../../components/HelpTip'
import './cameras.css'

interface Props { credential: string; onUnauthorized: () => void; owner: boolean }
export interface CameraSummary { id: string; name: string }
export interface CameraList { enabled: boolean; refresh_ms: number; cameras: CameraSummary[] }
export interface CameraEntry { id: string; name: string; source: 'tuya' | 'rtsp' | 'go2rtc'; stream: string; device_id: string; uid: string; resolution: 'sd' | 'hd'; rtsp_url: string; rtsp_set?: boolean; enabled: boolean }
export interface CameraConfig { enabled: boolean; mode: 'builtin' | 'external'; go2rtc_url: string; refresh_ms: number; cameras: CameraEntry[] }

const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const invalid = (): never => { throw new ApiError(null, 'response') }
const message = (error: unknown) => error instanceof ApiError ? (error.status === 422 && error.detail ? error.detail : error.message) : 'Nie udało się wykonać żądania. Spróbuj ponownie.'

export async function readCameras(credential: string, signal: AbortSignal): Promise<CameraList> {
  const value = await apiRequest('/api/v1/cameras', signal, credential)
  if (!object(value) || typeof value.enabled !== 'boolean' || !Number.isFinite(value.refresh_ms) || !Array.isArray(value.cameras)
    || !value.cameras.every(item => object(item) && typeof item.id === 'string' && typeof item.name === 'string')) return invalid()
  return value as unknown as CameraList
}

/** One JPEG frame fetched with the session header (an <img src> cannot send it), shown as a blob URL. */
export async function readFrame(credential: string, signal: AbortSignal, id: string): Promise<Blob> {
  const response = await fetch('/api/v1/cameras/' + encodeURIComponent(id) + '/frame.jpg', { headers: { 'X-Jarvis-Key': credential }, signal, cache: 'no-store', credentials: 'omit', redirect: 'error', mode: 'same-origin' })
  if (!response.ok) throw new ApiError(response.status)
  return response.blob()
}

export function CameraView({ camera, credential, refreshMs, running, onUnauthorized, onOpen }: { camera: CameraSummary; credential: string; refreshMs: number; running: boolean; onUnauthorized: () => void; onOpen: () => void }) {
  const [url, setUrl] = useState<string | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [stamp, setStamp] = useState<number | null>(null)
  const current = useRef<string | null>(null)
  useEffect(() => {
    if (!running) return
    const controller = new AbortController()
    let timer = 0
    const tick = async () => {
      if (document.visibilityState === 'hidden') { timer = window.setTimeout(() => { void tick() }, refreshMs); return }
      try {
        const blob = await readFrame(credential, controller.signal, camera.id)
        if (controller.signal.aborted) return
        const next = URL.createObjectURL(blob)
        if (current.current) URL.revokeObjectURL(current.current)
        current.current = next; setUrl(next); setProblem(null); setStamp(Date.now())
      } catch (failure) {
        if (controller.signal.aborted) return
        if (failure instanceof ApiError && failure.status === 401) { onUnauthorized(); return }
        setProblem(failure instanceof ApiError ? (failure.status === 504 ? 'Kamera nie odpowiada' : failure.status === 502 ? 'go2rtc nie zwrócił obrazu' : failure.status === 503 ? 'Podgląd wyłączony' : failure.message) : 'Brak połączenia')
      }
      timer = window.setTimeout(() => { void tick() }, refreshMs)
    }
    void tick()
    return () => { controller.abort(); window.clearTimeout(timer) }
  }, [camera.id, credential, refreshMs, running, onUnauthorized])
  useEffect(() => () => { if (current.current) URL.revokeObjectURL(current.current) }, [])
  return <figure className="camera-tile">
    <button type="button" className="camera-frame" onClick={onOpen} aria-label={'Powiększ kamerę ' + camera.name}>
      {url ? <img src={url} alt={'Podgląd: ' + camera.name} /> : <span className="camera-placeholder"><CameraIcon aria-hidden="true" /></span>}
      {problem && <span className="camera-problem" role="status"><CircleAlert aria-hidden="true" />{problem}</span>}
    </button>
    <figcaption><strong>{camera.name}</strong><span>{stamp ? new Date(stamp).toLocaleTimeString('pl-PL') : '—'}</span></figcaption>
  </figure>
}

const SECRET_MASK = '••••••••'
export type CameraSource = 'tuya' | 'rtsp' | 'go2rtc'
export interface BuiltinStatus { available: boolean; running: boolean; ffmpeg: boolean; problems: string[]; error: string | null }

function nextId(cameras: CameraEntry[]) {
  for (let number = cameras.length + 1; ; number += 1) if (!cameras.some(item => item.id === 'kamera' + number)) return 'kamera' + number
}
function blankCamera(cameras: CameraEntry[], mode: CameraConfig['mode']): CameraEntry {
  return { id: nextId(cameras), name: 'Kamera ' + (cameras.length + 1), source: mode === 'external' ? 'go2rtc' : 'tuya', stream: '', device_id: '', uid: '', resolution: 'sd', rtsp_url: '', enabled: true }
}

/** Built-in go2rtc state in words — what the owner needs to do next, if anything. */
function BuiltinState({ status, config }: { status: BuiltinStatus | null; config: CameraConfig }) {
  if (config.mode !== 'builtin' || !status) return null
  if (!status.available) return <p className="form-warning" role="status"><CircleAlert aria-hidden="true" />Wbudowany go2rtc nie jest zainstalowany — zainstaluj JARVIS z najnowszego instalatora albo w „Więcej opcji” wybierz własny go2rtc.</p>
  return <div className="camera-builtin" role="status">
    <p><span className={status.running ? 'status-dot is-ok' : 'status-dot'} aria-hidden="true" />{status.running ? 'go2rtc działa — kamery są podłączane automatycznie.' : config.enabled && config.cameras.length ? 'go2rtc nie działa — kliknij Zapisz, aby go uruchomić.' : 'go2rtc uruchomi się po dodaniu kamery i zapisaniu.'}{!status.ffmpeg && ' Brak ffmpeg — obraz z kamer Setti może się nie pokazać.'}</p>
    {status.error && <p className="form-error">{status.error}</p>}
    {status.problems.length > 0 && <ul className="camera-problems">{status.problems.map(item => <li key={item}>{item}</li>)}</ul>}
  </div>
}

function ConfigEditor({ credential, onSaved, onUnauthorized }: { credential: string; onSaved: () => void; onUnauthorized: () => void }) {
  const [draft, setDraft] = useState<CameraConfig | null>(null)
  const [revision, setRevision] = useState(0)
  const [status, setStatus] = useState<BuiltinStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [checks, setChecks] = useState<Record<number, string>>({})
  useEffect(() => {
    const controller = new AbortController()
    apiRequest('/api/v1/cameras/config', controller.signal, credential).then(value => {
      if (!object(value) || !object(value.config) || !Number.isSafeInteger(value.revision)) return invalid()
      setDraft(normalise(value.config as unknown as CameraConfig)); setRevision(value.revision as number)
      if (object(value.builtin)) setStatus(value.builtin as unknown as BuiltinStatus)
    }).catch(failure => { if (!controller.signal.aborted) { if (failure instanceof ApiError && failure.status === 401) onUnauthorized(); else setError(message(failure)) } })
    return () => controller.abort()
  }, [credential, onUnauthorized])
  if (!draft) return error ? <p className="form-error" role="alert">{error}</p> : <p role="status">Odczytywanie konfiguracji…</p>
  const builtin = draft.mode === 'builtin'
  const update = (index: number, patch: Partial<CameraEntry>) => setDraft({ ...draft, cameras: draft.cameras.map((item, position) => position === index ? { ...item, ...patch } : item) })
  async function save() {
    if (!draft || busy) return
    setBusy(true); setError(null)
    try {
      const body = { ...draft, cameras: draft.cameras.map(({ rtsp_set: _flag, ...item }) => item) }
      const value = await apiRequest('/api/v1/cameras/config', new AbortController().signal, credential, { method: 'PUT', body: { revision, config: body } })
      if (!object(value) || !Number.isSafeInteger(value.revision) || !object(value.config)) return invalid()
      setRevision(value.revision as number); setDraft(normalise(value.config as unknown as CameraConfig))
      if (object(value.builtin)) setStatus(value.builtin as unknown as BuiltinStatus)
      onSaved()
    } catch (failure) { if (failure instanceof ApiError && failure.status === 401) onUnauthorized(); else setError(message(failure)) } finally { setBusy(false) }
  }
  async function check(index: number) {
    const item = draft?.cameras[index]
    if (!draft || !item) return
    const deviceId = item.device_id.trim()
    if (!deviceId) { setChecks({ ...checks, [index]: 'Wpisz najpierw Device ID kamery.' }); return }
    setChecks({ ...checks, [index]: 'Sprawdzam w chmurze Tuya…' })
    try {
      const value = await apiRequest('/api/v1/cameras/tuya-info', new AbortController().signal, credential, { body: { device_id: deviceId } })
      if (!object(value) || typeof value.uid !== 'string') return invalid()
      const name = typeof value.name === 'string' && value.name ? value.name : ''
      update(index, { device_id: deviceId, uid: value.uid, name: /^Kamera \d+$/.test(item.name) && name ? name.slice(0, 60) : item.name })
      setChecks({ ...checks, [index]: '✓ ' + (name || 'Kamera znaleziona') + (value.online ? ' · online' : ' · offline') + '. Kliknij Zapisz.' })
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) { onUnauthorized(); return }
      const detail = failure instanceof ApiError ? failure.detail ?? '' : ''
      setChecks({ ...checks, [index]: failure instanceof ApiError && failure.status === 409 ? 'Najpierw zapisz dane chmury Tuya: Ustawienia → Brama → „Setti / Tuya przez chmurę” (Access ID i Secret).'
        : /Tuya error/.test(detail) ? 'Tuya: ' + detail.replace(/^Tuya error /, '') : 'Nie udało się sprawdzić kamery.' })
    }
  }
  return <div className="camera-config">
    <label className="voice-check"><input type="checkbox" checked={draft.enabled} onChange={event => setDraft({ ...draft, enabled: event.target.checked })} />Podgląd kamer włączony</label>
    <BuiltinState status={status} config={draft} />
    <ul className="camera-rows">{draft.cameras.map((item, index) => <li key={index} className="camera-card">
      <div className="camera-card-grid">
        <div className="form-field"><FieldLabel htmlFor={'cam-name-' + index} help="Nazwa widoczna pod podglądem, np. „Wjazd” albo „Hala”.">Nazwa</FieldLabel><input id={'cam-name-' + index} value={item.name} maxLength={60} onChange={event => update(index, { name: event.target.value })} placeholder="Wjazd" /></div>
        {builtin ? <div className="form-field"><FieldLabel htmlFor={'cam-source-' + index} help="Kamery Setti działają przez chmurę Tuya — wystarczy ich Device ID. Kamery IP i rejestratory podłączasz adresem RTSP.">Rodzaj kamery</FieldLabel>
          <select id={'cam-source-' + index} value={item.source} onChange={event => update(index, { source: event.target.value as CameraSource })}><option value="tuya">Setti / Tuya (Device ID)</option><option value="rtsp">Kamera IP / rejestrator (RTSP)</option></select></div>
          : <div className="form-field"><FieldLabel htmlFor={'cam-stream-' + index} help="Nazwa strumienia dokładnie taka jak w Twoim go2rtc (lista Streams albo plik go2rtc.yaml).">Strumień go2rtc</FieldLabel><input id={'cam-stream-' + index} value={item.stream} onChange={event => update(index, { stream: event.target.value })} placeholder="nvr_ch1" /></div>}
        {builtin && item.source === 'tuya' && <div className="form-field"><FieldLabel htmlFor={'cam-device-' + index} help="iot.tuya.com → Twój projekt → Devices → All Devices → kolumna Device ID przy kamerze. Kamera musi być na tym samym koncie aplikacji co brama.">Device ID kamery</FieldLabel>
          <input id={'cam-device-' + index} value={item.device_id} maxLength={64} autoComplete="off" onChange={event => update(index, { device_id: event.target.value.trim(), uid: '' })} placeholder="bf12ab34cd56ef78gh90ij" /></div>}
        {builtin && item.source === 'rtsp' && <div className="form-field"><FieldLabel htmlFor={'cam-rtsp-' + index} help={<>Adres strumienia z hasłem, np. <code>rtsp://admin:HASLO@192.168.1.64:554/Streaming/Channels/102</code> (Hikvision, podstrumień). Hasło zostaje na tym komputerze i nie jest pokazywane po zapisaniu.</>}>Adres RTSP</FieldLabel>
          <input id={'cam-rtsp-' + index} type="password" autoComplete="new-password" value={item.rtsp_url === SECRET_MASK ? '' : item.rtsp_url} maxLength={300}
            placeholder={item.rtsp_url === SECRET_MASK ? 'zapisany ✓ — wpisz nowy tylko, aby zmienić' : 'rtsp://admin:hasło@192.168.1.64:554/...'}
            onChange={event => update(index, { rtsp_url: event.target.value.trim() === '' && item.rtsp_set ? SECRET_MASK : event.target.value.trim() })} /></div>}
      </div>
      <div className="camera-card-actions">
        {builtin && item.source === 'tuya' && <button type="button" className="button secondary" disabled={busy} onClick={() => { void check(index) }}><Search aria-hidden="true" />Sprawdź kamerę</button>}
        {builtin && <label className="voice-check"><input type="checkbox" checked={item.resolution === 'hd'} onChange={event => update(index, { resolution: event.target.checked ? 'hd' : 'sd' })} />Wysoka jakość (HD)</label>}
        <label className="voice-check"><input type="checkbox" checked={item.enabled} onChange={event => update(index, { enabled: event.target.checked })} />Aktywna</label>
        <button type="button" className="icon-button" aria-label={'Usuń kamerę ' + (item.name || index + 1)} onClick={() => setDraft({ ...draft, cameras: draft.cameras.filter((_, position) => position !== index) })}><Trash2 aria-hidden="true" /></button>
      </div>
      {checks[index] && <p className="workshop-caption" role="status">{checks[index]}</p>}
      {builtin && item.source === 'tuya' && item.device_id && !item.uid && !checks[index] && <p className="workshop-caption">Kliknij „Sprawdź kamerę”, zanim zapiszesz.</p>}
    </li>)}</ul>
    <div className="camera-actions">
      <button type="button" className="button subtle" disabled={draft.cameras.length >= 16} onClick={() => setDraft({ ...draft, enabled: true, cameras: [...draft.cameras, blankCamera(draft.cameras, draft.mode)] })}><Plus aria-hidden="true" />Dodaj kamerę</button>
      <button type="button" className="button primary" disabled={busy} onClick={() => { void save() }}><Save aria-hidden="true" />Zapisz</button>
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
    <details className="settings-more"><summary>Więcej opcji</summary>
      <div className="camera-config-grid">
        <div className="form-field"><FieldLabel htmlFor="camera-refresh" help="Jak często odświeżać obraz, w milisekundach. 1000 = raz na sekundę. Przy słabym internecie w telefonie ustaw 2000–3000.">Odświeżanie (ms)</FieldLabel><input id="camera-refresh" type="number" min={250} max={10000} step={250} value={draft.refresh_ms} onChange={event => setDraft({ ...draft, refresh_ms: Number(event.target.value) })} /></div>
      </div>
      <label className="voice-check"><input type="checkbox" checked={!builtin} onChange={event => {
        const mode = event.target.checked ? 'external' : 'builtin'
        setDraft({ ...draft, mode, cameras: draft.cameras.map(item => ({ ...item, source: mode === 'external' ? 'go2rtc' : item.source === 'go2rtc' ? 'tuya' : item.source })) })
      }} />Używam własnego go2rtc (zaawansowane)</label>
      {!builtin && <div className="form-field"><FieldLabel htmlFor="go2rtc-url" help={<>Adres Twojego programu go2rtc, zwykle <code>http://127.0.0.1:1984</code>. Kamery i hasła ustawiasz wtedy w jego pliku go2rtc.yaml, a tutaj tylko nazwy strumieni.</>}>Adres go2rtc</FieldLabel><input id="go2rtc-url" value={draft.go2rtc_url} onChange={event => setDraft({ ...draft, go2rtc_url: event.target.value })} placeholder="http://127.0.0.1:1984" /></div>}
    </details>
  </div>
}

const CAMERA_DEFAULTS: Omit<CameraEntry, 'id' | 'name' | 'enabled'> = { source: 'go2rtc', stream: '', device_id: '', uid: '', resolution: 'sd', rtsp_url: '' }
/** Older saved configs and minimal test doubles may miss the 0.18 fields. */
function normalise(config: CameraConfig): CameraConfig {
  return { ...config, mode: config.mode ?? 'external', cameras: config.cameras.map(item => ({ ...CAMERA_DEFAULTS, ...(item as Partial<CameraEntry>) } as CameraEntry)) }
}

/** Camera settings (owner): go2rtc address and streams. Preview stays in the Cameras view. */
export function CameraSettings({ credential, onUnauthorized }: { credential: string; onUnauthorized: () => void }) {
  const [saved, setSaved] = useState(false)
  return <div className="settings-block">
    <h2 className="panel-heading"><CameraIcon aria-hidden="true" />Kamery</h2>
    <p className="panel-description">Dodaj kamerę, wybierz rodzaj i wpisz Device ID (Setti) albo adres RTSP. JARVIS sam uruchamia i ustawia go2rtc na tym komputerze.</p>
    <ConfigEditor credential={credential} onUnauthorized={onUnauthorized} onSaved={() => setSaved(true)} />
    {saved && <p className="workshop-caption" role="status">Zapisano. Podgląd: <a href="#/cameras">Kamery</a>.</p>}
  </div>
}

export function CamerasPanel(props: Props) { return <CamerasWorkspace key={props.credential} {...props} /> }

function CamerasWorkspace({ credential, onUnauthorized, owner }: Props) {
  const [list, setList] = useState<CameraList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(true)
  const [focused, setFocused] = useState<string | null>(null)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized
  const [stableUnauthorized] = useState(() => () => unauthorized.current())
  useEffect(() => {
    const controller = new AbortController()
    readCameras(credential, controller.signal).then(setList).catch(failure => {
      if (controller.signal.aborted) return
      if (failure instanceof ApiError && failure.status === 401) unauthorized.current(); else setError(message(failure))
    })
    return () => controller.abort()
  }, [credential])
  const shown = list?.cameras.filter(item => focused === null || item.id === focused) ?? []
  return <div className="cameras-feature">
    {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div>}
    <section className="panel" aria-labelledby="cameras-title">
      <div className="camera-head"><h2 className="panel-heading" id="cameras-title"><CameraIcon aria-hidden="true" />Podgląd</h2>
        <div className="camera-actions">
          {focused && <button type="button" className="button subtle" onClick={() => setFocused(null)}><Maximize2 aria-hidden="true" />Wszystkie kamery</button>}
          <button type="button" className="button secondary" onClick={() => setRunning(value => !value)}>{running ? <><Pause aria-hidden="true" />Wstrzymaj</> : <><Play aria-hidden="true" />Wznów</>}</button>
        </div></div>
      {!list ? <p role="status">Odczytywanie kamer…</p> : !list.enabled || list.cameras.length === 0
        ? <p className="panel-description">{owner ? <>Brak skonfigurowanych kamer. Dodaj je w <a href="#/settings/cameras">Ustawienia → Kamery</a>.</> : 'Właściciel nie udostępnił jeszcze kamer.'}</p>
        : <div className={'camera-grid' + (focused ? ' is-single' : '')}>{shown.map(item => <CameraView key={item.id} camera={item} credential={credential} refreshMs={list.refresh_ms} running={running} onUnauthorized={stableUnauthorized} onOpen={() => setFocused(current => current ? null : item.id)} />)}</div>}
      <p className="panel-description camera-note">Obraz jest pobierany klatka po klatce przez JARVIS (bez bezpośredniego połączenia telefonu z kamerą). Przy słabym łączu zwiększ odświeżanie.</p>
    </section>
  </div>
}

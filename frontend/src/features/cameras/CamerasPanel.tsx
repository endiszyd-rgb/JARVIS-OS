import { useEffect, useRef, useState } from 'react'
import { Camera as CameraIcon, CircleAlert, Maximize2, Pause, Play, Plus, Save, Trash2 } from 'lucide-react'
import { ApiError, apiRequest } from '../../api'
import { FieldLabel } from '../../components/HelpTip'
import './cameras.css'

interface Props { credential: string; onUnauthorized: () => void; owner: boolean }
export interface CameraSummary { id: string; name: string }
export interface CameraList { enabled: boolean; refresh_ms: number; cameras: CameraSummary[] }
export interface CameraEntry { id: string; name: string; stream: string; enabled: boolean }
export interface CameraConfig { enabled: boolean; go2rtc_url: string; refresh_ms: number; cameras: CameraEntry[] }

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

function ConfigEditor({ credential, onSaved, onUnauthorized }: { credential: string; onSaved: () => void; onUnauthorized: () => void }) {
  const [draft, setDraft] = useState<CameraConfig | null>(null)
  const [revision, setRevision] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    apiRequest('/api/v1/cameras/config', controller.signal, credential).then(value => {
      if (!object(value) || !object(value.config) || !Number.isSafeInteger(value.revision)) return invalid()
      setDraft(value.config as unknown as CameraConfig); setRevision(value.revision as number)
    }).catch(failure => { if (!controller.signal.aborted) { if (failure instanceof ApiError && failure.status === 401) onUnauthorized(); else setError(message(failure)) } })
    return () => controller.abort()
  }, [credential, onUnauthorized])
  if (!draft) return error ? <p className="form-error" role="alert">{error}</p> : <p role="status">Odczytywanie konfiguracji…</p>
  const update = (index: number, patch: Partial<CameraEntry>) => setDraft({ ...draft, cameras: draft.cameras.map((item, position) => position === index ? { ...item, ...patch } : item) })
  async function save() {
    if (!draft || busy) return
    setBusy(true); setError(null)
    try {
      const value = await apiRequest('/api/v1/cameras/config', new AbortController().signal, credential, { method: 'PUT', body: { revision, config: draft } })
      if (!object(value) || !Number.isSafeInteger(value.revision)) return invalid()
      setRevision(value.revision as number); onSaved()
    } catch (failure) { if (failure instanceof ApiError && failure.status === 401) onUnauthorized(); else setError(message(failure)) } finally { setBusy(false) }
  }
  return <div className="camera-config">
    <label className="voice-check"><input type="checkbox" checked={draft.enabled} onChange={event => setDraft({ ...draft, enabled: event.target.checked })} />Podgląd kamer włączony</label>
    <div className="camera-config-grid">
      <div className="form-field"><FieldLabel htmlFor="go2rtc-url" help={<>Adres programu go2rtc na komputerze warsztatowym — zwykle <code>http://127.0.0.1:1984</code>. To go2rtc łączy się z kamerami Setti (źródło Tuya) i trzyma ich hasła; JARVIS pobiera od niego tylko obraz.</>}>Adres go2rtc</FieldLabel><input id="go2rtc-url" value={draft.go2rtc_url} onChange={event => setDraft({ ...draft, go2rtc_url: event.target.value })} placeholder="http://127.0.0.1:1984" /></div>
      <div className="form-field"><FieldLabel htmlFor="camera-refresh" help="Jak często odświeżać obraz, w milisekundach. 1000 = raz na sekundę. Przy słabym internecie w telefonie ustaw 2000–3000.">Odświeżanie (ms)</FieldLabel><input id="camera-refresh" type="number" min={250} max={10000} step={250} value={draft.refresh_ms} onChange={event => setDraft({ ...draft, refresh_ms: Number(event.target.value) })} /></div>
    </div>
    <ul className="camera-rows">{draft.cameras.map((item, index) => <li key={index} className="camera-row">
      <div className="form-field"><FieldLabel htmlFor={'cam-id-' + index} help="Krótka nazwa techniczna bez spacji i polskich liter, np. zewnetrzna.">Identyfikator</FieldLabel><input id={'cam-id-' + index} value={item.id} onChange={event => update(index, { id: event.target.value.toLowerCase() })} placeholder="brama" /></div>
      <div className="form-field"><FieldLabel htmlFor={'cam-name-' + index} help="Nazwa widoczna pod podglądem, np. „Wjazd” albo „Hala”.">Nazwa</FieldLabel><input id={'cam-name-' + index} value={item.name} onChange={event => update(index, { name: event.target.value })} placeholder="Wjazd" /></div>
      <div className="form-field"><FieldLabel htmlFor={'cam-stream-' + index} help="Nazwa strumienia dokładnie taka jak w go2rtc (lista Streams w go2rtc albo plik go2rtc.yaml), np. kamera_zewn.">Strumień go2rtc</FieldLabel><input id={'cam-stream-' + index} value={item.stream} onChange={event => update(index, { stream: event.target.value })} placeholder="nvr_ch1" /></div>
      <label className="voice-check"><input type="checkbox" checked={item.enabled} onChange={event => update(index, { enabled: event.target.checked })} />Aktywna</label>
      <button type="button" className="icon-button" aria-label={'Usuń kamerę ' + (item.name || index + 1)} onClick={() => setDraft({ ...draft, cameras: draft.cameras.filter((_, position) => position !== index) })}><Trash2 aria-hidden="true" /></button>
    </li>)}</ul>
    <div className="camera-actions">
      <button type="button" className="button subtle" disabled={draft.cameras.length >= 16} onClick={() => setDraft({ ...draft, cameras: [...draft.cameras, { id: 'kamera' + (draft.cameras.length + 1), name: 'Kamera ' + (draft.cameras.length + 1), stream: '', enabled: true }] })}><Plus aria-hidden="true" />Dodaj kamerę</button>
      <button type="button" className="button primary" disabled={busy} onClick={() => { void save() }}><Save aria-hidden="true" />Zapisz</button>
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
  </div>
}

/** Camera settings (owner): go2rtc address and streams. Preview stays in the Cameras view. */
export function CameraSettings({ credential, onUnauthorized }: { credential: string; onUnauthorized: () => void }) {
  const [saved, setSaved] = useState(false)
  return <div className="settings-block">
    <h2 className="panel-heading"><CameraIcon aria-hidden="true" />Kamery</h2>
    <p className="panel-description">Kamery Setti łączysz w go2rtc (instrukcja: docs/DOSTEP-ZDALNY.md), a tutaj podajesz, które strumienie pokazywać.</p>
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

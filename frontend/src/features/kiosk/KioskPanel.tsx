import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Camera, Check, Mic, MicOff, PackageSearch, Send, X } from 'lucide-react'
import { ApiError, apiRequest } from '../../api'
import { GateTile } from '../gate/GateTile'
import { CameraView, readCameras } from '../cameras/CamerasPanel'
import type { CameraList } from '../cameras/CamerasPanel'
import { TodayCard } from '../workshop/TodayCard'
import { recognitionConstructor } from '../voice/recognition'
import type { RecognitionLike } from '../voice/recognition'
import './kiosk.css'

interface Props { credential: string; onUnauthorized: () => void; workshopData: boolean }
interface Reply { reply: string; handled?: boolean; device?: { status?: string } }

const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)

export async function sendCommand(credential: string, text: string): Promise<Reply> {
  const value = await apiRequest('/api/v1/voice/command', new AbortController().signal, credential, { body: { text: text.slice(0, 500) }, timeoutMs: 30000 })
  if (!object(value) || typeof value.reply !== 'string') throw new ApiError(null, 'response')
  return value as unknown as Reply
}

function speak(text: string) {
  try {
    const synth = window.speechSynthesis
    if (!synth || typeof SpeechSynthesisUtterance !== 'function') return
    synth.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'pl-PL'
    synth.speak(utterance)
  } catch { /* speech output is optional */ }
}

/** One screen for the workshop floor or a phone: talk to Jarvis, gate, cameras and today's work. */
export function KioskPanel({ credential, onUnauthorized, workshopData }: Props) {
  const [listening, setListening] = useState(false)
  const [heard, setHeard] = useState('')
  const [reply, setReply] = useState<Reply | null>(null)
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [cameras, setCameras] = useState<CameraList | null>(null)
  const recognizer = useRef<RecognitionLike | null>(null)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized
  const [stableUnauthorized] = useState(() => () => unauthorized.current())
  const Recognition = recognitionConstructor()

  useEffect(() => {
    const controller = new AbortController()
    readCameras(credential, controller.signal).then(value => { if (!controller.signal.aborted) setCameras(value) }).catch(() => { /* cameras are optional here */ })
    return () => { controller.abort(); recognizer.current?.abort() }
  }, [credential])

  async function run(text: string) {
    const command = text.trim()
    if (!command || busy) return
    setBusy(true); setHeard(command)
    try {
      const result = await sendCommand(credential, command)
      setReply(result); speak(result.reply)
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) { unauthorized.current(); return }
      setReply({ reply: failure instanceof ApiError ? failure.message : 'Nie udało się wysłać polecenia.' })
    } finally { setBusy(false) }
  }

  function listen() {
    if (!Recognition) return
    if (listening) { recognizer.current?.stop(); return }
    const recognition = new Recognition()
    recognition.lang = 'pl-PL'; recognition.continuous = false; recognition.interimResults = false; recognition.maxAlternatives = 1
    recognition.onresult = event => { const result = event.results[event.resultIndex]; if (result?.isFinal || result) void run(result[0].transcript) }
    recognition.onerror = event => { if (event.error !== 'aborted' && event.error !== 'no-speech') setReply({ reply: event.error === 'not-allowed' ? 'Brak zgody na mikrofon. Zezwól w ustawieniach przeglądarki.' : 'Nie udało się rozpoznać mowy. Spróbuj ponownie albo wpisz polecenie.' }) }
    recognition.onend = () => { setListening(false); recognizer.current = null }
    recognition.onstart = () => setListening(true)
    recognizer.current = recognition
    try { recognition.start() } catch { setListening(false) }
  }

  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const value = typed; setTyped(''); void run(value) }
  const confirming = reply?.device?.status === 'confirmation_required'
  const shown = cameras?.enabled ? cameras.cameras.slice(0, 4) : []

  return <div className="kiosk">
    <section className="panel kiosk-voice" aria-labelledby="kiosk-voice-title">
      <h2 className="panel-heading" id="kiosk-voice-title">Powiedz do Jarvisa</h2>
      {Recognition
        ? <button type="button" className={'kiosk-mic' + (listening ? ' is-listening' : '')} aria-pressed={listening} disabled={busy} onClick={listen}>
            {listening ? <MicOff aria-hidden="true" /> : <Mic aria-hidden="true" />}<span>{listening ? 'Słucham… (dotknij, aby zakończyć)' : busy ? 'Wykonuję…' : 'Dotknij i mów'}</span></button>
        : <p className="workshop-caption">Ta przeglądarka nie rozpoznaje mowy — wpisz polecenie poniżej.</p>}
      <form className="kiosk-type" onSubmit={submit}>
        <label className="visually-hidden" htmlFor="kiosk-command">Polecenie</label>
        <input id="kiosk-command" value={typed} onChange={event => setTyped(event.target.value)} placeholder="np. brama" maxLength={500} disabled={busy} autoComplete="off" />
        <button type="submit" className="icon-button" aria-label="Wyślij polecenie" disabled={busy || !typed.trim()}><Send aria-hidden="true" /></button>
      </form>
      <div className="kiosk-chips">
        {workshopData && <button type="button" className="button subtle" disabled={busy} onClick={() => { void run('co dziś') }}>Co dziś?</button>}
        {workshopData && <button type="button" className="button subtle" disabled={busy} onClick={() => { void run('co trzeba zamówić') }}><PackageSearch aria-hidden="true" />Części</button>}
        <button type="button" className="button subtle" disabled={busy} onClick={() => { void run('stan bramy') }}>Stan bramy</button>
      </div>
      {(heard || reply) && <div className="kiosk-reply" role="status" aria-live="polite">
        {heard && <p className="kiosk-heard">„{heard}”</p>}
        {reply && <p>{reply.reply}</p>}
        {confirming && <div className="kiosk-confirm"><button type="button" className="button primary" disabled={busy} onClick={() => { void run('tak') }}><Check aria-hidden="true" />Tak</button><button type="button" className="button secondary" disabled={busy} onClick={() => { void run('nie') }}><X aria-hidden="true" />Nie</button></div>}
      </div>}
    </section>
    <GateTile credential={credential} onUnauthorized={onUnauthorized} />
    {shown.length > 0 && cameras && <section className="panel" aria-labelledby="kiosk-cameras-title">
      <h2 className="panel-heading" id="kiosk-cameras-title"><Camera aria-hidden="true" />Kamery</h2>
      <div className="camera-grid kiosk-cameras">{shown.map(item => <CameraView key={item.id} camera={item} credential={credential} refreshMs={Math.max(cameras.refresh_ms, 2000)} running onUnauthorized={stableUnauthorized} onOpen={() => { window.location.hash = '#/cameras' }} />)}</div>
    </section>}
    {workshopData && <TodayCard credential={credential} onUnauthorized={onUnauthorized} compact autoLoad />}
  </div>
}

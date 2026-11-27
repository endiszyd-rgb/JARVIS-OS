import { useCallback, useEffect, useRef, useState } from 'react'
import { AudioLines, CircleAlert, Ear, Mic, MicOff } from 'lucide-react'
import { ApiError } from '../../api'
import { defaultVoiceConfig, readGate, readVoiceConfig, sendVoiceMessage, synthesizeWav, transcribeWav } from '../gate/api'
import type { GateStatus, VoiceConfig } from '../gate/api'
import { stateTone } from '../gate/GatePanel'
import { afterWakeWord, encodeWav16k, looksLikeDeviceCommand, recognitionConstructor } from './recognition'
import type { RecognitionLike } from './recognition'
import './voice.css'

interface Props { credential: string; onUnauthorized: () => void; owner?: boolean }
type Phase = 'off' | 'listening' | 'armed' | 'processing' | 'speaking' | 'confirming' | 'recording'
interface Line { id: number; who: 'you' | 'jarvis' | 'system'; text: string }
const phaseLabel: Record<Phase, string> = { off: 'WYŁĄCZONY', listening: 'NASŁUCH', armed: 'SŁUCHAM POLECENIA', processing: 'PRZETWARZANIE', speaking: 'MÓWIĘ', confirming: 'CZEKAM NA „TAK”', recording: 'NAGRYWANIE' }
const message = (error: unknown) => error instanceof ApiError ? error.message : 'Nie udało się wykonać żądania. Spróbuj ponownie.'

export function VoicePanel(props: Props) { return <VoiceWorkspace key={props.credential} {...props} /> }

function VoiceWorkspace({ credential, onUnauthorized, owner = true }: Props) {
  const [config, setConfig] = useState<VoiceConfig>(defaultVoiceConfig)
  const [wyomingAvailable, setWyomingAvailable] = useState(false)
  const [phase, setPhase] = useState<Phase>('off')
  const [lines, setLines] = useState<Line[]>([])
  const [interim, setInterim] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [gate, setGate] = useState<GateStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const supported = recognitionConstructor() !== null
  const recognizer = useRef<RecognitionLike | null>(null)
  const active = useRef(false)
  const phaseRef = useRef<Phase>('off')
  const session = useRef<string | null>(null)
  const armedTimer = useRef<number | null>(null)
  const counter = useRef(0)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized
  const configRef = useRef(config)
  configRef.current = config
  const recorder = useRef<{ context: AudioContext; stream: MediaStream; chunks: Float32Array[]; node: AudioWorkletNode } | null>(null)

  const setPhaseBoth = (next: Phase) => { phaseRef.current = next; setPhase(next) }
  const say = useCallback((who: Line['who'], text: string) => setLines(previous => [...previous.slice(-39), { id: ++counter.current, who, text }]), [])

  useEffect(() => {
    const controller = new AbortController()
    const voiceSettings = owner ? readVoiceConfig(credential, controller.signal) : Promise.resolve({ config: defaultVoiceConfig, revision: 0, wyomingAvailable: false })
    Promise.all([voiceSettings, readGate(credential, controller.signal)]).then(([voice, overview]) => {
      if (controller.signal.aborted) return
      setConfig(voice.config); setWyomingAvailable(voice.wyomingAvailable); setGate(overview.gate)
    }).catch(failure => { if (!controller.signal.aborted) { if (failure instanceof ApiError && failure.status === 401) unauthorized.current(); else setError(message(failure)) } })
    return () => { controller.abort(); stopAll() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credential])

  function stopAll() {
    active.current = false
    if (armedTimer.current) window.clearTimeout(armedTimer.current)
    const current = recognizer.current
    recognizer.current = null
    if (current) { current.onend = null; current.onresult = null; current.onerror = null; try { current.abort() } catch { /* already stopped */ } }
    window.speechSynthesis?.cancel()
    void stopRecording(false)
    setPhaseBoth('off'); setInterim('')
  }

  // ---- speaking -------------------------------------------------------------------------------
  async function speak(text: string) {
    if (!configRef.current.speak_replies) return
    const previous = phaseRef.current
    setPhaseBoth('speaking')
    pauseRecognition()
    try {
      if (configRef.current.engine === 'wyoming' && wyomingAvailable) {
        const blob = await synthesizeWav(credential, new AbortController().signal, text)
        await new Promise<void>(resolve => { const audio = new Audio(URL.createObjectURL(blob)); audio.onended = () => resolve(); audio.onerror = () => resolve(); void audio.play().catch(() => resolve()) })
      } else if ('speechSynthesis' in window) {
        await new Promise<void>(resolve => {
          const utterance = new SpeechSynthesisUtterance(text)
          utterance.lang = configRef.current.language
          const voice = window.speechSynthesis.getVoices().find(item => item.lang.replace('_', '-').toLowerCase().startsWith(configRef.current.language.slice(0, 2)))
          if (voice) utterance.voice = voice
          utterance.onend = () => resolve(); utterance.onerror = () => resolve()
          window.speechSynthesis.cancel(); window.speechSynthesis.speak(utterance)
          window.setTimeout(resolve, 15000)
        })
      }
    } finally {
      if (active.current) { setPhaseBoth(previous === 'speaking' ? 'listening' : previous); resumeRecognition() }
      else setPhaseBoth('off')
    }
  }

  // ---- command handling -----------------------------------------------------------------------
  async function handleCommand(text: string) {
    const trimmed = text.trim()
    if (!trimmed) return
    say('you', trimmed)
    const confirming = phaseRef.current === 'confirming'
    if (!confirming && !configRef.current.send_to_model && !looksLikeDeviceCommand(trimmed)) {
      say('system', 'To nie wygląda na polecenie urządzenia. Włącz „wysyłaj inne zdania do modelu”, aby rozmawiać z AI.')
      return
    }
    setPhaseBoth('processing'); setBusy(true)
    try {
      const reply = await sendVoiceMessage(credential, new AbortController().signal, trimmed, session.current, !owner)
      session.current = reply.session_id
      say('jarvis', reply.reply)
      if (reply.device?.gate) setGate(reply.device.gate)
      await speak(reply.reply)
      if (reply.device?.status === 'confirmation_required') {
        setPhaseBoth('confirming')
        if (armedTimer.current) window.clearTimeout(armedTimer.current)
        armedTimer.current = window.setTimeout(() => { if (phaseRef.current === 'confirming') { setPhaseBoth(active.current ? 'listening' : 'off'); say('system', 'Minął czas na potwierdzenie.') } }, 12000)
      } else if (active.current && phaseRef.current !== 'off') setPhaseBoth('listening')
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) { stopAll(); unauthorized.current(); return }
      say('system', message(failure))
      if (active.current) setPhaseBoth('listening')
    } finally { setBusy(false) }
  }

  // ---- browser recognition (wake word) -------------------------------------------------------
  const paused = useRef(false)
  function pauseRecognition() { paused.current = true; try { recognizer.current?.abort() } catch { /* ignore */ } }
  function resumeRecognition() { paused.current = false; if (active.current && configRef.current.engine === 'browser') startRecognition() }

  function startRecognition() {
    const Constructor = recognitionConstructor()
    if (!Constructor || !active.current || paused.current) return
    try { recognizer.current?.abort() } catch { /* ignore */ }
    const instance = new Constructor()
    instance.lang = configRef.current.language; instance.continuous = true; instance.interimResults = true; instance.maxAlternatives = 1
    instance.onresult = event => {
      let finalText = '', interimText = ''
      for (let index = event.resultIndex; index < event.results.length; index++) {
        const result = event.results[index]
        if (result.isFinal) finalText += result[0].transcript + ' '; else interimText += result[0].transcript
      }
      setInterim(interimText)
      if (!finalText.trim()) return
      setInterim('')
      const current = phaseRef.current
      if (current === 'processing' || current === 'speaking') return
      if (current === 'confirming' || current === 'armed') {
        if (armedTimer.current) window.clearTimeout(armedTimer.current)
        const stripped = afterWakeWord(finalText, configRef.current.wake_word)
        void handleCommand(stripped === null ? finalText : stripped)
        return
      }
      if (!configRef.current.wake_listening) { void handleCommand(finalText); return }
      const command = afterWakeWord(finalText, configRef.current.wake_word)
      if (command === null) return
      if (command) { void handleCommand(command); return }
      setPhaseBoth('armed')
      void speak('Słucham.')
      armedTimer.current = window.setTimeout(() => { if (phaseRef.current === 'armed') setPhaseBoth('listening') }, 8000)
    }
    instance.onerror = event => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') { stopAll(); setError('Przeglądarka nie zezwoliła na mikrofon. Zezwól na dostęp do mikrofonu dla tej strony i włącz nasłuch ponownie.') }
      else if (event.error === 'network') setError('Rozpoznawanie mowy w przeglądarce wymaga połączenia z internetem (Chrome/Edge). Alternatywa: lokalne Wyoming.')
      else if (event.error !== 'no-speech' && event.error !== 'aborted') setError('Rozpoznawanie mowy: ' + event.error)
    }
    instance.onend = () => { if (active.current && !paused.current && recognizer.current === instance) window.setTimeout(startRecognition, 250) }
    recognizer.current = instance
    try { instance.start() } catch { /* start() throws when already started */ }
  }

  function toggleListening() {
    setError(null)
    if (active.current) { stopAll(); say('system', 'Nasłuch wyłączony.'); return }
    if (!supported) { setError('Ta przeglądarka nie obsługuje rozpoznawania mowy. Użyj Chrome lub Edge albo włącz Wyoming.'); return }
    active.current = true; paused.current = false
    setPhaseBoth('listening')
    say('system', config.wake_listening ? `Nasłuch włączony. Powiedz „${config.wake_word}, otwórz bramę”.` : 'Nasłuch włączony. Mów polecenia bez słowa aktywującego.')
    startRecognition()
  }

  // ---- Wyoming push-to-talk --------------------------------------------------------------------
  async function startRecording() {
    if (recorder.current) return
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } })
      const context = new AudioContext()
      await context.audioWorklet.addModule('/ui/pcm_worklet.js')
      const node = new AudioWorkletNode(context, 'jarvis-pcm-capture', { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1] })
      const chunks: Float32Array[] = []
      node.port.onmessage = event => {
        const data = event.data as { type?: string; samples?: Float32Array; sequence?: number }
        if (data?.type === 'samples' && data.samples instanceof Float32Array) { if (chunks.length < 3000) chunks.push(data.samples); node.port.postMessage({ type: 'ack', sequence: data.sequence }) }
      }
      context.createMediaStreamSource(stream).connect(node); node.connect(context.destination)
      recorder.current = { context, stream, chunks, node }
      active.current = true
      setPhaseBoth('recording')
    } catch { setError('Nie udało się uruchomić mikrofonu.') }
  }
  async function stopRecording(send: boolean) {
    const current = recorder.current
    if (!current) return
    recorder.current = null
    try { current.node.port.postMessage({ type: 'stop' }) } catch { /* ignore */ }
    current.stream.getTracks().forEach(track => track.stop())
    const rate = current.context.sampleRate
    await current.context.close().catch(() => undefined)
    if (!send || current.chunks.length === 0) { if (phaseRef.current === 'recording') setPhaseBoth('off'); return }
    setPhaseBoth('processing'); setBusy(true)
    try {
      const text = await transcribeWav(credential, new AbortController().signal, encodeWav16k(current.chunks, rate))
      setBusy(false)
      const stripped = afterWakeWord(text, configRef.current.wake_word)
      await handleCommand(stripped === null ? text : stripped)
    } catch (failure) { setBusy(false); say('system', message(failure)) }
    finally { if (phaseRef.current !== 'confirming') { setPhaseBoth('off'); active.current = false } }
  }

  // ---- settings -------------------------------------------------------------------------------
  const browserMode = config.engine === 'browser'
  return <div className="voice-feature">
    {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div>}
    <section className="panel voice-console" aria-labelledby="voice-title" aria-busy={busy}>
      <div className="voice-head"><div><h2 className="panel-heading" id="voice-title"><AudioLines aria-hidden="true" />Sterowanie głosem</h2>
        <p className="panel-description">{browserMode ? 'Rozpoznawanie mowy przeglądarki (Chrome/Edge). Dźwięk jest przetwarzany przez usługę mowy przeglądarki.' : 'Lokalne Wyoming: przytrzymaj przycisk, mów, puść.'} Polecenia urządzeń wykonuje serwer JARVIS po sprawdzeniu uprawnień.</p></div></div>
      <div className={'voice-orb-row ' + (gate ? stateTone(gate.state) : '')}>
        <div className={'voice-orb phase-' + phase} aria-hidden="true"><span /><span /><span /></div>
        <div className="voice-readout" role="status" aria-live="polite">
          <p className="voice-readout-label">STAN ASYSTENTA</p>
          <p className="voice-readout-value">{phaseLabel[phase]}</p>
          <p className="voice-readout-meta">{interim ? '„' + interim + '…”' : gate ? `${gate.name}: ${gate.state_label}` : ' '}</p>
        </div>
      </div>
      <div className="voice-actions">
        {browserMode ? <button type="button" className={'button ' + (phase === 'off' ? 'primary' : 'secondary')} onClick={toggleListening} disabled={busy && phase === 'off'}>{phase === 'off' ? <Mic aria-hidden="true" /> : <MicOff aria-hidden="true" />}{phase === 'off' ? 'Włącz nasłuch' : 'Wyłącz nasłuch'}</button>
          : <button type="button" className={'button ' + (phase === 'recording' ? 'secondary' : 'primary')} disabled={!wyomingAvailable || busy}
            onPointerDown={() => { void startRecording() }} onPointerUp={() => { void stopRecording(true) }} onPointerLeave={() => { if (phase === 'recording') void stopRecording(true) }}
            onKeyDown={event => { if (event.key === ' ' || event.key === 'Enter') { event.preventDefault(); void startRecording() } }} onKeyUp={event => { if (event.key === ' ' || event.key === 'Enter') void stopRecording(true) }}>
            <Mic aria-hidden="true" />{phase === 'recording' ? 'Mów… (puść, aby wysłać)' : 'Przytrzymaj i mów'}</button>}
        <button type="button" className="button subtle" onClick={() => { void handleCommand('brama') }} disabled={busy}>Brama</button>
        <button type="button" className="button subtle" onClick={() => { void handleCommand('stan bramy') }} disabled={busy}>Stan bramy</button>
      </div>
      {!browserMode && !wyomingAvailable && <p className="voice-caption">Wyoming nie jest skonfigurowane na serwerze (JARVIS_VOICE_ENABLED, WYOMING_STT_URI, WYOMING_TTS_URI). Do czasu konfiguracji przełącz silnik na przeglądarkę.</p>}
      {browserMode && !supported && <p className="voice-caption">Ta przeglądarka nie udostępnia rozpoznawania mowy. Otwórz panel w Chrome lub Edge.</p>}
      <ol className="voice-transcript" aria-label="Przebieg rozmowy głosowej">{lines.map(line => <li key={line.id} className={'line-' + line.who}><span className="voice-who">{line.who === 'you' ? 'TY' : line.who === 'jarvis' ? 'JARVIS' : 'INFO'}</span>{line.text}</li>)}</ol>
      <p className="voice-caption"><Ear aria-hidden="true" /> Przykłady: „{config.wake_word}, otwórz bramę”, „{config.wake_word}, zamknij bramę”, „{config.wake_word}, brama stop”, „{config.wake_word}, jaki jest stan bramy”. Gdy brama wymaga potwierdzenia, odpowiedz „tak” lub „nie”.</p>
    </section>

    {owner && <p className="voice-caption">Słowo aktywujące, język i czytanie odpowiedzi: <a href="#/settings/voice">Ustawienia → Głos</a>.</p>}
  </div>
}

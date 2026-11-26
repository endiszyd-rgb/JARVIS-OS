/* Minimal typings for the Chrome/Edge Web Speech API; lib.dom does not ship the constructor. */
export interface RecognitionResultLike { isFinal: boolean; 0: { transcript: string; confidence: number }; length: number }
export interface RecognitionEventLike { resultIndex: number; results: ArrayLike<RecognitionResultLike> }
export interface RecognitionErrorLike { error: string; message?: string }
export interface RecognitionLike {
  lang: string; continuous: boolean; interimResults: boolean; maxAlternatives: number
  onresult: ((event: RecognitionEventLike) => void) | null
  onerror: ((event: RecognitionErrorLike) => void) | null
  onend: (() => void) | null
  onstart: (() => void) | null
  start(): void; stop(): void; abort(): void
}
type RecognitionConstructor = new () => RecognitionLike

export function recognitionConstructor(): RecognitionConstructor | null {
  const scope = window as unknown as { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor }
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null
}

export function normalize(text: string): string {
  return text.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/ł/g, 'l').replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim()
}

/** Returns the command following the wake word, '' when only the wake word was said, or null when absent. */
export function afterWakeWord(text: string, wakeWord: string): string | null {
  const spoken = normalize(text), wake = normalize(wakeWord)
  if (!wake) return spoken
  const index = spoken.indexOf(wake)
  if (index === -1) return null
  return spoken.slice(index + wake.length).trim()
}

const DEVICE = /\b(bram|garaz|szlaban|wjazd|czesc|zamow)/
const CONTROL = /^(tak|nie|anuluj|stop|potwierdzam|ok|okej|zgoda|dawaj|zrob to)\b/
export function looksLikeDeviceCommand(text: string): boolean {
  const spoken = normalize(text)
  return DEVICE.test(spoken) || CONTROL.test(spoken)
}

/** Encode mono float samples (any rate) as a 16 kHz 16-bit PCM WAV blob for the Wyoming transcriber. */
export function encodeWav16k(chunks: Float32Array[], sourceRate: number): Blob {
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0)
  const joined = new Float32Array(total)
  let offset = 0
  for (const chunk of chunks) { joined.set(chunk, offset); offset += chunk.length }
  const ratio = sourceRate / 16000
  const length = Math.max(1, Math.floor(joined.length / ratio))
  const pcm = new Int16Array(length)
  for (let index = 0; index < length; index++) {
    const position = index * ratio, base = Math.floor(position), next = Math.min(base + 1, joined.length - 1), weight = position - base
    const sample = joined[base] * (1 - weight) + joined[next] * weight
    pcm[index] = Math.max(-32768, Math.min(32767, Math.round(sample * 32767)))
  }
  const header = new ArrayBuffer(44), view = new DataView(header)
  const ascii = (at: number, text: string) => { for (let i = 0; i < text.length; i++) view.setUint8(at + i, text.charCodeAt(i)) }
  ascii(0, 'RIFF'); view.setUint32(4, 36 + pcm.byteLength, true); ascii(8, 'WAVE'); ascii(12, 'fmt ')
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, 16000, true)
  view.setUint32(28, 32000, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true); ascii(36, 'data'); view.setUint32(40, pcm.byteLength, true)
  return new Blob([header, pcm.buffer], { type: 'audio/wav' })
}

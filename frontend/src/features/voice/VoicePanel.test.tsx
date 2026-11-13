import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { VoicePanel } from './VoicePanel'
import { afterWakeWord, encodeWav16k, looksLikeDeviceCommand, normalize } from './recognition'
import type { RecognitionEventLike, RecognitionLike } from './recognition'

const KEY = 'synthetic-voice-owner-key'
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const gate = { name: 'Brama warsztatu', driver: 'simulator', live: false, state: 'closed', state_label: 'zamknięta', changed: null, last_action: null, require_confirmation: false, pulse: false }
const voiceConfig = { engine: 'browser', wake_word: 'jarvis', wake_listening: true, speak_replies: false, language: 'pl-PL', send_to_model: false }
afterEach(() => vi.unstubAllGlobals())

describe('recognition helpers', () => {
  it('normalizes Polish text and extracts the command after the wake word', () => {
    expect(normalize('Jarvis, OTWÓRZ bramę!')).toBe('jarvis otworz brame')
    expect(afterWakeWord('Jarvis otwórz bramę', 'jarvis')).toBe('otworz brame')
    expect(afterWakeWord('hej jarvis', 'jarvis')).toBe('')
    expect(afterWakeWord('otwórz bramę', 'jarvis')).toBeNull()
  })
  it('recognizes device-related phrases and confirmations only', () => {
    expect(looksLikeDeviceCommand('otwórz bramę')).toBe(true)
    expect(looksLikeDeviceCommand('tak')).toBe(true)
    expect(looksLikeDeviceCommand('jaka jest pogoda')).toBe(false)
  })
  it('encodes a 16 kHz 16-bit mono WAV', () => {
    const blob = encodeWav16k([new Float32Array([0, 0.5, -0.5, 1])], 32000)
    expect(blob.type).toBe('audio/wav')
    expect(blob.size).toBe(44 + 2 * 2)
  })
})

class FakeRecognition implements RecognitionLike {
  static instances: FakeRecognition[] = []
  lang = ''; continuous = false; interimResults = false; maxAlternatives = 1
  onresult: ((event: RecognitionEventLike) => void) | null = null
  onerror: RecognitionLike['onerror'] = null
  onend: (() => void) | null = null
  onstart: (() => void) | null = null
  started = false
  constructor() { FakeRecognition.instances.push(this) }
  start() { this.started = true }
  stop() { this.started = false }
  abort() { this.started = false }
  hear(transcript: string) { this.onresult?.({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript, confidence: 0.9 }, length: 1 }] }) }
}

describe('Voice panel', () => {
  it('starts browser recognition on demand and sends a wake-word gate command as voice chat', async () => {
    FakeRecognition.instances = []
    vi.stubGlobal('SpeechRecognition', FakeRecognition)
    const fetch = vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/config/voice') return json({ config: voiceConfig, revision: 0, wyoming_available: false })
      if (path === '/api/v1/devices/gate') return json({ gate, config: {}, revision: 0, events: [], drivers: [] })
      if (path === '/api/v1/chat') {
        const body = JSON.parse(String(options.body))
        expect(body.input_mode).toBe('voice'); expect(body.message).toBe('otworz brame')
        return json({ reply: 'Otwieram: Brama warsztatu.', session_id: '11111111-1111-4111-8111-111111111111', model: 'parser', device: { status: 'executed', action: 'open', gate: { ...gate, state: 'opening', state_label: 'otwiera się' } } })
      }
      return json({}, 404)
    })
    vi.stubGlobal('fetch', fetch)
    render(<VoicePanel credential={KEY} onUnauthorized={vi.fn()} />)
    await screen.findByText('Brama warsztatu: zamknięta')
    expect(FakeRecognition.instances).toHaveLength(0)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Włącz nasłuch' }))
    expect(FakeRecognition.instances).toHaveLength(1)
    const recognition = FakeRecognition.instances[0]
    expect(recognition.started && recognition.continuous && recognition.lang === 'pl-PL').toBe(true)
    act(() => recognition.hear('jaka jest pogoda'))
    expect(fetch.mock.calls.some(call => String(call[0]) === '/api/v1/chat')).toBe(false)
    act(() => recognition.hear('Jarvis, otwórz bramę'))
    await screen.findByText('Otwieram: Brama warsztatu.')
    await waitFor(() => expect(screen.getByText('Brama warsztatu: otwiera się')).toBeInTheDocument())
    expect(document.body.innerHTML).not.toContain(KEY)
  })

  it('ignores non-device phrases unless sending to the model is enabled', async () => {
    FakeRecognition.instances = []
    vi.stubGlobal('SpeechRecognition', FakeRecognition)
    const fetch = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === '/api/v1/config/voice') return json({ config: { ...voiceConfig, wake_listening: false }, revision: 0, wyoming_available: false })
      if (path === '/api/v1/devices/gate') return json({ gate, config: {}, revision: 0, events: [], drivers: [] })
      return json({}, 404)
    })
    vi.stubGlobal('fetch', fetch)
    render(<VoicePanel credential={KEY} onUnauthorized={vi.fn()} />)
    await screen.findByText('Brama warsztatu: zamknięta')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Włącz nasłuch' }))
    act(() => FakeRecognition.instances[0].hear('opowiedz dowcip'))
    await screen.findByText(/To nie wygląda na polecenie urządzenia/)
    expect(fetch.mock.calls.some(call => String(call[0]) === '/api/v1/chat')).toBe(false)
  })

  it('explains when the browser lacks speech recognition', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => String(input) === '/api/v1/config/voice' ? json({ config: voiceConfig, revision: 0, wyoming_available: false }) : json({ gate, config: {}, revision: 0, events: [], drivers: [] })))
    render(<VoicePanel credential={KEY} onUnauthorized={vi.fn()} />)
    await screen.findByText('Brama warsztatu: zamknięta')
    expect(screen.getByText(/nie udostępnia rozpoznawania mowy/)).toBeInTheDocument()
  })
})

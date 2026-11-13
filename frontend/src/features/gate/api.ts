import { ApiError, apiRequest } from '../../api'

export type GateDriver = 'disabled' | 'simulator' | 'http' | 'tuya_cloud' | 'home_assistant'
export type GateAction = 'open' | 'close' | 'stop' | 'status'
export type GateState = 'unknown' | 'open' | 'closed' | 'opening' | 'closing' | 'stopped'

export interface GateStatus {
  name: string; driver: GateDriver; live: boolean; state: GateState; state_label: string
  changed: number | null; last_action: string | null; require_confirmation: boolean; pulse: boolean
  raw?: unknown; values?: Record<string, unknown>
}
export interface GateEvent { id: number; action: string; source: string; actor: string; result: string; created: number; detail: Record<string, unknown> }
export interface HttpDriverConfig { open_url: string; close_url: string; stop_url: string; status_url: string; method: 'GET' | 'POST'; body: string; username: string; password: string; password_set?: boolean; status_open_match: string }
export interface TuyaDriverConfig { endpoint: string; access_id: string; access_secret: string; access_secret_set?: boolean; device_id: string; open_code: string; open_value: boolean | number | string; close_code: string; close_value: boolean | number | string; stop_code: string; stop_value: boolean | number | string; status_code: string }
export interface HomeAssistantDriverConfig { url: string; token: string; token_set?: boolean; entity_id: string; open_service: string; close_service: string; stop_service: string }
export interface GateConfig {
  driver: GateDriver; name: string; require_confirmation: boolean; cooldown_seconds: number; travel_seconds: number; pulse: boolean
  http: HttpDriverConfig | null; tuya: TuyaDriverConfig | null; home_assistant: HomeAssistantDriverConfig | null
}
export interface GateOverview { gate: GateStatus; config: GateConfig; revision: number; events: GateEvent[]; drivers: string[] }
export type CommandResult =
  | { status: 'executed'; action: GateAction; external_request_sent: boolean; gate: GateStatus }
  | { status: 'confirmation_required'; action: GateAction; confirm_token: string; expires_in: number; prompt: string; gate: GateStatus }

export const DRIVERS: GateDriver[] = ['simulator', 'http', 'tuya_cloud', 'home_assistant', 'disabled']
export const driverLabels: Record<GateDriver, string> = {
  disabled: 'Wyłączone', simulator: 'Symulator (bez sprzętu)', http: 'Lokalne HTTP (Shelly / Tasmota / ESP)',
  tuya_cloud: 'Tuya / Smart Life (chmura)', home_assistant: 'Home Assistant',
}
export const emptyHttp: HttpDriverConfig = { open_url: '', close_url: '', stop_url: '', status_url: '', method: 'GET', body: '', username: '', password: '', status_open_match: '' }
export const emptyTuya: TuyaDriverConfig = { endpoint: 'https://openapi.tuyaeu.com', access_id: '', access_secret: '', device_id: '', open_code: 'switch_1', open_value: true, close_code: 'switch_1', close_value: false, stop_code: '', stop_value: true, status_code: '' }
export const emptyHomeAssistant: HomeAssistantDriverConfig = { url: '', token: '', entity_id: '', open_service: 'cover.open_cover', close_service: 'cover.close_cover', stop_service: 'cover.stop_cover' }

const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const invalid = (): never => { throw new ApiError(null, 'response') }

function status(value: unknown): GateStatus {
  if (!object(value) || typeof value.name !== 'string' || typeof value.driver !== 'string' || typeof value.state !== 'string'
    || typeof value.state_label !== 'string' || typeof value.live !== 'boolean') return invalid()
  return value as unknown as GateStatus
}

export async function readGate(credential: string, signal: AbortSignal): Promise<GateOverview> {
  const value = await apiRequest('/api/v1/devices/gate', signal, credential)
  if (!object(value) || !object(value.config) || !Array.isArray(value.events) || !Number.isSafeInteger(value.revision)) return invalid()
  return { gate: status(value.gate), config: value.config as unknown as GateConfig, revision: value.revision as number, events: value.events as GateEvent[], drivers: value.drivers as string[] }
}

export async function sendCommand(credential: string, signal: AbortSignal, action: GateAction, source: 'panel' | 'voice', confirmToken?: string): Promise<CommandResult> {
  const value = await apiRequest('/api/v1/devices/gate/command', signal, credential, { timeoutMs: 30000, body: { action, source, confirm_token: confirmToken ?? null } })
  if (!object(value)) return invalid()
  if (action === 'status') return { status: 'executed', action, external_request_sent: Boolean(value.live), gate: status(value) }
  if (value.status === 'confirmation_required' && typeof value.confirm_token === 'string' && typeof value.prompt === 'string') {
    return { status: 'confirmation_required', action, confirm_token: value.confirm_token, expires_in: Number(value.expires_in) || 12, prompt: value.prompt, gate: status(value.gate) }
  }
  if (value.status === 'executed') return { status: 'executed', action, external_request_sent: Boolean(value.external_request_sent), gate: status(value.gate) }
  return invalid()
}

export async function testGate(credential: string, signal: AbortSignal): Promise<GateStatus> {
  const value = await apiRequest('/api/v1/devices/gate/test', signal, credential, { timeoutMs: 30000, body: {} })
  if (!object(value) || value.status !== 'reachable') return invalid()
  return status(value.gate)
}

export async function saveGateConfig(credential: string, signal: AbortSignal, revision: number, config: GateConfig): Promise<{ config: GateConfig; revision: number }> {
  const value = await apiRequest('/api/v1/devices/gate/config', signal, credential, { method: 'PUT', body: { revision, config } })
  if (!object(value) || !object(value.config) || !Number.isSafeInteger(value.revision)) return invalid()
  return { config: value.config as unknown as GateConfig, revision: value.revision as number }
}

export interface VoiceConfig { engine: 'browser' | 'wyoming'; wake_word: string; wake_listening: boolean; speak_replies: boolean; language: 'pl-PL' | 'en-US'; send_to_model: boolean }
export const defaultVoiceConfig: VoiceConfig = { engine: 'browser', wake_word: 'jarvis', wake_listening: true, speak_replies: true, language: 'pl-PL', send_to_model: false }

export async function readVoiceConfig(credential: string, signal: AbortSignal): Promise<{ config: VoiceConfig; revision: number; wyomingAvailable: boolean }> {
  const value = await apiRequest('/api/v1/config/voice', signal, credential)
  if (!object(value) || !object(value.config) || !Number.isSafeInteger(value.revision)) return invalid()
  return { config: { ...defaultVoiceConfig, ...(value.config as Partial<VoiceConfig>) }, revision: value.revision as number, wyomingAvailable: Boolean(value.wyoming_available) }
}

export async function saveVoiceConfig(credential: string, signal: AbortSignal, revision: number, config: VoiceConfig): Promise<{ config: VoiceConfig; revision: number }> {
  const value = await apiRequest('/api/v1/config/voice', signal, credential, { method: 'PUT', body: { revision, config } })
  if (!object(value) || !object(value.config) || !Number.isSafeInteger(value.revision)) return invalid()
  return { config: { ...defaultVoiceConfig, ...(value.config as Partial<VoiceConfig>) }, revision: value.revision as number }
}

export interface VoiceReply { reply: string; session_id: string; model: string; device?: { status: string; action?: string; confirm_token?: string; prompt?: string; gate?: GateStatus } }
export async function sendVoiceMessage(credential: string, signal: AbortSignal, message: string, sessionId: string | null): Promise<VoiceReply> {
  const value = await apiRequest('/api/v1/chat', signal, credential, { timeoutMs: 95000, body: { message, input_mode: 'voice', session_id: sessionId, do_not_remember: true } })
  if (!object(value) || typeof value.reply !== 'string' || typeof value.session_id !== 'string') return invalid()
  return value as unknown as VoiceReply
}

export async function transcribeWav(credential: string, signal: AbortSignal, wav: Blob): Promise<string> {
  const response = await fetch('/api/v1/voice/transcribe', { method: 'POST', headers: { 'X-Jarvis-Key': credential, 'Content-Type': 'audio/wav' }, body: wav, signal, cache: 'no-store', credentials: 'omit' })
  if (!response.ok) throw new ApiError(response.status)
  const value: unknown = await response.json()
  if (!object(value) || typeof value.text !== 'string') return invalid()
  return value.text
}

export async function synthesizeWav(credential: string, signal: AbortSignal, text: string): Promise<Blob> {
  const response = await fetch('/api/v1/voice/synthesize', { method: 'POST', headers: { 'X-Jarvis-Key': credential, 'Content-Type': 'application/json' }, body: JSON.stringify({ text: text.slice(0, 1000) }), signal, cache: 'no-store', credentials: 'omit' })
  if (!response.ok) throw new ApiError(response.status)
  return response.blob()
}

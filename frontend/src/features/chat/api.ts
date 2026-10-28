import { ApiError, apiRequest } from '../../api'
import type { ChatMessage, ChatReply, ChatSession, ModelCatalog, ModelOption } from './types'

export const SESSION_PAGE = 20
export const MESSAGE_PAGE = 100
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
function object(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === 'object' && !Array.isArray(value) }
function bad(): never { throw new ApiError(null, 'response') }
function timestamp(value: unknown): value is number { return typeof value === 'number' && Number.isFinite(value) && value >= 0 }
function identifier(value: unknown): value is string { return typeof value === 'string' && UUID.test(value) }
function session(value: unknown, created = false): ChatSession {
  if (!object(value) || !identifier(value.id) || typeof value.title !== 'string' || value.title.length > 120
    || !['demo', 'ollama', 'openai'].includes(String(value.provider)) || typeof value.model_name !== 'string' || value.model_name.length > 150
    || !timestamp(value.created) || !timestamp(value.updated) || !['text', 'voice'].includes(String(value.input_mode))
    || !(value.active_turn === null || identifier(value.active_turn) || (created && value.active_turn === undefined))) return bad()
  if (value.message_count !== undefined && (!Number.isSafeInteger(value.message_count) || Number(value.message_count) < 0)) return bad()
  return { ...value, active_turn: value.active_turn ?? null } as unknown as ChatSession
}
function model(value: unknown): ModelOption {
  if (!object(value) || !['demo', 'ollama', 'openai'].includes(String(value.provider)) || typeof value.name !== 'string'
    || !value.name || value.name.length > 150 || typeof value.cloud !== 'boolean') return bad()
  return value as unknown as ModelOption
}
export function modelKey(value: Pick<ModelOption, 'provider' | 'name'>): string { return JSON.stringify({ provider: value.provider, name: value.name }) }
export async function getModels(credential: string, signal: AbortSignal): Promise<ModelCatalog> {
  const value = await apiRequest('/api/v1/models', signal, credential)
  if (!object(value) || !['demo', 'ollama', 'openai'].includes(String(value.default_provider)) || !Array.isArray(value.models)
    || value.models.length > 200 || typeof value.default_ollama_model !== 'string' || value.probes_network !== false) return bad()
  return { default_provider: value.default_provider as ModelCatalog['default_provider'], default_ollama_model: value.default_ollama_model, models: value.models.map(model) }
}
export async function getSessions(credential: string, offset: number, signal: AbortSignal): Promise<ChatSession[]> {
  const value = await apiRequest(`/api/v1/chat/sessions?limit=${SESSION_PAGE}&offset=${offset}`, signal, credential)
  if (!Array.isArray(value) || value.length > SESSION_PAGE) return bad()
  return value.map(item => session(item))
}
export async function getSession(credential: string, id: string, signal: AbortSignal): Promise<ChatSession> {
  if (!identifier(id)) return bad()
  return session(await apiRequest('/api/v1/chat/sessions/' + encodeURIComponent(id), signal, credential))
}
export async function getMessages(credential: string, id: string, offset: number, signal: AbortSignal): Promise<ChatMessage[]> {
  if (!identifier(id)) return bad()
  const value = await apiRequest(`/api/v1/chat/sessions/${encodeURIComponent(id)}/messages?limit=${MESSAGE_PAGE}&offset=${offset}`, signal, credential)
  if (!Array.isArray(value) || value.length > MESSAGE_PAGE) return bad()
  return value.map(item => {
    if (!object(item) || !Number.isSafeInteger(item.id) || Number(item.id) < 1 || !['user', 'assistant'].includes(String(item.role))
      || typeof item.content !== 'string' || item.content.length > 100000 || !timestamp(item.created)
      || !['pending', 'completed', 'failed'].includes(String(item.state)) || !identifier(item.turn_id)) return bad()
    return item as unknown as ChatMessage
  })
}
export async function createSession(credential: string, title: string, choice: ModelOption, signal: AbortSignal): Promise<ChatSession> {
  return session(await apiRequest('/api/v1/chat/sessions', signal, credential, {
    body: { title, model: choice.provider, model_name: choice.name },
  }), true)
}
export async function sendMessage(credential: string, id: string, message: string, choice: ModelOption, doNotRemember: boolean, signal: AbortSignal): Promise<ChatReply> {
  if (!identifier(id)) return bad()
  const value = await apiRequest('/api/v1/chat', signal, credential, { timeoutMs: 95000, body: {
    message, session_id: id, model: choice.provider, model_name: choice.name, input_mode: 'text', do_not_remember: doNotRemember,
  } })
  if (!object(value) || typeof value.reply !== 'string' || value.session_id !== id || !identifier(value.turn_id)) return bad()
  return value as unknown as ChatReply
}

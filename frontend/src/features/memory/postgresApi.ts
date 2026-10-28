import { ApiError, apiRequest } from '../../api'
export interface RecordRow { id: string; revision: number; workshop_id: string | null; content?: string; category?: string; source?: string; source_id?: string; name?: string; instructions?: string }
export interface Session { id: string; revision: number; provider: 'ollama' | 'openai'; profile_id: string | null; profile_revision: number | null }
export interface Version { revision: number; content?: string; instructions?: string; name?: string }
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
export const uuid = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(v)
const rev = (v: unknown): v is number => Number.isSafeInteger(v) && Number(v) >= 0
const invalid = (): never => { throw new ApiError(null, 'response') }
export type Kind = 'notes' | 'profiles'
export const base = '/api/v1/storage/memory'
export const route = (kind: Kind, id?: string) => base + (kind === 'profiles' ? '/profiles' : '') + (id ? '/' + (uuid(id) ? id : invalid()) : '')
export async function pgStatus(key: string, signal: AbortSignal) {
  const v = await apiRequest(base + '/status', signal, key)
  if (!object(v) || typeof v.enabled !== 'boolean' || !(v.memory_schema_version === null || rev(v.memory_schema_version))) return invalid()
  return { enabled: v.enabled, version: v.memory_schema_version as number | null }
}
export function row(v: unknown, kind: Kind): RecordRow {
  if (!object(v) || !uuid(v.id) || !rev(v.revision) || !(v.workshop_id === null || uuid(v.workshop_id))) return invalid()
  if (kind === 'profiles' ? typeof v.name !== 'string' || typeof v.instructions !== 'string' : typeof v.content !== 'string' || typeof v.category !== 'string' || typeof v.source !== 'string' || typeof v.source_id !== 'string') return invalid()
  return v as unknown as RecordRow
}
export async function rows(key: string, signal: AbortSignal, kind: Kind, scope: string, offset: number) {
  const v = await apiRequest(route(kind) + `?limit=20&offset=${offset}` + (scope ? '&workshop_id=' + encodeURIComponent(scope) : ''), signal, key)
  if (!Array.isArray(v) || v.length > 20) return invalid()
  return v.map(item => row(item, kind))
}
export async function versions(key: string, signal: AbortSignal, kind: Kind, id: string) {
  const v = await apiRequest(route(kind, id) + '/history?limit=100', signal, key)
  const list = kind === 'notes' && object(v) ? v.versions : v
  if (!Array.isArray(list) || list.length > 100 || !list.every(item => object(item) && rev(item.revision) && (kind === 'notes' ? typeof item.content === 'string' : typeof item.instructions === 'string' && typeof item.name === 'string'))) return invalid()
  return list as Version[]
}
export async function sessionCreate(key: string, signal: AbortSignal, body: object): Promise<Session> {
  const v = await apiRequest(base + '/conversations', signal, key, { method: 'POST', body })
  if (!object(v) || !uuid(v.id) || !rev(v.revision) || !['ollama', 'openai'].includes(String(v.provider)) || !(v.profile_id === null || uuid(v.profile_id)) || !(v.profile_revision === null || rev(v.profile_revision))) return invalid()
  return v as unknown as Session
}
export async function messages(key: string, signal: AbortSignal, s: Session) {
  const v = await apiRequest(base + '/conversations/' + s.id + '/messages', signal, key)
  if (!object(v) || !rev(v.revision) || !Array.isArray(v.messages) || !v.messages.every(m => object(m) && ['user', 'assistant'].includes(String(m.role)) && typeof m.content === 'string')) return invalid()
  return { revision: v.revision, messages: v.messages as { role: string; content: string }[] }
}

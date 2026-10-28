import { ApiError, apiRequest } from '../../api'

export const CATEGORIES = ['preferences', 'equipment', 'projects', 'decisions', 'working_style', 'manual'] as const
export type Category = typeof CATEGORIES[number]
export interface MemoryNote { id: string; text: string; created: number; source: string; category: Category; revision: number; updated: number }
export interface MemoryPolicy { enabled: boolean; mode: 'manual' | 'auto'; categories: Category[]; retention_days: number | null }
export interface PolicySnapshot { revision: number; policy: MemoryPolicy; automatic_extraction_active: boolean; automatic_extractor: string }
export interface HistoryRow { revision: number; text: string; source: string; category: Category; created: number }
export interface OriginRow { revision: number; session_id: string; turn_id: string; quote: string; extractor: string; created: number; session_available: number }
export interface RetentionPreview { dry_run: boolean; count: number; retention_days: number | null }

const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const invalid = (): never => { throw new ApiError(null, 'response') }
const integer = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
const timestamp = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && Number.isFinite(new Date(value * 1000).getTime())
const category = (value: unknown): value is Category => typeof value === 'string' && CATEGORIES.some(item => item === value)
const text = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 4000
const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i
const ident = (value: unknown): value is string => typeof value === 'string' && uuid.test(value)
const days = (value: unknown): value is number | null => value === null || integer(value) && value >= 1 && value <= 3650
const path = (id: string) => { if (!ident(id)) return invalid(); return '/api/v1/memory/' + encodeURIComponent(id) }

export async function readNotes(credential: string, signal: AbortSignal): Promise<MemoryNote[]> {
  const value = await apiRequest('/api/v1/memory', signal, credential)
  if (!Array.isArray(value) || value.length > 100 || value.some(row => !object(row) || !ident(row.id) || !text(row.text)
    || !timestamp(row.created) || typeof row.source !== 'string' || !category(row.category) || !integer(row.revision) || !timestamp(row.updated))) return invalid()
  return value as MemoryNote[]
}

export async function readPolicy(credential: string, signal: AbortSignal): Promise<PolicySnapshot> {
  const value = await apiRequest('/api/v1/memory/policy', signal, credential)
  if (!object(value) || !integer(value.revision) || !object(value.policy) || typeof value.policy.enabled !== 'boolean'
    || !['manual', 'auto'].includes(String(value.policy.mode)) || !Array.isArray(value.policy.categories) || value.policy.categories.length > 6
    || !value.policy.categories.every(category) || !days(value.policy.retention_days) || typeof value.automatic_extraction_active !== 'boolean'
    || typeof value.automatic_extractor !== 'string') return invalid()
  return value as unknown as PolicySnapshot
}

export async function addNote(credential: string, signal: AbortSignal, body: { text: string; category: Category }): Promise<void> {
  const value = await apiRequest('/api/v1/memory', signal, credential, { method: 'POST', body })
  if (!object(value) || !ident(value.id)) return invalid()
}
export async function correctNote(credential: string, signal: AbortSignal, id: string, body: { text: string; category: Category; revision: number }): Promise<void> {
  const value = await apiRequest(path(id), signal, credential, { method: 'PUT', body })
  if (!object(value) || value.id !== id || value.revision !== body.revision + 1) return invalid()
}
export async function deleteNote(credential: string, signal: AbortSignal, id: string): Promise<void> {
  const value = await apiRequest(path(id), signal, credential, { method: 'DELETE' })
  if (!object(value) || value.deleted !== id) return invalid()
}
export async function savePolicy(credential: string, signal: AbortSignal, revision: number, policy: MemoryPolicy): Promise<void> {
  const value = await apiRequest('/api/v1/memory/policy', signal, credential, { method: 'PUT', body: { revision, policy } })
  if (!object(value) || value.revision !== revision + 1) return invalid()
}
export async function readHistory(credential: string, signal: AbortSignal, id: string): Promise<HistoryRow[]> {
  const value = await apiRequest(path(id) + '/history', signal, credential)
  if (!Array.isArray(value) || value.some(row => !object(row) || !integer(row.revision) || !text(row.text)
    || typeof row.source !== 'string' || !category(row.category) || !timestamp(row.created))) return invalid()
  return value as HistoryRow[]
}
export async function readOrigins(credential: string, signal: AbortSignal, id: string): Promise<OriginRow[]> {
  const value = await apiRequest(path(id) + '/origins', signal, credential)
  if (!Array.isArray(value) || value.some(row => !object(row) || !integer(row.revision) || !ident(row.session_id)
    || !ident(row.turn_id) || typeof row.quote !== 'string' || typeof row.extractor !== 'string' || !timestamp(row.created)
    || typeof row.session_available !== 'number' || ![0, 1].includes(row.session_available))) return invalid()
  return value as OriginRow[]
}
export async function retention(credential: string, signal: AbortSignal, dryRun: boolean): Promise<RetentionPreview> {
  const value = await apiRequest('/api/v1/memory/retention', signal, credential, { method: 'POST', body: { dry_run: dryRun } })
  if (!object(value) || value.dry_run !== dryRun || !integer(value.count) || !days(value.retention_days)) return invalid()
  return value as unknown as RetentionPreview
}

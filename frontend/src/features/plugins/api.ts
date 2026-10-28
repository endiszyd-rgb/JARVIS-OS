import { ApiError, apiRequest } from '../../api'

export type Protocol = 'demo' | 'openapi' | 'mcp'
export interface Plugin { id: string; name: string; protocol: Protocol; description: string; enabled: boolean; transport_ready: boolean }
export interface PluginConfig { endpoint: string; secret_env: string | null; reviewed_read_tools: string[]; openapi: Record<string, unknown> | null }
export interface Tool { id: string; plugin_id: string; name: string; protocol: Protocol; description: string; inputSchema: Record<string, unknown>; read_only_reviewed: true; required_scope: string }
export interface Manifest { id: string; name: string; protocol: Protocol; description: string }
const ID = /^[a-z][a-z0-9_]{1,40}$/
const NAME = /^[A-Za-z][A-Za-z0-9_.-]{0,79}$/
const SECRET = /^JARVIS_PLUGIN_SECRET_[A-Z0-9_]{1,60}$/
export function object(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === 'object' && !Array.isArray(value) }
function invalid(): never { throw new ApiError(null, 'response') }
function pluginPath(id: string): string { if (!ID.test(id)) return invalid(); return '/api/v1/plugins/' + encodeURIComponent(id) }
function protocol(value: unknown): value is Protocol { return ['demo', 'openapi', 'mcp'].includes(String(value)) }

export async function readPlugins(credential: string, signal: AbortSignal): Promise<Plugin[]> {
  const value = await apiRequest('/api/v1/plugins', signal, credential)
  if (!Array.isArray(value) || value.length > 1000 || value.some(row => !object(row) || typeof row.id !== 'string' || !ID.test(row.id)
    || typeof row.name !== 'string' || typeof row.description !== 'string' || !protocol(row.protocol)
    || typeof row.enabled !== 'boolean' || typeof row.transport_ready !== 'boolean') || new Set(value.map(row => row.id)).size !== value.length) return invalid()
  return value as Plugin[]
}
export async function readConfig(credential: string, id: string, signal: AbortSignal): Promise<PluginConfig | null> {
  const value = await apiRequest(pluginPath(id) + '/config', signal, credential)
  if (value === null) return null
  if (!object(value) || typeof value.endpoint !== 'string' || value.endpoint.length > 500
    || !(value.secret_env === null || typeof value.secret_env === 'string' && SECRET.test(value.secret_env))
    || !Array.isArray(value.reviewed_read_tools) || value.reviewed_read_tools.length > 100
    || !value.reviewed_read_tools.every(item => typeof item === 'string' && NAME.test(item))
    || !(value.openapi === null || object(value.openapi))) return invalid()
  return value as unknown as PluginConfig
}
export async function saveConfig(credential: string, id: string, config: PluginConfig, signal: AbortSignal): Promise<void> {
  const value = await apiRequest(pluginPath(id) + '/config', signal, credential, { method: 'PUT', body: config })
  if (!object(value) || value.configured !== true || value.enabled !== false) return invalid()
}
export async function togglePlugin(credential: string, id: string, enabled: boolean, signal: AbortSignal): Promise<void> {
  const value = await apiRequest(pluginPath(id), signal, credential, { method: 'PUT', body: { enabled } })
  if (!object(value) || value.id !== id || value.enabled !== enabled) return invalid()
}
export async function registerPlugin(credential: string, manifest: Manifest, signal: AbortSignal): Promise<void> {
  const value = await apiRequest('/api/v1/plugins', signal, credential, { method: 'POST', body: manifest })
  if (!object(value) || value.id !== manifest.id || value.enabled !== false || value.status !== 'manifest_registered') return invalid()
}
export async function readTools(credential: string, id: string, signal: AbortSignal): Promise<Tool[]> {
  const value = await apiRequest(pluginPath(id) + '/tools', signal, credential, { timeoutMs: 40000 })
  if (!Array.isArray(value) || value.length > 100 || value.some(row => !object(row) || row.plugin_id !== id
    || typeof row.id !== 'string' || typeof row.name !== 'string' || !NAME.test(row.name) || !protocol(row.protocol)
    || typeof row.description !== 'string' || !object(row.inputSchema) || row.read_only_reviewed !== true
    || row.required_scope !== 'plugins:invoke') || new Set(value.map(row => row.name)).size !== value.length) return invalid()
  return value as Tool[]
}
export async function invokeRead(credential: string, id: string, operation: string, args: Record<string, unknown>, signal: AbortSignal): Promise<Record<string, unknown>> {
  if (!NAME.test(operation)) return invalid()
  const value = await apiRequest(pluginPath(id) + '/invoke', signal, credential, { method: 'POST', timeoutMs: 40000, body: { operation, arguments: args } })
  if (!object(value)) return invalid()
  return value
}

export class InputError extends Error {}
export function parseObject(text: string, label: string): Record<string, unknown> {
  if (new TextEncoder().encode(text).byteLength > 65536) throw new InputError(label + ' przekracza limit64KiB.')
  try { const value: unknown = JSON.parse(text); if (object(value)) return value } catch { /* Show no raw parser text. */ }
  throw new InputError(label + ' musi być poprawnym obiektem JSON.')
}
export function formConfig(endpoint: string, secret: string, reviewed: string, spec: string, kind: Protocol): PluginConfig {
  let url: URL
  try { url = new URL(endpoint) } catch { throw new InputError('Wprowadź poprawny adres endpointu HTTP lub HTTPS.') }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || endpoint.length > 500)
    throw new InputError('Adres endpointu nie może zawierać danych logowania, query ani fragmentu.')
  const env = secret.trim() || null
  if (env && !SECRET.test(env)) throw new InputError('Podaj nazwę zmiennej JARVIS_PLUGIN_SECRET_…, bez wartości sekretu.')
  const reads = reviewed.split(/[\n,]/).map(item => item.trim()).filter(Boolean)
  if (reads.length > 100 || new Set(reads).size !== reads.length || reads.some(item => !NAME.test(item)))
    throw new InputError('Podaj do100 unikalnych nazw odczytów, oddzielonych przecinkiem lub nową linią.')
  return { endpoint: endpoint.trim(), secret_env: env, reviewed_read_tools: reads, openapi: kind === 'openapi' ? parseObject(spec, 'Specyfikacja OpenAPI') : null }
}

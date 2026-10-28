import { ApiError, apiRequest } from '../../api'

export interface Settings { name: string; tone: 'casual' | 'formal'; model: 'demo' | 'ollama' | 'openai' }
export interface ConfiguredModel { provider: 'demo' | 'ollama' | 'openai'; name: string; cloud: boolean }
export interface ModelCatalog { models: ConfiguredModel[]; defaultOllamaModel: string }
export interface SettingsProposal { id: string; kind: 'settings'; payload: Settings; status: 'pending' }

const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const invalid = (): never => { throw new ApiError(null, 'response') }
const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i

function settings(value: unknown): Settings {
  if (!object(value) || typeof value.name !== 'string' || !value.name.length || value.name.length > 80
    || !['casual', 'formal'].includes(String(value.tone)) || !['demo', 'ollama', 'openai'].includes(String(value.model))) return invalid()
  return { name: value.name, tone: value.tone as Settings['tone'], model: value.model as Settings['model'] }
}

export function sameSettings(first: Settings, second: Settings): boolean {
  return first.name === second.name && first.tone === second.tone && first.model === second.model
}

export async function readSettings(credential: string, signal: AbortSignal): Promise<Settings> {
  const response = await apiRequest('/api/v1/status', signal, credential)
  if (!object(response)) return invalid()
  return settings(response.settings)
}

export async function readCatalog(credential: string, signal: AbortSignal): Promise<ModelCatalog> {
  const response = await apiRequest('/api/v1/models', signal, credential)
  if (!object(response) || response.source !== 'owner_configuration' || response.probes_network !== false
    || typeof response.default_ollama_model !== 'string' || !Array.isArray(response.models) || response.models.length > 200) return invalid()
  const models = response.models.map(item => {
    if (!object(item) || !['demo', 'ollama', 'openai'].includes(String(item.provider)) || typeof item.name !== 'string'
      || !item.name.length || item.name.length > 150 || typeof item.cloud !== 'boolean') return invalid()
    return { provider: item.provider as ConfiguredModel['provider'], name: item.name, cloud: item.cloud }
  })
  return { models, defaultOllamaModel: response.default_ollama_model }
}

export async function proposeSettings(credential: string, signal: AbortSignal, payload: Settings): Promise<SettingsProposal> {
  const response = await apiRequest('/api/v1/proposals', signal, credential, { method: 'POST', body: { kind: 'settings', payload } })
  if (!object(response) || typeof response.id !== 'string' || !uuid.test(response.id)
    || response.kind !== 'settings' || response.status !== 'pending') return invalid()
  const normalized = settings(response.payload)
  if (!sameSettings(normalized, payload)) return invalid()
  return { id: response.id, kind: 'settings', payload: normalized, status: 'pending' }
}

export async function decideSettings(credential: string, signal: AbortSignal, id: string, approve: boolean): Promise<void> {
  if (!uuid.test(id)) return invalid()
  const response = await apiRequest('/api/v1/proposals/' + encodeURIComponent(id) + '/decide', signal, credential,
    { method: 'POST', body: { approve } })
  if (!object(response) || response.id !== id || response.status !== (approve ? 'applied' : 'rejected')) return invalid()
}

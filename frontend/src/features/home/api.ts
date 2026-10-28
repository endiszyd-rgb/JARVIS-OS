import { ApiError, apiRequest } from '../../api'

export interface HomeState {
  entity_id: string
  state: string
  attributes: { friendly_name?: string; unit_of_measurement?: string }
  last_changed?: string
}
export interface HomeRead { mode: 'live_readonly'; states: HomeState[]; controls_enabled: false }
export interface Integrations {
  home_readonly_enabled: boolean
  twilio_webhook_enabled: boolean
  physical_controls: false
  whatsapp_send: false
  whatsapp_calling: false
}
export function object(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === 'object' && !Array.isArray(value) }
export function invalid(): never { throw new ApiError(null, 'response') }
export const ENTITY = /^[a-z_]+\.[a-z0-9_]+$/
export async function readHome(credential: string, signal: AbortSignal, entity = ''): Promise<HomeRead> {
  if (entity && !ENTITY.test(entity)) return invalid()
  const result = await apiRequest('/api/v1/home/states' + (entity ? '/' + encodeURIComponent(entity) : ''), signal, credential, { timeoutMs: 30000 })
  if (!object(result) || result.mode !== 'live_readonly' || result.controls_enabled !== false || !Array.isArray(result.states)
    || result.states.length > 10000) return invalid()
  const states = result.states.map(row => {
    if (!object(row) || typeof row.entity_id !== 'string' || !ENTITY.test(row.entity_id) || typeof row.state !== 'string'
      || !object(row.attributes) || (row.attributes.friendly_name !== undefined && typeof row.attributes.friendly_name !== 'string')
      || (row.attributes.unit_of_measurement !== undefined && typeof row.attributes.unit_of_measurement !== 'string')
      || (row.last_changed !== undefined && typeof row.last_changed !== 'string')) return invalid()
    return { entity_id: row.entity_id, state: row.state,
      attributes: { friendly_name: row.attributes.friendly_name, unit_of_measurement: row.attributes.unit_of_measurement },
      last_changed: row.last_changed } as HomeState
  })
  return { mode: 'live_readonly', controls_enabled: false, states }
}
export async function readIntegrations(credential: string, signal: AbortSignal): Promise<Integrations> {
  const result = await apiRequest('/api/v1/integrations', signal, credential)
  if (!object(result) || typeof result.home_readonly_enabled !== 'boolean' || typeof result.twilio_webhook_enabled !== 'boolean'
    || result.physical_controls !== false || result.whatsapp_send !== false || result.whatsapp_calling !== false) return invalid()
  return result as unknown as Integrations
}

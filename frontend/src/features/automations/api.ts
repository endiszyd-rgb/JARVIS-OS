import { ApiError, apiRequest } from '../../api'

export interface AutomationPayload { title: string; interval_minutes: number; message: string }
export interface Automation { id: string; payload: AutomationPayload; next_run: number }
export interface AutomationProposal { id: string; kind: 'automation'; payload: AutomationPayload; status: 'pending' }
const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
function invalid(): never { throw new ApiError(null, 'response') }
function payload(value: unknown): AutomationPayload {
  if (!object(value) || typeof value.title !== 'string' || value.title.length < 1 || value.title.length > 100
    || typeof value.message !== 'string' || value.message.length < 1 || value.message.length > 2000
    || !Number.isSafeInteger(value.interval_minutes) || Number(value.interval_minutes) < 1 || Number(value.interval_minutes) > 525600) return invalid()
  return { title: value.title, interval_minutes: Number(value.interval_minutes), message: value.message }
}
export async function readAutomations(credential: string, signal: AbortSignal): Promise<Automation[]> {
  const response = await apiRequest('/api/v1/automations', signal, credential)
  if (!Array.isArray(response)) return invalid()
  return response.map(row => {
    if (!object(row) || typeof row.id !== 'string' || !UUID.test(row.id) || typeof row.next_run !== 'number'
      || !Number.isFinite(row.next_run) || row.next_run < 0 || !Number.isFinite(new Date(row.next_run * 1000).getTime())) return invalid()
    return { id: row.id, payload: payload(row.payload), next_run: row.next_run }
  })
}
export async function proposeAutomation(credential: string, submitted: AutomationPayload, signal: AbortSignal): Promise<AutomationProposal> {
  const response = await apiRequest('/api/v1/proposals', signal, credential, { method: 'POST', body: { kind: 'automation', payload: submitted } })
  if (!object(response) || typeof response.id !== 'string' || !UUID.test(response.id) || response.kind !== 'automation' || response.status !== 'pending') return invalid()
  const normalized = payload(response.payload)
  if (normalized.title !== submitted.title || normalized.message !== submitted.message || normalized.interval_minutes !== submitted.interval_minutes) return invalid()
  return { id: response.id, kind: 'automation', payload: normalized, status: 'pending' }
}
export async function decideAutomation(credential: string, id: string, approve: boolean, signal: AbortSignal): Promise<void> {
  if (!UUID.test(id)) return invalid()
  const response = await apiRequest('/api/v1/proposals/' + encodeURIComponent(id) + '/decide', signal, credential, { method: 'POST', body: { approve } })
  if (!object(response) || response.id !== id || response.status !== (approve ? 'applied' : 'rejected')) return invalid()
}
export async function tickAutomations(credential: string, signal: AbortSignal): Promise<string[]> {
  const response = await apiRequest('/api/v1/automations/tick', signal, credential, { method: 'POST', body: {} })
  if (!object(response) || response.external_request_sent !== false || !Array.isArray(response.fired)
    || !response.fired.every(id => typeof id === 'string' && UUID.test(id))) return invalid()
  return response.fired
}

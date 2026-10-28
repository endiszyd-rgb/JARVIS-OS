import { ApiError, apiRequest } from '../../api'

export interface AuditEvent {
  id: number
  event: string
  detail: string
  created: number
}

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

export async function readActivity(credential: string, signal: AbortSignal): Promise<AuditEvent[]> {
  const result = await apiRequest('/api/v1/audit', signal, credential)
  if (!Array.isArray(result) || result.length > 100 || result.some(row =>
    !object(row) || typeof row.id !== 'number' || !Number.isSafeInteger(row.id) || row.id < 0
    || typeof row.event !== 'string' || !row.event
    || typeof row.detail !== 'string' || typeof row.created !== 'number'
    || !Number.isFinite(row.created) || !Number.isFinite(new Date(row.created * 1000).getTime())
  )) throw new ApiError(null, 'response')
  return result as AuditEvent[]
}

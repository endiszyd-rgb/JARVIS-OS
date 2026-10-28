import { ApiError, apiRequest } from '../../api'

export interface Notification { id: string; message: string; created: number }
const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i
export async function readNotifications(credential: string, signal: AbortSignal): Promise<Notification[]> {
  const response = await apiRequest('/api/v1/notifications', signal, credential)
  if (!Array.isArray(response) || response.length > 100 || response.some(row => !row || typeof row !== 'object' || Array.isArray(row)
    || typeof row.id !== 'string' || !UUID.test(row.id) || typeof row.message !== 'string' || typeof row.created !== 'number'
    || !Number.isFinite(row.created) || row.created < 0 || !Number.isFinite(new Date(row.created * 1000).getTime()))) throw new ApiError(null, 'response')
  return response as Notification[]
}

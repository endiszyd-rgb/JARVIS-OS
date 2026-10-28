import { ApiError, apiRequest } from '../../api'
export type Kind = 'settings' | 'automation' | 'code'
export type Status = 'pending' | 'rejected' | 'applied' | 'review_required' | 'rolled_back'
export interface Proposal { id: string; kind: Kind; payload: Record<string, unknown>; status: Status; previous: string | null }
const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i
const object = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v)
const bad = (): never => { throw new ApiError(null, 'response') }
function path(id: string) { if (!uuid.test(id)) return bad(); return '/api/v1/proposals/' + id }
export async function readProposals(key: string, signal: AbortSignal): Promise<Proposal[]> {
  const value = await apiRequest('/api/v1/proposals', signal, key)
  if (!Array.isArray(value) || value.length > 100) return bad()
  return value.map(row => {
    if (!object(row) || typeof row.id !== 'string' || !uuid.test(row.id) || !['settings', 'automation', 'code'].includes(String(row.kind))
      || !object(row.payload) || !['pending', 'rejected', 'applied', 'review_required', 'rolled_back'].includes(String(row.status))
      || !(row.previous === null || typeof row.previous === 'string')) return bad()
    return row as unknown as Proposal
  })
}
export async function decideProposal(key: string, row: Proposal, approve: boolean, signal: AbortSignal): Promise<Status> {
  if (row.status !== 'pending') throw new ApiError(409)
  const expected = !approve ? 'rejected' : row.kind === 'code' ? 'review_required' : 'applied'
  const value = await apiRequest(path(row.id) + '/decide', signal, key, { method: 'POST', body: { approve } })
  if (!object(value) || value.id !== row.id || value.status !== expected) return bad()
  return expected
}
export async function rollbackProposal(key: string, row: Proposal, signal: AbortSignal): Promise<void> {
  if (row.status !== 'applied' || row.kind === 'code') throw new ApiError(409)
  const value = await apiRequest(path(row.id) + '/rollback', signal, key, { method: 'POST', body: {} })
  if (!object(value) || value.status !== 'rolled_back') return bad()
}

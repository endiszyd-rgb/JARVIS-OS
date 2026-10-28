import { apiRequest } from '../../api'
import { invalid, object } from '../home/api'

export const DOMAINS = ['calendar', 'orders', 'vehicles', 'parts', 'customers', 'finances', 'reports', 'notifications'] as const
export type Domain = typeof DOMAINS[number]
export const PAGE = 50
type Row = Record<string, unknown>
export interface Page { items: Row[]; has_more: boolean }
export interface SnapshotInfo { mode: 'snapshot_readonly'; created_at: string; sha256: string; audited_commit: string; domains: Domain[]; live: false }
export interface SnapshotDomain { mode: 'snapshot_readonly'; domain: Domain; snapshot_created_at: string; sha256: string; audited_commit: string; limit: number; offset: number; data: Row }
export interface LiveOrders { mode: 'live_readonly'; audited_commit: string; data: Row | Row[]; detail: boolean }
export type WorkshopRead = { kind: 'metadata'; value: SnapshotInfo } | { kind: 'snapshot'; value: SnapshotDomain } | { kind: 'live'; value: LiveOrders }
const hash = (value: unknown, length: number) => typeof value === 'string' && value.length === length && /^[a-f0-9]+$/.test(value)
const date = (value: unknown) => typeof value === 'string' && Number.isFinite(new Date(value).getTime())

export function page(value: unknown): value is Page {
  return object(value) && Array.isArray(value.items) && value.items.length <= PAGE && value.items.every(object) && typeof value.has_more === 'boolean'
}
export async function readSnapshotInfo(credential: string, signal: AbortSignal): Promise<WorkshopRead> {
  const value = await apiRequest('/api/v1/autologika/snapshot', signal, credential)
  if (!object(value) || value.mode !== 'snapshot_readonly' || value.live !== false || !date(value.created_at)
    || !hash(value.sha256, 64) || !hash(value.audited_commit, 40) || !Array.isArray(value.domains)
    || value.domains.length > DOMAINS.length || value.domains.some(item => !DOMAINS.includes(item as Domain))) return invalid()
  return { kind: 'metadata', value: value as unknown as SnapshotInfo }
}
export async function readSnapshotDomain(credential: string, signal: AbortSignal, domain: Domain, offset: number, month: string): Promise<WorkshopRead> {
  if (!DOMAINS.includes(domain) || !Number.isSafeInteger(offset) || offset < 0 || offset > 100000 || !/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) return invalid()
  const value = await apiRequest(`/api/v1/autologika/snapshot/${domain}?limit=${PAGE}&offset=${offset}&month=${encodeURIComponent(month)}`, signal, credential)
  if (!object(value) || value.mode !== 'snapshot_readonly' || value.domain !== domain || !date(value.snapshot_created_at)
    || !hash(value.sha256, 64) || !hash(value.audited_commit, 40) || value.limit !== PAGE || value.offset !== offset || !object(value.data)) return invalid()
  if (domain === 'parts') {
    if (!['job_part_orders', 'inventory_parts', 'repair_parts'].every(key => page(value.data && (value.data as Row)[key]))) return invalid()
  } else if (domain === 'finances') {
    if (value.data.month !== month || value.data.currency !== 'PLN' || value.data.accounting_profit !== false
      || ['orders_count', 'orders_value', 'contribution', 'receivables', 'paid_in_month'].some(key => typeof (value.data as Row)[key] !== 'number' || !Number.isFinite((value.data as Row)[key]))) return invalid()
  } else if (domain === 'reports') {
    if (!Array.isArray(value.data.status_counts) || !value.data.status_counts.every(row => object(row) && typeof row.status === 'string' && Number.isSafeInteger(row.count) && Number(row.count) >= 0)) return invalid()
  } else if (!page(value.data)) return invalid()
  return { kind: 'snapshot', value: value as unknown as SnapshotDomain }
}
export async function readOrders(credential: string, signal: AbortSignal, id: string): Promise<WorkshopRead> {
  if (id && (!/^[1-9][0-9]*$/.test(id) || !Number.isSafeInteger(Number(id)))) return invalid()
  const value = await apiRequest('/api/v1/autologika/readonly/orders' + (id ? '/' + id : ''), signal, credential, { timeoutMs: 15000 })
  if (!object(value) || value.mode !== 'live_readonly' || !hash(value.audited_commit, 40)
    || (id ? !object(value.data) : !Array.isArray(value.data) || value.data.length > 100 || !value.data.every(object))) return invalid()
  return { kind: 'live', value: { mode: 'live_readonly', audited_commit: value.audited_commit as string, data: value.data as Row | Row[], detail: Boolean(id) } }
}

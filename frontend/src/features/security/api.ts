import { ApiError, apiRequest } from '../../api'
import type { Role } from '../../types'

export const roles: Role[] = ['owner', 'observer', 'home_reader', 'workshop_reader', 'automation_runner']
export const scopes = ['status:read', 'scheduler:tick', 'home:read', 'plugins:read', 'plugins:invoke', 'messages:read', 'messages:draft'] as const
export type Scope = typeof scopes[number]
export interface User { id: string; username: string; role: Role; enabled: boolean; revision: number; created: number; updated: number }
export interface Session { id: string; user_id: string; username: string; role: Role; expires_at: number; revoked: boolean; created: number }
export interface ServiceToken { id: string; name: string; scopes: Scope[]; expires: number; revoked: boolean }
export interface Snapshot { users: User[]; sessions: Session[]; tokens: ServiceToken[] }
export interface IssuedToken { id: string; token: string }
const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i
function object(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === 'object' && !Array.isArray(value) }
function bad(): never { throw new ApiError(null, 'response') }
function time(value: unknown): value is number { return typeof value === 'number' && Number.isFinite(value) && value >= 0 }
function id(value: unknown): value is string { return typeof value === 'string' && uuid.test(value) }
function user(value: unknown): User {
  if (!object(value) || !id(value.id) || typeof value.username !== 'string' || !roles.includes(value.role as Role)
    || typeof value.enabled !== 'boolean' || !Number.isSafeInteger(value.revision) || Number(value.revision) < 0
    || !time(value.created) || !time(value.updated)) return bad()
  return value as unknown as User
}
function session(value: unknown): Session {
  if (!object(value) || !id(value.id) || !id(value.user_id) || typeof value.username !== 'string' || !roles.includes(value.role as Role)
    || typeof value.revoked !== 'boolean' || !time(value.expires_at) || !time(value.created)) return bad()
  return value as unknown as Session
}
function token(value: unknown): ServiceToken {
  if (!object(value) || !id(value.id) || typeof value.name !== 'string' || !Array.isArray(value.scopes)
    || !value.scopes.every(item => scopes.includes(item)) || !time(value.expires) || ![0, 1, false, true].includes(value.revoked as number | boolean)) return bad()
  return { ...value, revoked: Boolean(value.revoked) } as unknown as ServiceToken
}
function list<T>(value: unknown, limit: number, parse: (item: unknown) => T): T[] {
  if (!Array.isArray(value) || value.length > limit) return bad()
  return value.map(parse)
}
export async function readSecurity(credential: string, signal: AbortSignal): Promise<Snapshot> {
  const [users, sessions, tokens] = await Promise.all([
    apiRequest('/api/v1/security/users', signal, credential), apiRequest('/api/v1/security/sessions', signal, credential), apiRequest('/api/v1/security/tokens', signal, credential),
  ])
  return { users: list(users, 256, user), sessions: list(sessions, 10000, session), tokens: list(tokens, 10000, token) }
}
export async function createUser(credential: string, signal: AbortSignal, username: string, password: string, role: Role): Promise<User> {
  return user(await apiRequest('/api/v1/security/users', signal, credential, { method: 'POST', body: { username, password, role } }))
}
export async function changeUser(credential: string, signal: AbortSignal, current: User, role: Role, enabled: boolean): Promise<User> {
  if (!id(current.id)) return bad()
  const value = user(await apiRequest('/api/v1/security/users/' + current.id, signal, credential, { method: 'PATCH', body: { revision: current.revision, role, enabled } }))
  if (value.id !== current.id || value.revision <= current.revision || value.role !== role || value.enabled !== enabled) return bad()
  return value
}
export async function revoke(credential: string, signal: AbortSignal, kind: 'sessions' | 'tokens', ident: string): Promise<void> {
  if (!id(ident)) return bad()
  const value = await apiRequest('/api/v1/security/' + kind + '/' + ident, signal, credential, { method: 'DELETE' })
  if (!object(value) || value.revoked !== ident) return bad()
}
export async function issueToken(credential: string, signal: AbortSignal, name: string, selected: Scope[], hours: number): Promise<IssuedToken> {
  const value = await apiRequest('/api/v1/security/tokens', signal, credential, { method: 'POST', body: { name, scopes: selected, hours } })
  if (!object(value) || !id(value.id) || typeof value.token !== 'string' || !/^jv_[A-Za-z0-9_-]{32,256}$/.test(value.token)) return bad()
  return { id: value.id, token: value.token }
}

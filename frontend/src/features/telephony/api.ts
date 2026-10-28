import { ApiError, apiRequest } from '../../api'

export interface Window { start: string; end: string }
export interface Day { weekday: number; windows: Window[] }
export interface ExceptionDay { start: string; end: string; label: string }
export interface Policy {
  enabled: boolean; owner_number: string; workshop_number: string; timezone: 'Europe/Warsaw';
  weekly: Day[]; exceptions: ExceptionDay[]; dnd: boolean; dnd_until: string | null;
  outside_hours: 'log_and_notify'; no_answer: 'callback_request'
}
export interface SavedPolicy { revision: number; policy: Policy }
export type Situation = 'routine' | 'contact_requested' | 'insistent' | 'crisis'
export interface Decision {
  revision: number; preview_only: true; executed: false; local_time: string; situation: Situation;
  eligible_for_owner_contact: boolean; action: 'request_owner_acceptance' | 'log_and_notify' | 'continue_reception';
  reasons: string[]; owner_must_accept: true; emergency_services_notice: boolean; fallback: 'callback_request';
  notifications_sent: false; carrier_connected: false
}
export interface Draft {
  enabled: boolean; owner: string; workshop: string; hours: string[]; exceptions: string; dnd: boolean; until: string
}
export const days = ['Poniedziałek', 'Wtorek', 'Środa', 'Czwartek', 'Piątek', 'Sobota', 'Niedziela']
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const invalid = (): never => { throw new ApiError(null, 'response') }
const revision = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) >= 0
const phone = /^(?:|\+[1-9][0-9]{6,14})$/
const startTime = /^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/
const endTime = /^(?:(?:[01][0-9]|2[0-3]):[0-5][0-9]|24:00)$/
const date = (value: unknown): value is string => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value + 'T00:00:00Z')) && new Date(value + 'T00:00:00Z').toISOString().slice(0, 10) === value
export const aware = (value: string) => /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value))
function policy(value: unknown): Policy {
  if (!object(value) || typeof value.enabled !== 'boolean' || typeof value.dnd !== 'boolean'
    || typeof value.owner_number !== 'string' || !phone.test(value.owner_number) || typeof value.workshop_number !== 'string' || !phone.test(value.workshop_number)
    || value.timezone !== 'Europe/Warsaw' || value.outside_hours !== 'log_and_notify' || value.no_answer !== 'callback_request'
    || !(value.dnd_until === null || typeof value.dnd_until === 'string' && aware(value.dnd_until))
    || !Array.isArray(value.weekly) || value.weekly.length > 7 || !Array.isArray(value.exceptions) || value.exceptions.length > 100) return invalid()
  for (const day of value.weekly) {
    if (!object(day) || !Number.isInteger(day.weekday) || Number(day.weekday) < 0 || Number(day.weekday) > 6 || !Array.isArray(day.windows) || day.windows.length > 8) return invalid()
    for (const window of day.windows) if (!object(window) || typeof window.start !== 'string' || !startTime.test(window.start)
      || typeof window.end !== 'string' || !endTime.test(window.end) || window.start >= window.end) return invalid()
  }
  if (new Set(value.weekly.map(day => day.weekday)).size !== value.weekly.length) return invalid()
  for (const exception of value.exceptions) if (!object(exception) || !date(exception.start) || !date(exception.end)
    || exception.end < exception.start || typeof exception.label !== 'string' || exception.label.length > 100) return invalid()
  return value as unknown as Policy
}
function saved(value: unknown): SavedPolicy {
  if (!object(value) || !revision(value.revision)) return invalid()
  return { revision: value.revision, policy: policy(value.policy) }
}
export async function readPolicy(credential: string, signal: AbortSignal): Promise<SavedPolicy> {
  const value = await apiRequest('/api/v1/telephony/settings', signal, credential)
  if (!object(value) || value.mode !== 'policy_preview' || value.carrier_connected !== false || value.customer_answering !== 'jarvis_first') return invalid()
  return saved(value)
}
export async function savePolicy(credential: string, current: SavedPolicy, next: Policy, signal: AbortSignal): Promise<SavedPolicy> {
  const value = await apiRequest('/api/v1/telephony/settings', signal, credential, { method: 'PUT', body: { revision: current.revision, policy: next } })
  if (!object(value) || value.executed !== false || value.revision !== current.revision + 1) return invalid()
  return saved(value)
}
export async function previewPolicy(credential: string, at: string, situation: Situation, signal: AbortSignal): Promise<Decision> {
  const value = await apiRequest('/api/v1/telephony/preview', signal, credential, { method: 'POST', body: { at: at.trim() || null, situation } })
  if (!object(value) || !revision(value.revision) || value.preview_only !== true || value.executed !== false || value.carrier_connected !== false
    || value.notifications_sent !== false || value.owner_must_accept !== true || value.fallback !== 'callback_request'
    || typeof value.local_time !== 'string' || !aware(value.local_time) || value.situation !== situation
    || typeof value.eligible_for_owner_contact !== 'boolean' || typeof value.emergency_services_notice !== 'boolean'
    || !['request_owner_acceptance', 'log_and_notify', 'continue_reception'].includes(String(value.action))
    || !Array.isArray(value.reasons) || value.reasons.length > 20 || !value.reasons.every(item => typeof item === 'string')) return invalid()
  return value as unknown as Decision
}
export function toDraft(policy: Policy): Draft {
  return { enabled: policy.enabled, owner: policy.owner_number, workshop: policy.workshop_number, dnd: policy.dnd,
    until: policy.dnd_until ?? '', hours: days.map((_, weekday) => (policy.weekly.find(day => day.weekday === weekday)?.windows ?? []).map(window => window.start + '-' + window.end).join(', ')),
    exceptions: policy.exceptions.map(exception => exception.start + (exception.end === exception.start ? '' : '..' + exception.end) + (exception.label ? ' | ' + exception.label : '')).join('\n') }
}
export class InputError extends Error {}
export function fromDraft(draft: Draft): Policy {
  const owner = draft.owner.trim(), workshop = draft.workshop.trim(), until = draft.until.trim() || null
  if (!phone.test(owner) || !phone.test(workshop)) throw new InputError('Numery podaj w formacie międzynarodowym, np. +48…, albo pozostaw puste przy wyłączonej polityce.')
  if (owner && owner === workshop) throw new InputError('Numer właściciela musi różnić się od numeru warsztatu.')
  if (until && !aware(until)) throw new InputError('Termin Nie przeszkadzać wymaga poprawnej daty i przesunięcia strefy, np. +01:00.')
  const weekly = draft.hours.map((text, weekday) => {
    const windows = text.trim() ? text.split(',').map(part => {
      const pair = part.trim().split('-').map(item => item.trim())
      if (pair.length !== 2 || !startTime.test(pair[0]) || !endTime.test(pair[1]) || pair[0] >= pair[1]) throw new InputError('Godziny podaj jako 08:00-18:00. Przedział przez północ rozdziel na dwa dni.')
      return { start: pair[0], end: pair[1] }
    }).sort((first, second) => first.start.localeCompare(second.start)) : []
    if (windows.length > 8 || windows.some((window, index) => index > 0 && windows[index - 1].end > window.start)) throw new InputError('Jednego dnia podaj do 8 niepokrywających się przedziałów.')
    return { weekday, windows }
  })
  const exceptions = draft.exceptions.split('\n').map(line => line.trim()).filter(Boolean).map(line => {
    const [range, ...labelParts] = line.split('|'), pair = range.trim().split('..').map(item => item.trim())
    const start = pair[0], end = pair[1] ?? start, label = labelParts.join('|').trim()
    if (pair.length > 2 || !date(start) || !date(end) || end < start || label.length > 100) throw new InputError('Wyjątek podaj jako RRRR-MM-DD lub zakres RRRR-MM-DD..RRRR-MM-DD, opcjonalnie | opis.')
    return { start, end, label }
  })
  if (exceptions.length > 100) throw new InputError('Możesz zapisać do 100 wyjątków.')
  if (draft.enabled && (!owner || !workshop || !weekly.some(day => day.windows.length))) throw new InputError('Przed włączeniem ustaw oba numery i co najmniej jeden przedział dostępności.')
  return { enabled: draft.enabled, owner_number: owner, workshop_number: workshop, timezone: 'Europe/Warsaw', weekly, exceptions,
    dnd: draft.dnd, dnd_until: until, outside_hours: 'log_and_notify', no_answer: 'callback_request' }
}

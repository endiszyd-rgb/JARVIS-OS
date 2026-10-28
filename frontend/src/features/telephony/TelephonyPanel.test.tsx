import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TelephonyPanel } from './TelephonyPanel'
import type { Policy } from './api'

const CREDENTIAL = 'synthetic-telephony-session-secret'
const POLICY: Policy = { enabled: false, owner_number: '+48500111222', workshop_number: '+48500333444', timezone: 'Europe/Warsaw', weekly: [{ weekday: 2, windows: [{ start: '08:00', end: '18:00' }] }], exceptions: [], dnd: false, dnd_until: null, outside_hours: 'log_and_notify', no_answer: 'callback_request' }
const DECISION = { revision: 3, preview_only: true, executed: false, local_time: '2026-10-28T12:00:00+01:00', situation: 'crisis', eligible_for_owner_contact: false, action: 'log_and_notify', reasons: ['disabled'], owner_must_accept: true, emergency_services_notice: true, fallback: 'callback_request', notifications_sent: false, carrier_connected: false }
type Call = { path: string; options: RequestInit }
type Handler = (path: string, options: RequestInit) => Response | Promise<Response> | undefined
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
function server(handler?: Handler) {
  const calls: Call[] = [], state = { revision: 3, policy: structuredClone(POLICY) }
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
    const path = String(input); calls.push({ path, options })
    const custom = handler?.(path, options); if (custom !== undefined) return await custom
    if (path === '/api/v1/telephony/settings' && options.method === 'PUT') {
      const submitted = JSON.parse(String(options.body)); state.revision = submitted.revision + 1; state.policy = submitted.policy
      return response({ ...state, executed: false })
    }
    if (path === '/api/v1/telephony/settings') return response({ ...state, mode: 'policy_preview', carrier_connected: false, customer_answering: 'jarvis_first' })
    if (path === '/api/v1/telephony/preview') return response({ ...DECISION, situation: JSON.parse(String(options.body)).situation, revision: state.revision })
    throw new Error('Unexpected telephony request: ' + path)
  }))
  return { calls, state }
}
function panel() { const onUnauthorized = vi.fn(); return { ...render(<TelephonyPanel credential={CREDENTIAL} onUnauthorized={onUnauthorized} />), onUnauthorized } }
async function loaded() { await waitFor(() => expect(screen.getByLabelText('Numer właściciela')).toHaveValue(POLICY.owner_number)) }
afterEach(() => vi.unstubAllGlobals())

describe('Local telephony policy and decision preview', () => {
  it('reads only local policy on mount without invoking preview or a carrier', async () => {
    const { calls } = server(); panel(); await loaded()
    expect(calls.map(call => call.path)).toEqual(['/api/v1/telephony/settings'])
    expect(screen.getByText('Operator niepodłączony')).toBeInTheDocument()
    expect(screen.getByLabelText('Środa')).toHaveValue('08:00-18:00')
    expect(screen.getByLabelText('Poniedziałek')).toHaveValue('')
    expect(document.body.innerHTML).not.toContain(CREDENTIAL)
    expect(new Headers(calls[0].options.headers).get('X-Jarvis-Key')).toBe(CREDENTIAL)
  })

  it('saves a full policy with its revision and preserves all weekday windows and exceptions', async () => {
    const { calls, state } = server(); panel(); await loaded(); const user = userEvent.setup()
    await user.click(screen.getByLabelText('Zezwalaj na przekazywanie'))
    await user.type(screen.getByLabelText('Poniedziałek'), '09:00-12:00, 13:00-24:00')
    await user.type(screen.getByLabelText('Urlopy i wyjątki'), '2026-12-24..2026-12-26 | Urlop')
    await user.click(screen.getByLabelText('Nie przeszkadzać', { exact: true }))
    await user.type(screen.getByLabelText('Nie przeszkadzać do', { exact: true }), '2026-10-28T18:00:00+01:00')
    await user.click(screen.getByRole('button', { name: 'Zapisz zasady' }))
    await screen.findByText('Zapisano zasady. Nie wykonano połączenia.')
    const saved = calls.find(call => call.options.method === 'PUT')!, body = JSON.parse(String(saved.options.body))
    expect(body.revision).toBe(3)
    expect(body.policy).toMatchObject({ enabled: true, owner_number: POLICY.owner_number, workshop_number: POLICY.workshop_number, timezone: 'Europe/Warsaw', dnd: true, dnd_until: '2026-10-28T18:00:00+01:00', outside_hours: 'log_and_notify', no_answer: 'callback_request', exceptions: [{ start: '2026-12-24', end: '2026-12-26', label: 'Urlop' }] })
    expect(body.policy.weekly[0]).toEqual({ weekday: 0, windows: [{ start: '09:00', end: '12:00' }, { start: '13:00', end: '24:00' }] })
    expect(body.policy.weekly).toHaveLength(7)
    expect(state.revision).toBe(4)
    expect(calls.filter(call => call.path.endsWith('/preview'))).toHaveLength(0)
  })

  it('does not overwrite a newer policy after409 and requires a deliberate reload', async () => {
    let conflict = true
    const { calls, state } = server((_path, options) => options.method === 'PUT' && conflict ? response({ detail: CREDENTIAL }, 409) : undefined)
    panel(); await loaded(); const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Zapisz zasady' }))
    await screen.findByRole('alert')
    expect(screen.getByRole('button', { name: 'Zapisz zasady' })).toBeDisabled()
    expect(document.body.innerHTML).not.toContain(CREDENTIAL)
    expect(calls.filter(call => call.options.method === 'PUT')).toHaveLength(1)
    conflict = false; state.revision = 4
    await user.click(screen.getByRole('button', { name: 'Wczytaj zasady ponownie' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Zapisz zasady' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'Zapisz zasady' }))
    await screen.findByText('Zapisano zasady. Nie wykonano połączenia.')
    expect(JSON.parse(String(calls.filter(call => call.options.method === 'PUT')[1].options.body)).revision).toBe(4)
  })

  it('previews the saved server policy instead of submitting unsaved form changes', async () => {
    const { calls, state } = server(); panel(); await loaded(); const user = userEvent.setup()
    await user.click(screen.getByLabelText('Zezwalaj na przekazywanie'))
    await user.type(screen.getByLabelText('Termin podglądu ze strefą'), '2026-10-28T12:00:00+01:00')
    await user.selectOptions(screen.getByLabelText('Przykładowa sytuacja'), 'crisis')
    await user.click(screen.getByRole('button', { name: 'Sprawdź decyzję' }))
    await screen.findByText('Podgląd — nie wykonano połączenia ani wysyłki.')
    expect(JSON.parse(String(calls.find(call => call.path.endsWith('/preview'))!.options.body))).toEqual({ at: '2026-10-28T12:00:00+01:00', situation: 'crisis' })
    expect(state.policy.enabled).toBe(false)
    expect(calls.filter(call => call.options.method === 'PUT')).toHaveLength(0)
    expect(screen.getByText('Przekazywanie wyłączone')).toBeInTheDocument()
    expect(screen.getByText('Właściciel zawsze musi osobno zaakceptować kontakt.')).toBeInTheDocument()
  })

  it('rejects an offsetless preview time and overlapping hours before any mutation', async () => {
    const { calls } = server(); panel(); await loaded(); const user = userEvent.setup()
    await user.type(screen.getByLabelText('Termin podglądu ze strefą'), '2026-10-28T12:00:00')
    await user.click(screen.getByRole('button', { name: 'Sprawdź decyzję' }))
    await screen.findByRole('alert')
    const hours = screen.getByLabelText('Środa'); await user.clear(hours); await user.type(hours, '08:00-12:00, 11:00-18:00')
    await user.click(screen.getByRole('button', { name: 'Zapisz zasady' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('niepokrywających'))
    expect(calls).toHaveLength(1)
  })

  it('never presents a response claiming execution as a valid harmless preview', async () => {
    server(path => path.endsWith('/preview') ? response({ ...DECISION, situation: 'routine', executed: true }) : undefined)
    panel(); await loaded(); await userEvent.setup().click(screen.getByRole('button', { name: 'Sprawdź decyzję' }))
    await screen.findByRole('alert')
    expect(screen.queryByText('Podgląd — nie wykonano połączenia ani wysyłki.')).not.toBeInTheDocument()
  })

  it('clears private policy and preview controls on401 without retrying the mutation', async () => {
    const { calls } = server((_path, options) => options.method === 'PUT' ? response({}, 401) : undefined)
    const { onUnauthorized } = panel(); await loaded()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Zapisz zasady' }))
    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledTimes(1))
    expect(screen.queryByLabelText('Numer właściciela')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Termin podglądu ze strefą')).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain(POLICY.owner_number)
    expect(calls.filter(call => call.options.method === 'PUT')).toHaveLength(1)
  })

  it('does not let a late401 from a former credential clear a new identity', async () => {
    let resolveOld: ((value: Response) => void) | undefined
    server((_path, options) => new Headers(options.headers).get('X-Jarvis-Key') === CREDENTIAL ? new Promise<Response>(resolve => { resolveOld = resolve }) : undefined)
    const onUnauthorized = vi.fn(), view = render(<TelephonyPanel credential={CREDENTIAL} onUnauthorized={onUnauthorized} />)
    await waitFor(() => expect(resolveOld).toBeDefined())
    view.rerender(<TelephonyPanel credential="synthetic-second-session" onUnauthorized={onUnauthorized} />)
    await loaded()
    await act(async () => resolveOld!(response({}, 401)))
    expect(onUnauthorized).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Numer właściciela')).toHaveValue(POLICY.owner_number)
  })

  it('aborts outstanding reads on unmount and ignores their late completion', async () => {
    let resolveRead: ((value: Response) => void) | undefined, signal: AbortSignal | undefined
    server((_path, options) => { signal = options.signal as AbortSignal; return new Promise<Response>(resolve => { resolveRead = resolve }) })
    const view = panel(); await waitFor(() => expect(resolveRead).toBeDefined()); view.unmount()
    expect(signal?.aborted).toBe(true)
    await act(async () => resolveRead!(response({}, 401)))
    expect(view.onUnauthorized).not.toHaveBeenCalled()
  })
})

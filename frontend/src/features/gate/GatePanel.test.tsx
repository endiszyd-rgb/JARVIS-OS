import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { GatePanel } from './GatePanel'
import { GateTile } from './GateTile'

const KEY = 'synthetic-gate-owner-key'
const gate = (state = 'closed', extra = {}) => ({ name: 'Brama warsztatu', driver: 'simulator', live: false, state, state_label: state === 'closed' ? 'zamknięta' : state === 'opening' ? 'otwiera się' : state, changed: null, last_action: null, require_confirmation: false, pulse: false, ...extra })
const config = { driver: 'simulator', name: 'Brama warsztatu', require_confirmation: false, cooldown_seconds: 3, travel_seconds: 15, pulse: false, http: null, tuya: null, home_assistant: null }
const overview = (state = 'closed', events: unknown[] = [], extra = {}) => ({ gate: gate(state, extra), config: { ...config, ...extra }, revision: 1, events, drivers: ['simulator', 'http', 'tuya_cloud', 'home_assistant', 'disabled'] })
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
afterEach(() => vi.unstubAllGlobals())

describe('Gate panel', () => {
  it('loads the overview, sends an open command and shows the new state', async () => {
    let state = 'closed'
    const fetch = vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/devices/gate') return json(overview(state))
      if (path === '/api/v1/devices/gate/command') {
        const body = JSON.parse(String(options.body))
        expect(body.action).toBe('open'); expect(body.source).toBe('panel')
        state = 'opening'
        return json({ status: 'executed', action: 'open', external_request_sent: false, gate: gate('opening') })
      }
      return json({ detail: 'unexpected' }, 404)
    })
    vi.stubGlobal('fetch', fetch)
    render(<GatePanel credential={KEY} onUnauthorized={vi.fn()} />)
    expect(await screen.findByText('ZAMKNIĘTA')).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Otwórz' }))
    expect(await screen.findByText('OTWIERA SIĘ')).toBeInTheDocument()
    expect(new Headers(fetch.mock.calls[0]?.[1]?.headers).get('X-Jarvis-Key')).toBe(KEY)
    expect(document.body.innerHTML).not.toContain(KEY)
  })

  it('asks for confirmation when the server requires it and only then executes', async () => {
    let executed = false
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/devices/gate') return json(overview('closed', [], { require_confirmation: true }))
      const body = JSON.parse(String(options.body))
      if (!body.confirm_token) return json({ status: 'confirmation_required', action: 'close', confirm_token: 'tok-1', expires_in: 12, prompt: 'Zamknąć bramę?', gate: gate('closed') })
      expect(body.confirm_token).toBe('tok-1'); executed = true
      return json({ status: 'executed', action: 'close', external_request_sent: false, gate: gate('closing', { state_label: 'zamyka się' }) })
    }))
    const user = userEvent.setup()
    render(<GatePanel credential={KEY} onUnauthorized={vi.fn()} />)
    await screen.findByText('ZAMKNIĘTA')
    await user.click(screen.getByRole('button', { name: 'Zamknij' }))
    expect(await screen.findByText('Zamknąć bramę?')).toBeInTheDocument()
    expect(executed).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Tak, wykonaj' }))
    await waitFor(() => expect(executed).toBe(true))
  })

  it('shows driver fields for the selected driver and saves configuration with the revision', async () => {
    let saved: Record<string, unknown> | null = null
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/devices/gate') return json(overview())
      if (path === '/api/v1/devices/gate/config' && options.method === 'PUT') { saved = JSON.parse(String(options.body)); return json({ config: { ...config, driver: 'http' }, revision: 2 }) }
      return json({}, 404)
    }))
    const user = userEvent.setup()
    render(<GatePanel credential={KEY} onUnauthorized={vi.fn()} />)
    await screen.findByText('ZAMKNIĘTA')
    await user.click(screen.getByRole('button', { name: 'Edytuj' }))
    await user.selectOptions(screen.getByLabelText('Sterownik'), 'http')
    await user.type(screen.getByLabelText('URL otwarcia'), 'http://192.168.1.50/relay/0?turn=on')
    await user.click(screen.getByRole('button', { name: 'Zapisz konfigurację' }))
    await screen.findByText('Konfiguracja bramy zapisana.')
    expect(saved).not.toBeNull()
    expect(saved!.revision).toBe(1)
    expect((saved!.config as { driver: string; http: { open_url: string } }).http.open_url).toBe('http://192.168.1.50/relay/0?turn=on')
  })

  it('reports session expiry through onUnauthorized', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ detail: 'expired' }, 401)))
    const unauthorized = vi.fn()
    render(<GatePanel credential={KEY} onUnauthorized={unauthorized} />)
    await waitFor(() => expect(unauthorized).toHaveBeenCalledTimes(1))
    expect(document.body.textContent).not.toContain('expired')
  })
})

describe('Gate dashboard tile', () => {
  it('renders the state and sends a close command', async () => {
    const fetch = vi.fn(async (input: RequestInfo | URL, _options: RequestInit = {}) => String(input) === '/api/v1/devices/gate' ? json(overview('open', [], { state_label: 'otwarta' }))
      : json({ status: 'executed', action: 'close', external_request_sent: false, gate: gate('closing', { state_label: 'zamyka się' }) }))
    vi.stubGlobal('fetch', fetch)
    render(<GateTile credential={KEY} onUnauthorized={vi.fn()} />)
    await screen.findByText('OTWARTA')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Zamknij' }))
    expect(await screen.findByText('ZAMYKA SIĘ')).toBeInTheDocument()
    expect(JSON.parse(String(fetch.mock.calls[1][1]?.body)).action).toBe('close')
  })
})

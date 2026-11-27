import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { GateSettings, explain } from './GateSettings'
import { ApiError } from '../../api'
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

  it('settings: shows driver fields for the selected driver and saves configuration with the revision', async () => {
    let saved: Record<string, unknown> | null = null
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/devices/gate') return json(overview())
      if (path === '/api/v1/devices/gate/config' && options.method === 'PUT') { saved = JSON.parse(String(options.body)); return json({ config: { ...config, driver: 'http' }, revision: 2 }) }
      return json({}, 404)
    }))
    const user = userEvent.setup()
    render(<GateSettings credential={KEY} onUnauthorized={vi.fn()} />)
    await user.selectOptions(await screen.findByLabelText('Sterownik'), 'http')
    await user.type(screen.getByLabelText('Adres otwarcia'), 'http://192.168.1.50/relay/0?turn=on')
    await user.click(screen.getByRole('button', { name: 'Zapisz' }))
    await screen.findByText('Ustawienia bramy zapisane.')
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

describe('Gate settings hints and placement', () => {
  it('offers Setti/Tuya first, explains fields with a "?" hint and keeps driver settings out of the gate view', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(overview())))
    const user = userEvent.setup()
    render(<GateSettings credential={KEY} onUnauthorized={vi.fn()} />)
    const driver = await screen.findByLabelText('Sterownik') as HTMLSelectElement
    expect([...driver.options].map(item => item.value).slice(0, 2)).toEqual(['tuya_local', 'tuya_cloud'])
    await user.selectOptions(driver, 'tuya_cloud')
    const hint = screen.getByRole('button', { name: 'Podpowiedź: Access ID' })
    const bubble = document.getElementById(hint.getAttribute('aria-describedby')!)!
    expect(bubble).toHaveAttribute('role', 'tooltip')
    expect(bubble.textContent).toContain('iot.tuya.com')
    expect(hint).toHaveAttribute('aria-expanded', 'false')
    await user.click(hint)  // tap on a phone
    expect(hint).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByLabelText('Access ID')).toBeInTheDocument()
    expect(screen.getByText('Więcej opcji')).toBeInTheDocument()  // codes are folded away
  })

  it('local Setti/Tuya: finds the device on the LAN, fetches the key once and saves without showing it', async () => {
    const saved: Record<string, unknown>[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/devices/gate') {
        const last = saved.at(-1) as { tuya_local: Record<string, unknown> } | undefined
        return json(last ? { ...overview(), config: { ...last, tuya_local: { ...last.tuya_local, local_key: '••••••••', local_key_set: true } }, revision: 2 } : overview())
      }
      if (path === '/api/v1/devices/gate/tuya-local/scan') return json({ devices: [{ address: '192.168.1.50', device_id: 'bf98dev', version: '3.4' }] })
      if (path === '/api/v1/devices/gate/tuya-local/key') {
        expect(JSON.parse(String(options.body))).toEqual({ device_id: 'bf98dev' })
        return json({ local_key: 'secret-local-key', name: 'Brama Setti' })
      }
      if (path === '/api/v1/devices/gate/config') {
        const body = JSON.parse(String(options.body)); saved.push(body.config)
        return json({ config: { ...body.config, tuya_local: { ...body.config.tuya_local, local_key: '••••••••', local_key_set: true } }, revision: 2 })
      }
      return json({ detail: 'unexpected' }, 404)
    }))
    const user = userEvent.setup()
    render(<GateSettings credential={KEY} onUnauthorized={vi.fn()} />)
    await user.selectOptions(await screen.findByLabelText('Sterownik'), 'tuya_local')
    await user.click(screen.getByRole('button', { name: 'Znajdź w sieci' }))
    await user.click(await screen.findByRole('button', { name: /192\.168\.1\.50 · bf98dev/ }))
    expect(screen.getByLabelText('Adres IP sterownika')).toHaveValue('192.168.1.50')
    expect(screen.getByLabelText('ID urządzenia')).toHaveValue('bf98dev')
    await user.click(screen.getByRole('button', { name: 'Pobierz klucz z chmury Tuya' }))
    expect(await screen.findByText(/Klucz pobrany \(Brama Setti\)/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Zapisz' }))
    await waitFor(() => expect(saved).toHaveLength(1))
    expect(saved[0]).toMatchObject({ driver: 'tuya_local', tuya_local: { address: '192.168.1.50', device_id: 'bf98dev', local_key: 'secret-local-key', version: '3.4' } })
    const key = await screen.findByLabelText('Klucz lokalny')
    await waitFor(() => expect(key).toHaveValue(''))  // stored key is not shown as dots
    expect(key).toHaveAttribute('placeholder', expect.stringContaining('zapisany ✓'))
    expect(document.body.innerHTML).not.toContain('secret-local-key')
  })

  it('one-button Setti: "Otwórz" can send the same signal as "Zamknij"', async () => {
    const saved: Record<string, unknown>[] = []
    const local = { device_id: 'bf98dev', local_key: '••••••••', local_key_set: true, address: '192.168.1.50', version: '3.4', open_dp: 1, open_value: true, close_dp: 1, close_value: false, stop_dp: 0, stop_value: true, status_dp: 0 }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/devices/gate') return json({ ...overview(), config: { ...config, driver: 'tuya_local', tuya_local: saved.at(-1)?.tuya_local ?? local } })
      if (path === '/api/v1/devices/gate/config') { const body = JSON.parse(String(options.body)); saved.push(body.config); return json({ config: body.config, revision: 2 }) }
      return json({ detail: 'unexpected' }, 404)
    }))
    const user = userEvent.setup()
    render(<GateSettings credential={KEY} onUnauthorized={vi.fn()} />)
    const same = await screen.findByLabelText(/„Otwórz” wysyła ten sam sygnał co „Zamknij”/)
    expect(same).not.toBeChecked()
    await user.click(same)
    expect(same).toBeChecked()
    expect(screen.getByLabelText('Sygnał przycisku Otwórz')).toHaveValue('off')
    await user.click(screen.getByRole('button', { name: 'Zapisz' }))
    await waitFor(() => expect(saved).toHaveLength(1))
    expect(saved[0]).toMatchObject({ tuya_local: { open_dp: 1, open_value: false, close_dp: 1, close_value: false, local_key: '••••••••' } })
    await user.click(await screen.findByLabelText(/„Otwórz” wysyła ten sam sygnał co „Zamknij”/))
    expect(screen.getByLabelText('Sygnał przycisku Otwórz')).toHaveValue('on')
  })

  it('explains Tuya errors with the next step', () => {
    expect(explain(new ApiError(502, 'http', 'Tuya error 28841107: No permission. The data center is suspended.'))).toContain('Central Europe')
    expect(explain(new ApiError(502, 'http', 'Tuya error 28841101: expired'))).toContain('Extend Trial Period')
    expect(explain(new ApiError(502, 'http', 'Tuya local error 914: Check device key — zły klucz lokalny albo wersja protokołu'))).toContain('zły klucz lokalny')
    expect(explain(new ApiError(502, 'http', 'Gate controller is unreachable'))).toContain('adres IP')
  })

  it('the gate view only links to the settings', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(overview())))
    render(<GatePanel credential={KEY} onUnauthorized={vi.fn()} />)
    await screen.findByText('ZAMKNIĘTA')
    expect(screen.queryByLabelText('Sterownik')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ustawienia → Brama' })).toHaveAttribute('href', '#/settings/gate')
  })
})

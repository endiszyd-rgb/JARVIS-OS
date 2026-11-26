import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ConnectionSettings, TodayCard } from './TodayCard'

const KEY = 'synthetic-workshop-owner-key'
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const order = (id: number, plate: string, status: string, label: string) => ({ id, title: 'Naprawa ' + id, status, status_label: label, wait_state: 'BRAK', due_at: '2026-11-26', plate, make: 'Skoda', model: 'Fabia', customer: 'Jan Testowy' })
const BRIEF = { mode: 'live_readonly', date: '2026-11-26', open_orders: 4, by_status: { NAPRAWA: 1 }, due_today: [order(2, 'PO12345', 'NAPRAWA', 'naprawa')], overdue: [], ready: [order(3, 'WX9876A', 'GOTOWE', 'gotowe do odbioru')], waiting_customer: [], waiting_parts_orders: 1,
  to_order: [{ order_id: 2, plate: 'PO12345', name: 'Zestaw rozrządu', part_no: 'INA-530', qty: 1, status: 'DO_ZAMOWIENIA', supplier: null, expected_at: null }], on_order: [], partial: false }
afterEach(() => vi.unstubAllGlobals())

describe('Today in the workshop', () => {
  it('reads nothing until asked, then shows orders and parts', async () => {
    const fetch = vi.fn(async (_input: RequestInfo | URL) => json(BRIEF))
    vi.stubGlobal('fetch', fetch)
    render(<TodayCard credential={KEY} onUnauthorized={vi.fn()} />)
    expect(fetch).not.toHaveBeenCalled()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Pokaż dziś' }))
    expect(await screen.findByText('Zestaw rozrządu')).toBeInTheDocument()
    expect(screen.getByText('Skoda Fabia · PO12345')).toBeInTheDocument()
    expect(screen.getByText('Skoda Fabia · WX9876A')).toBeInTheDocument()
    expect(String(fetch.mock.calls[0]?.[0])).toBe('/api/v1/autologika/today')
  })

  it('explains a missing or unreachable connection', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ detail: 'AutoLogika unavailable, PIN rejected or response invalid' }, 502)))
    render(<TodayCard credential={KEY} onUnauthorized={vi.fn()} autoLoad />)
    expect(await screen.findByText(/AutoLogika nie odpowiada albo odrzuciła PIN/)).toBeInTheDocument()
  })

  it('saves the connection without echoing the PIN and tests it', async () => {
    const bodies: unknown[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/autologika/connection' && options.method === 'PUT') { bodies.push(JSON.parse(String(options.body))); return json({ config: { enabled: true, url: 'http://127.0.0.1:8787', pin: '••••••', pin_set: true }, revision: 1 }) }
      if (path === '/api/v1/autologika/connection') return json({ config: { enabled: false, url: 'http://127.0.0.1:8787', pin: '', pin_set: false }, revision: 0 })
      if (path === '/api/v1/autologika/connection/test') return json({ status: 'connected', open_orders: 4 })
      return json({}, 404)
    }))
    const saved = vi.fn()
    render(<ConnectionSettings credential={KEY} onUnauthorized={vi.fn()} onSaved={saved} />)
    const user = userEvent.setup()
    await user.click(await screen.findByLabelText('Połączenie na żywo włączone'))
    await user.type(screen.getByLabelText('PIN'), '246810')
    await user.click(screen.getByRole('button', { name: 'Zapisz i sprawdź połączenie' }))
    expect(await screen.findByText('Połączono. Otwartych zleceń: 4.')).toBeInTheDocument()
    expect(bodies).toEqual([{ revision: 0, config: { enabled: true, url: 'http://127.0.0.1:8787', pin: '246810' } }])
    await waitFor(() => expect(saved).toHaveBeenCalled())
    expect(screen.getByLabelText('PIN')).toHaveValue('')
  })
})

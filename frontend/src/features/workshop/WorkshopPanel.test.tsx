import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { WorkshopPanel } from './WorkshopPanel'

const KEY = 'synthetic-workshop-session-key'
const COMMIT = 'a'.repeat(40), SHA = 'b'.repeat(64), DATE = '2026-10-25T10:00:00Z'
const DOMAINS = ['calendar', 'orders', 'vehicles', 'parts', 'customers', 'finances', 'reports', 'notifications']
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
type Call = { path: string; options: RequestInit }
type Handler = (path: string, options: RequestInit) => Response | Promise<Response> | undefined
function server(handler?: Handler) {
  const calls: Call[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
    const path = String(input); calls.push({ path, options })
    const custom = handler?.(path, options)
    if (custom !== undefined) return await custom
    const url = new URL(path, 'http://localhost')
    if (url.pathname === '/api/v1/autologika/snapshot') return json({ mode: 'snapshot_readonly', created_at: DATE, sha256: SHA, audited_commit: COMMIT, domains: DOMAINS, live: false })
    if (url.pathname.startsWith('/api/v1/autologika/snapshot/')) {
      const domain = url.pathname.split('/').at(-1)!
      const offset = Number(url.searchParams.get('offset'))
      let data: unknown = { items: offset ? [] : [{ id: 1, title: 'Testowe zlecenie', status: 'NOWE' }], has_more: offset === 0 }
      if (domain === 'parts') data = { job_part_orders: { items: offset ? [] : [{ id: 1, name: 'Filtr testowy' }], has_more: offset === 0 }, inventory_parts: { items: [], has_more: false }, repair_parts: { items: [], has_more: false } }
      if (domain === 'finances') data = { month: url.searchParams.get('month'), currency: 'PLN', accounting_profit: false, orders_count: 3, orders_value: 500, contribution: 200, receivables: 100, paid_in_month: 400 }
      if (domain === 'reports') data = { status_counts: [{ status: 'NOWE', count: 1 }] }
      return json({ mode: 'snapshot_readonly', domain, snapshot_created_at: DATE, sha256: SHA, audited_commit: COMMIT, limit: 50, offset, data })
    }
    if (url.pathname.startsWith('/api/v1/autologika/readonly/orders')) return json({ mode: 'live_readonly', audited_commit: COMMIT, data: [{ id: 8, title: 'Zlecenie z usługi' }] })
    throw new Error('Unexpected workshop request: ' + path)
  }))
  return calls
}
function panel(canReadPrivate = true, onUnauthorized = vi.fn(), credential = KEY) { return <WorkshopPanel credential={credential} onUnauthorized={onUnauthorized} canReadPrivate={canReadPrivate} /> }
afterEach(() => vi.unstubAllGlobals())

describe('AutoLogika reads preserve source and role boundaries', () => {
  it('performs no automatic reads and paginates the offline source explicitly', async () => {
    const calls = server(), user = userEvent.setup()
    render(panel())
    expect(calls).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: 'Odczytaj domenę' }))
    await screen.findByText('Testowe zlecenie')
    expect(screen.getByText('snapshot_readonly')).toBeInTheDocument()
    expect(screen.getByText(/Utworzono kopię/)).toBeInTheDocument()
    expect(new Headers(calls[0].options.headers).get('X-Jarvis-Key')).toBe(KEY)
    expect(calls[0].path).toContain('/snapshot/orders?limit=50&offset=0&month=')
    await user.click(screen.getByRole('button', { name: 'Następna strona danych' }))
    await screen.findByText('Brak rekordów w tym odczycie.')
    expect(calls[1].path).toContain('offset=50')
    expect(screen.getByRole('button', { name: 'Następna strona danych' })).toBeDisabled()
    expect(document.body.innerHTML).not.toContain(KEY)
  })

  it('limits workshop readers to five domains and remounts when private access changes', async () => {
    const calls = server(), user = userEvent.setup()
    const view = render(panel())
    await user.selectOptions(screen.getByLabelText('Domena kopii'), 'finances')
    await user.click(screen.getByRole('button', { name: 'Odczytaj domenę' }))
    await screen.findByText('Wartość zleceń PLN')
    view.rerender(panel(false))
    expect(screen.queryByText('Wartość zleceń PLN')).not.toBeInTheDocument()
    expect(screen.getAllByRole('option')).toHaveLength(5)
    expect(screen.queryByRole('option', { name: 'Finanse' })).not.toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Raporty' })).not.toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Powiadomienia' })).not.toBeInTheDocument()
    expect(calls).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: 'Odczytaj domenę' }))
    await screen.findByText('Testowe zlecenie')
    expect(calls[1].path).toContain('/snapshot/orders?')
  })

  it('renders three independently bounded parts collections with shared pagination', async () => {
    const calls = server(), user = userEvent.setup()
    render(panel(false))
    await user.selectOptions(screen.getByLabelText('Domena kopii'), 'parts')
    await user.click(screen.getByRole('button', { name: 'Odczytaj domenę' }))
    await screen.findByText('Filtr testowy')
    expect(screen.getByRole('heading', { name: 'Magazyn części' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Części napraw' })).toBeInTheDocument()
    expect(screen.getAllByText('Brak rekordów w tym odczycie.')).toHaveLength(2)
    await user.click(screen.getByRole('button', { name: 'Następna strona danych' }))
    await waitFor(() => expect(screen.getAllByText('Brak rekordów w tym odczycie.')).toHaveLength(3))
    expect(calls[1].path).toContain('/parts?limit=50&offset=50')
  })

  it('separates live requests from snapshot reads and escapes returned content', async () => {
    const unsafe = '<img src=x onerror="stolen()">'
    const calls = server(path => path.includes('/readonly/') ? json({ mode: 'live_readonly', audited_commit: COMMIT, data: [{ id: 3, title: unsafe }] }) : undefined)
    const user = userEvent.setup()
    render(panel(false))
    expect(calls).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: 'Odczytaj zlecenia' }))
    await screen.findByText(unsafe)
    expect(screen.getByText('live_readonly')).toBeInTheDocument()
    expect(screen.queryByText(/Utworzono kopię/)).not.toBeInTheDocument()
    expect(document.querySelector('img')).toBeNull()
    expect(calls.map(call => call.path)).toEqual(['/api/v1/autologika/readonly/orders'])
  })

  it('validates live order IDs and retrieves the real detail contract without a snapshot request', async () => {
    const calls = server(path => path.endsWith('/readonly/orders/42') ? json({ mode: 'live_readonly', audited_commit: COMMIT, data: { order: { id: 42, title: 'Szczegół testowy' }, notes: [], diag: [], parts: [], payments: [] } }) : undefined)
    const user = userEvent.setup()
    render(panel(false))
    const id = screen.getByLabelText('Numer zlecenia (opcjonalnie)')
    await user.type(id, '-2')
    expect(screen.getByRole('button', { name: 'Odczytaj zlecenia' })).toBeDisabled()
    expect(calls).toHaveLength(0)
    await user.clear(id); await user.type(id, '42')
    await user.click(screen.getByRole('button', { name: 'Odczytaj zlecenia' }))
    await screen.findByText(/"title": "Szczegół testowy"/)
    expect(calls.map(call => call.path)).toEqual(['/api/v1/autologika/readonly/orders/42'])
    expect(screen.queryByRole('button', { name: 'Następna strona danych' })).not.toBeInTheDocument()
  })

  it('shows snapshot metadata as offline availability without fetching service data', async () => {
    const calls = server(), user = userEvent.setup()
    render(panel(false))
    await user.click(screen.getByRole('button', { name: 'Sprawdź kopię' }))
    await screen.findByText('Informacje o kopii')
    expect(screen.getByText('snapshot_readonly')).toBeInTheDocument()
    expect(screen.getByText(SHA)).toBeInTheDocument()
    expect(calls.map(call => call.path)).toEqual(['/api/v1/autologika/snapshot'])
    expect(screen.queryByRole('button', { name: 'Następna strona danych' })).not.toBeInTheDocument()
  })

  it('shows unavailable integration errors without diagnostics or DEMO replacement', async () => {
    const calls = server(() => json({ detail: 'Synthetic PIN must stay hidden' }, 503)), user = userEvent.setup()
    render(panel())
    await user.click(screen.getByRole('button', { name: 'Sprawdź kopię' }))
    await screen.findByRole('alert')
    expect(screen.queryByText('Testowe zlecenie')).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain('Synthetic PIN must stay hidden')
    expect(calls).toHaveLength(1)
  })

  it('clears private results and reports 401 without retrying', async () => {
    let expired = false
    const calls = server(() => expired ? json({ detail: 'Hidden diagnostics' }, 401) : undefined), user = userEvent.setup(), unauthorized = vi.fn()
    render(panel(true, unauthorized))
    await user.click(screen.getByRole('button', { name: 'Odczytaj domenę' }))
    await screen.findByText('Testowe zlecenie')
    expired = true
    await user.click(screen.getByRole('button', { name: 'Sprawdź kopię' }))
    await waitFor(() => expect(unauthorized).toHaveBeenCalledTimes(1))
    expect(screen.queryByText('Testowe zlecenie')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Sprawdź kopię' }))
    expect(calls).toHaveLength(2)
  })

  it('aborts pending reads and ignores late data after credentials change', async () => {
    let finish: ((result: Response) => void) | undefined, signal: AbortSignal | null | undefined
    server((_path, options) => { signal = options.signal; return new Promise<Response>(resolve => { finish = resolve }) })
    const user = userEvent.setup(), view = render(panel())
    await user.click(screen.getByRole('button', { name: 'Sprawdź kopię' }))
    await waitFor(() => expect(finish).toBeDefined())
    view.rerender(panel(true, vi.fn(), 'synthetic-next-credential'))
    expect(signal?.aborted).toBe(true)
    await act(async () => { finish!(json({ mode: 'snapshot_readonly', created_at: DATE, sha256: SHA, audited_commit: COMMIT, domains: DOMAINS, live: false })) })
    expect(screen.queryByText('Informacje o kopii')).not.toBeInTheDocument()
  })

  it('rejects malformed source metadata instead of declaring the copy available', async () => {
    server(() => json({ mode: 'snapshot_readonly', created_at: 'invalid date', sha256: SHA, audited_commit: COMMIT, domains: DOMAINS, live: false }))
    render(panel())
    await userEvent.setup().click(screen.getByRole('button', { name: 'Sprawdź kopię' }))
    await screen.findByRole('alert')
    expect(screen.queryByText('Informacje o kopii')).not.toBeInTheDocument()
  })
})

import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { HomePanel } from './HomePanel'

const KEY = 'synthetic-home-reader-key'
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
const DATA = { mode: 'live_readonly', controls_enabled: false, states: [{ entity_id: 'sensor.temperatura', state: '21.7', attributes: { friendly_name: 'Temperatura testowa', unit_of_measurement: '°C', synthetic_private_extra: 'Hidden attribute' } }] }
type Call = { path: string; options: RequestInit }
function server(handler: (path: string, options: RequestInit) => Response | Promise<Response> = () => response(DATA)) {
  const calls: Call[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => { const path = String(input); calls.push({ path, options }); return await handler(path, options) }))
  return calls
}
afterEach(() => vi.unstubAllGlobals())
describe('Home states require explicit reads', () => {
  it('reads states only on request, without fetching owner-only integration metadata', async () => {
    const calls = server(), user = userEvent.setup()
    render(<HomePanel credential={KEY} onUnauthorized={vi.fn()} />)
    expect(calls).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: 'Odczytaj stany' }))
    await screen.findByText('Temperatura testowa')
    expect(screen.getByText('live_readonly')).toBeInTheDocument()
    expect(calls.map(call => call.path)).toEqual(['/api/v1/home/states'])
    expect(new Headers(calls[0].options.headers).get('X-Jarvis-Key')).toBe(KEY)
    expect(document.body.textContent).not.toContain('Hidden attribute')
    expect(document.body.innerHTML).not.toContain(KEY)
    expect(screen.getAllByRole('button')).toHaveLength(1)
  })
  it('validates entity names before issuing allowlist-protected single-entity reads', async () => {
    const calls = server(), user = userEvent.setup()
    render(<HomePanel credential={KEY} onUnauthorized={vi.fn()} />)
    const entity = screen.getByLabelText('Encja Home Assistant (opcjonalnie)')
    await user.type(entity, '../private')
    expect(screen.getByRole('button', { name: 'Odczytaj stany' })).toBeDisabled()
    expect(calls).toHaveLength(0)
    await user.clear(entity); await user.type(entity, 'sensor.temperatura')
    await user.click(screen.getByRole('button', { name: 'Odczytaj stany' }))
    await screen.findByText('Temperatura testowa')
    expect(calls[0].path).toBe('/api/v1/home/states/sensor.temperatura')
  })
  it.each([503, 502, 403])('keeps HTTP%s diagnostics private and does not invent DEMO states', async status => {
    const calls = server(() => response({ detail: 'Synthetic secret URL' }, status))
    render(<HomePanel credential={KEY} onUnauthorized={vi.fn()} />)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Odczytaj stany' }))
    await screen.findByRole('alert')
    expect(document.body.textContent).not.toContain('Synthetic secret URL')
    expect(screen.queryByText('Temperatura testowa')).not.toBeInTheDocument()
    expect(calls).toHaveLength(1)
  })
  it('renders an empty allowlisted response without claiming that no devices exist', async () => {
    server(() => response({ ...DATA, states: [] }))
    render(<HomePanel credential={KEY} onUnauthorized={vi.fn()} />)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Odczytaj stany' }))
    await screen.findByText('Brak dozwolonych encji w odpowiedzi usługi.')
  })
  it('clears states on 401 and forwards session expiry exactly once', async () => {
    let expired = false
    const calls = server(() => expired ? response({}, 401) : response(DATA)), unauthorized = vi.fn(), user = userEvent.setup()
    render(<HomePanel credential={KEY} onUnauthorized={unauthorized} />)
    await user.click(screen.getByRole('button', { name: 'Odczytaj stany' }))
    await screen.findByText('Temperatura testowa')
    expired = true
    await user.click(screen.getByRole('button', { name: 'Odczytaj stany' }))
    await waitFor(() => expect(unauthorized).toHaveBeenCalledTimes(1))
    expect(screen.queryByText('Temperatura testowa')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Odczytaj stany' }))
    expect(calls).toHaveLength(2)
  })
  it('discards delayed private reads and clears entity fields on credential replacement', async () => {
    let finish: ((value: Response) => void) | undefined, signal: AbortSignal | null | undefined
    server((_path, options) => { signal = options.signal; return new Promise<Response>(resolve => { finish = resolve }) })
    const user = userEvent.setup(), view = render(<HomePanel credential={KEY} onUnauthorized={vi.fn()} />)
    await user.type(screen.getByLabelText('Encja Home Assistant (opcjonalnie)'), 'sensor.temperatura')
    await user.click(screen.getByRole('button', { name: 'Odczytaj stany' }))
    await waitFor(() => expect(finish).toBeDefined())
    view.rerender(<HomePanel credential="synthetic-next-reader" onUnauthorized={vi.fn()} />)
    expect(screen.getByLabelText('Encja Home Assistant (opcjonalnie)')).toHaveValue('')
    expect(signal?.aborted).toBe(true)
    await act(async () => { finish!(response(DATA)) })
    expect(screen.queryByText('Temperatura testowa')).not.toBeInTheDocument()
  })
  it('escapes service strings and rejects responses that claim control is enabled', async () => {
    let malformed = false
    const unsafe = '<img src=x onerror="steal()">'
    server(() => response({ ...DATA, controls_enabled: malformed, states: [{ ...DATA.states[0], attributes: { friendly_name: unsafe } }] }))
    const user = userEvent.setup()
    render(<HomePanel credential={KEY} onUnauthorized={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Odczytaj stany' }))
    await screen.findByText(unsafe)
    expect(document.querySelector('img')).toBeNull()
    malformed = true
    await user.click(screen.getByRole('button', { name: 'Odczytaj stany' }))
    await screen.findByRole('alert')
    expect(screen.queryByText(unsafe)).not.toBeInTheDocument()
  })
})

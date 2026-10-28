import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ActivityPanel } from './ActivityPanel'

const KEY = 'activity-synthetic-owner-token'
const ROWS = [
  { id: 9, event: 'memory.saved', detail: '{"actor":"owner-key","id":"note-id"}', created: 1800000010 },
  { id: 7, event: 'plugin.invoke_completed', detail: '{"plugin":"mqtt","operation":"status"}', created: 1800000000 },
]
function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

beforeEach(() => vi.stubGlobal('fetch', vi.fn(async () => response(ROWS))))
afterEach(() => vi.unstubAllGlobals())

describe('owner activity history', () => {
  it('requests only the latest audit endpoint and preserves its newest-first order', async () => {
    const calls = vi.mocked(fetch)
    render(<ActivityPanel credential={KEY} onUnauthorized={vi.fn()} />)
    await screen.findByText('memory.saved')
    expect(calls).toHaveBeenCalledTimes(1)
    const [path, options] = calls.mock.calls[0]
    expect(path).toBe('/api/v1/audit')
    expect(new Headers(options?.headers).get('X-Jarvis-Key')).toBe(KEY)
    expect(options?.method).toBe('GET')
    const list = screen.getByRole('list', { name: 'Pobrane zdarzenia' })
    const items = within(list).getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('memory.saved')
    expect(items[1]).toHaveTextContent('plugin.invoke_completed')
    expect(screen.getByText(/Do 100 najnowszych zapisanych zdarzeń/)).toBeInTheDocument()
    expect(screen.getByText(/Pokazano 2 z 2 pobranych zdarzeń/)).toBeInTheDocument()
    expect(document.body.innerHTML).not.toContain(KEY)
  })

  it('filters the fetched rows locally without pretending to search a full archive', async () => {
    const calls = vi.mocked(fetch)
    render(<ActivityPanel credential={KEY} onUnauthorized={vi.fn()} />)
    await screen.findByText('memory.saved')
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Filtruj zdarzenia'), 'MQTT')
    expect(screen.getByText('plugin.invoke_completed')).toBeInTheDocument()
    expect(screen.queryByText('memory.saved')).not.toBeInTheDocument()
    expect(screen.getByText(/wyłącznie w pobranych zdarzeniach/)).toBeInTheDocument()
    expect(calls).toHaveBeenCalledTimes(1)
    await user.clear(screen.getByLabelText('Filtruj zdarzenia'))
    await user.type(screen.getByLabelText('Filtruj zdarzenia'), 'not-present')
    expect(screen.getByText('Brak zdarzeń pasujących do filtra w tym odczycie.')).toBeInTheDocument()
  })

  it('renders JSON or historical detail as escaped text, including HTML-shaped input', async () => {
    const injection = '<img src=x onerror="window.compromised=true"><script>bad()</script>'
    vi.mocked(fetch).mockResolvedValue(response([{ ...ROWS[0], detail: JSON.stringify({ note: injection }) }]))
    const { container } = render(<ActivityPanel credential={KEY} onUnauthorized={vi.fn()} />)
    await screen.findByText('memory.saved')
    await userEvent.setup().click(screen.getByText('Szczegóły zdarzenia 9'))
    expect(container.querySelector('pre')?.textContent).toContain(injection.replaceAll('"', '\\"'))
    expect(container.querySelector('img,script')).toBeNull()
  })

  it('keeps a previous read after refresh fails and does not display server diagnostics', async () => {
    const diagnostics = 'Synthetic internal response must stay hidden'
    vi.mocked(fetch).mockResolvedValueOnce(response(ROWS)).mockResolvedValueOnce(response({ detail: diagnostics }, 500))
    render(<ActivityPanel credential={KEY} onUnauthorized={vi.fn()} />)
    await screen.findByText('memory.saved')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Odśwież historię' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Wyświetlany jest poprzedni odczyt.')
    expect(screen.getByText('memory.saved')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain(diagnostics)
  })

  it('clears rows and notifies the parent after a refresh returns 401', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(response(ROWS)).mockResolvedValueOnce(response({}, 401))
    const unauthorized = vi.fn()
    render(<ActivityPanel credential={KEY} onUnauthorized={unauthorized} />)
    await screen.findByText('memory.saved')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Odśwież historię' }))
    await waitFor(() => expect(unauthorized).toHaveBeenCalledTimes(1))
    expect(screen.queryByText('memory.saved')).not.toBeInTheDocument()
  })

  it('aborts the old identity read and ignores a late response after credentials change', async () => {
    let resolveOld: ((value: Response) => void) | undefined
    let oldSignal: AbortSignal | undefined
    vi.mocked(fetch).mockImplementationOnce(async (_input, options) => {
      oldSignal = options?.signal as AbortSignal
      return new Promise<Response>(resolve => { resolveOld = resolve })
    }).mockResolvedValueOnce(response([{ ...ROWS[1], event: 'new.identity.event' }]))
    const unauthorized = vi.fn()
    const { rerender } = render(<ActivityPanel credential={KEY} onUnauthorized={unauthorized} />)
    await waitFor(() => expect(resolveOld).toBeDefined())
    rerender(<ActivityPanel credential="other-synthetic-token" onUnauthorized={unauthorized} />)
    await screen.findByText('new.identity.event')
    expect(oldSignal?.aborted).toBe(true)
    await act(async () => { resolveOld!(response(ROWS)) })
    expect(screen.queryByText('memory.saved')).not.toBeInTheDocument()
    expect(screen.getByText('new.identity.event')).toBeInTheDocument()
    expect(unauthorized).not.toHaveBeenCalled()
  })

  it('does not emit an unauthorized callback from a request completed after unmount', async () => {
    let resolve: ((value: Response) => void) | undefined
    let signal: AbortSignal | undefined
    vi.mocked(fetch).mockImplementationOnce(async (_input, options) => {
      signal = options?.signal as AbortSignal
      return new Promise<Response>(done => { resolve = done })
    })
    const unauthorized = vi.fn()
    const { unmount } = render(<ActivityPanel credential={KEY} onUnauthorized={unauthorized} />)
    await waitFor(() => expect(resolve).toBeDefined())
    unmount()
    expect(signal?.aborted).toBe(true)
    await act(async () => { resolve!(response({}, 401)) })
    expect(unauthorized).not.toHaveBeenCalled()
  })

  it('rejects an invalid or oversized history response without crashing or displaying it', async () => {
    vi.mocked(fetch).mockResolvedValue(response(Array.from({ length: 101 }, (_, id) => ({ ...ROWS[0], id }))))
    render(<ActivityPanel credential={KEY} onUnauthorized={vi.fn()} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie udało się odczytać odpowiedzi serwera.')
    expect(screen.queryByText('memory.saved')).not.toBeInTheDocument()
    expect(screen.queryByText('Nie ma zapisanych zdarzeń w tym odczycie.')).not.toBeInTheDocument()
    expect(screen.getByText('Brak aktualnego odczytu historii.')).toBeInTheDocument()
  })
})

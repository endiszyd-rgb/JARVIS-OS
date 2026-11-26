import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { KioskPanel } from './KioskPanel'

const KEY = 'synthetic-kiosk-owner-key'
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const gate = { name: 'Brama warsztatu', driver: 'simulator', live: false, state: 'closed', state_label: 'zamknięta', changed: null, last_action: null, require_confirmation: true, pulse: false }
afterEach(() => vi.unstubAllGlobals())

describe('Workshop screen', () => {
  it('runs typed commands, asks for confirmation with buttons and shows today', async () => {
    const sent: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/devices/gate') return json({ gate, config: { name: gate.name, driver: 'simulator', require_confirmation: true }, events: [] })
      if (path === '/api/v1/cameras') return json({ enabled: false, refresh_ms: 1000, cameras: [] })
      if (path === '/api/v1/autologika/today') return json({ detail: 'Read-only integration explicitly disabled' }, 503)
      if (path === '/api/v1/voice/command') {
        const text = JSON.parse(String(options.body)).text as string
        sent.push(text)
        return json(text === 'otwórz bramę' ? { reply: 'Otworzyć bramę? Powiedz „tak”, aby potwierdzić.', handled: true, device: { status: 'confirmation_required' } }
          : { reply: 'Otwieram: Brama warsztatu.', handled: true, device: { status: 'executed' } })
      }
      return json({}, 404)
    }))
    render(<KioskPanel credential={KEY} onUnauthorized={vi.fn()} workshopData />)
    const user = userEvent.setup()
    expect(await screen.findByText('Połączenie z AutoLogiką nie jest skonfigurowane.')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Polecenie'), 'otwórz bramę')
    await user.click(screen.getByRole('button', { name: 'Wyślij polecenie' }))
    await user.click(await screen.findByRole('button', { name: 'Tak' }))
    expect(await screen.findByText('Otwieram: Brama warsztatu.')).toBeInTheDocument()
    expect(sent).toEqual(['otwórz bramę', 'tak'])
    expect(screen.getByRole('button', { name: 'Co dziś?' })).toBeInTheDocument()
    expect(screen.getByText(/nie rozpoznaje mowy/)).toBeInTheDocument()  // jsdom has no speech recognition
  })
})

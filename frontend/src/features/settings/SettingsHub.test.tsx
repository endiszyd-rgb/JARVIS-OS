import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SettingsPanel } from './SettingsPanel'

const KEY = 'synthetic-settings-owner-key'
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const voice = { config: { engine: 'browser', wake_word: 'jarvis', wake_listening: true, language: 'pl-PL', speak_replies: true, send_to_model: false }, revision: 3, wyoming_available: false }
afterEach(() => { vi.unstubAllGlobals(); window.location.hash = '' })

describe('Settings hub', () => {
  it('opens the tab named in the address and switches tabs', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === '/api/v1/config/voice') return json(voice)
      if (path === '/api/v1/autologika/connection') return json({ config: { enabled: false, url: 'http://127.0.0.1:8787', pin: '', pin_set: false }, revision: 0 })
      return json({}, 404)
    }))
    window.location.hash = '#/settings/voice'
    render(<SettingsPanel credential={KEY} onUnauthorized={vi.fn()} onStatusChanged={vi.fn()} />)
    expect(screen.getByRole('tab', { name: 'Głos' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByLabelText('Słowo aktywujące')).toHaveValue('jarvis')
    expect(screen.getByRole('button', { name: 'Podpowiedź: Słowo aktywujące' })).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('tab', { name: 'AutoLogika' }))
    expect(await screen.findByLabelText('Adres AutoLogiki')).toHaveValue('http://127.0.0.1:8787')
    expect(window.location.hash).toBe('#/settings/autologika')
    expect(screen.getByRole('link', { name: 'Bezpieczeństwo' })).toHaveAttribute('href', '#/security')
  })
})

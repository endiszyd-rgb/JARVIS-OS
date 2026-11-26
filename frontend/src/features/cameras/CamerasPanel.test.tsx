import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CameraSettings, CamerasPanel } from './CamerasPanel'

const TOKEN = 'synthetic-camera-session-token-0123456789'
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
beforeEach(() => {
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:frame-1'), revokeObjectURL: vi.fn() }))
})
afterEach(() => vi.unstubAllGlobals())

describe('Cameras panel', () => {
  it('lists cameras and loads frames with the session header', async () => {
    const fetch = vi.fn(async (input: RequestInfo | URL, _options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/cameras') return json({ enabled: true, refresh_ms: 10000, cameras: [{ id: 'brama', name: 'Wjazd' }] })
      if (path === '/api/v1/cameras/brama/frame.jpg') return new Response(new Uint8Array([0xff, 0xd8]), { status: 200, headers: { 'Content-Type': 'image/jpeg' } })
      return json({ detail: 'unexpected' }, 404)
    })
    vi.stubGlobal('fetch', fetch)
    render(<CamerasPanel credential={TOKEN} onUnauthorized={vi.fn()} owner={false} />)
    expect(await screen.findByRole('img', { name: 'Podgląd: Wjazd' })).toHaveAttribute('src', 'blob:frame-1')
    const frameCall = fetch.mock.calls.find(call => String(call[0]).endsWith('frame.jpg'))
    expect(new Headers(frameCall?.[1]?.headers).get('X-Jarvis-Key')).toBe(TOKEN)
    expect(screen.queryByRole('heading', { name: 'Konfiguracja kamer' })).not.toBeInTheDocument()
    expect(document.body.innerHTML).not.toContain(TOKEN)
  })

  it('shows a camera problem without leaving the view', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => String(input) === '/api/v1/cameras'
      ? json({ enabled: true, refresh_ms: 10000, cameras: [{ id: 'hala', name: 'Hala' }] }) : json({ detail: 'Camera did not answer in time' }, 504)))
    render(<CamerasPanel credential={TOKEN} onUnauthorized={vi.fn()} owner={false} />)
    expect(await screen.findByText('Kamera nie odpowiada')).toBeInTheDocument()
  })

  it('lets the owner edit and save the go2rtc configuration', async () => {
    let saved: unknown = null
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/cameras') return json({ enabled: false, refresh_ms: 1000, cameras: [] })
      if (path === '/api/v1/cameras/config' && options.method === 'PUT') { saved = JSON.parse(String(options.body)); return json({ config: (saved as { config: unknown }).config, revision: 1 }) }
      if (path === '/api/v1/cameras/config') return json({ config: { enabled: false, go2rtc_url: 'http://127.0.0.1:1984', refresh_ms: 1000, cameras: [] }, revision: 0 })
      return json({ detail: 'unexpected' }, 404)
    }))
    render(<CameraSettings credential={TOKEN} onUnauthorized={vi.fn()} />)
    const user = userEvent.setup()
    await user.click(await screen.findByLabelText('Podgląd kamer włączony'))
    await user.click(screen.getByRole('button', { name: 'Dodaj kamerę' }))
    await user.type(screen.getByLabelText('Strumień go2rtc'), 'nvr_ch1')
    await user.click(screen.getByRole('button', { name: 'Zapisz' }))
    await waitFor(() => expect(saved).toEqual({ revision: 0, config: { enabled: true, go2rtc_url: 'http://127.0.0.1:1984', refresh_ms: 1000, cameras: [{ id: 'kamera1', name: 'Kamera 1', stream: 'nvr_ch1', enabled: true }] } }))
  })
})

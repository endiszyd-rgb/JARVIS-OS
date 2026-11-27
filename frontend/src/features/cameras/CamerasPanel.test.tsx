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
    await waitFor(() => expect(saved).toEqual({ revision: 0, config: { enabled: true, mode: 'external', go2rtc_url: 'http://127.0.0.1:1984', refresh_ms: 1000, cameras: [{ id: 'kamera1', name: 'Kamera 1', source: 'go2rtc', stream: 'nvr_ch1', device_id: '', uid: '', resolution: 'sd', rtsp_url: '', enabled: true }] } }))
  })

  it('built-in go2rtc: adds a Setti camera by Device ID, reads its UID and keeps RTSP passwords hidden', async () => {
    const saved: Record<string, unknown>[] = []
    const status = { available: true, running: false, ffmpeg: true, problems: [], error: null }
    const stored = { enabled: false, mode: 'builtin', go2rtc_url: 'http://127.0.0.1:1984', refresh_ms: 1000,
      cameras: [{ id: 'hala', name: 'Hala', source: 'rtsp', stream: '', device_id: '', uid: '', resolution: 'sd', rtsp_url: '••••••••', rtsp_set: true, enabled: true }] }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = String(input)
      if (path === '/api/v1/cameras/tuya-info') {
        expect(JSON.parse(String(options.body))).toEqual({ device_id: 'cam123' })
        return json({ uid: 'eu1700abc', name: 'Kamera zewnętrzna', category: 'sp', online: true })
      }
      if (path === '/api/v1/cameras/config' && options.method === 'PUT') {
        const body = JSON.parse(String(options.body)); saved.push(body.config)
        return json({ config: body.config, revision: 1, builtin: { ...status, running: true } })
      }
      if (path === '/api/v1/cameras/config') return json({ config: stored, revision: 0, builtin: status })
      return json({ detail: 'unexpected' }, 404)
    }))
    render(<CameraSettings credential={TOKEN} onUnauthorized={vi.fn()} />)
    const user = userEvent.setup()
    expect(await screen.findByText(/go2rtc uruchomi się po dodaniu kamery/)).toBeInTheDocument()
    const rtsp = screen.getByLabelText('Adres RTSP')
    expect(rtsp).toHaveValue('')
    expect(rtsp).toHaveAttribute('placeholder', expect.stringContaining('zapisany ✓'))
    await user.click(screen.getByRole('button', { name: 'Dodaj kamerę' }))
    expect(screen.getByLabelText('Podgląd kamer włączony')).toBeChecked()  // adding a camera switches the preview on
    expect(screen.getAllByLabelText('Rodzaj kamery')[1]).toHaveValue('tuya')
    await user.type(screen.getByLabelText('Device ID kamery'), ' cam123 ')
    await user.click(screen.getByRole('button', { name: 'Sprawdź kamerę' }))
    expect(await screen.findByText(/✓ Kamera zewnętrzna · online/)).toBeInTheDocument()
    expect(screen.getAllByLabelText('Nazwa')[1]).toHaveValue('Kamera zewnętrzna')
    await user.click(screen.getByRole('button', { name: 'Zapisz' }))
    await waitFor(() => expect(saved).toHaveLength(1))
    expect(saved[0]).toMatchObject({ enabled: true, mode: 'builtin', cameras: [
      { id: 'hala', source: 'rtsp', rtsp_url: '••••••••' },
      { id: 'kamera2', name: 'Kamera zewnętrzna', source: 'tuya', device_id: 'cam123', uid: 'eu1700abc', resolution: 'sd' }] })
    expect((saved[0].cameras as Record<string, unknown>[])[0]).not.toHaveProperty('rtsp_set')
    expect(await screen.findByText(/go2rtc działa/)).toBeInTheDocument()
  })

  it('built-in go2rtc missing: explains what to do', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ config: { enabled: true, mode: 'builtin', go2rtc_url: 'http://127.0.0.1:1984', refresh_ms: 1000, cameras: [] }, revision: 0,
      builtin: { available: false, running: false, ffmpeg: false, problems: [], error: null } })))
    render(<CameraSettings credential={TOKEN} onUnauthorized={vi.fn()} />)
    expect(await screen.findByText(/Wbudowany go2rtc nie jest zainstalowany/)).toBeInTheDocument()
  })
})

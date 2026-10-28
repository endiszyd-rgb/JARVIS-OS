import { afterEach, expect, it, vi } from 'vitest'
import { apiRequest } from './api'

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

it('allows a slow chat reply while ordinary reads keep their short timeout', async () => {
  vi.useFakeTimers()
  const fetcher = vi.fn((_path: string, options: RequestInit) => new Promise<Response>((resolve, reject) => {
    const timer = setTimeout(() => resolve(new Response('{"reply":"Late synthetic reply"}')), 15000)
    options.signal?.addEventListener('abort', () => { clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')) }, { once: true })
  }))
  vi.stubGlobal('fetch', fetcher)
  const signal = new AbortController().signal
  const chat = apiRequest('/api/v1/chat', signal, 'synthetic-session', { body: { message: 'Hello' }, timeoutMs: 95000 })
  const read = apiRequest('/api/v1/audit', signal, 'synthetic-session').catch(error => error)
  await vi.advanceTimersByTimeAsync(11000)
  expect(((await read) as Error).message).toContain('wyznaczonym czasie')
  await vi.advanceTimersByTimeAsync(4000)
  expect(await chat).toEqual({ reply: 'Late synthetic reply' })
  expect(fetcher).toHaveBeenCalledTimes(2)
})

it.each(['PATCH', 'PUT'] as const)('forwards explicit %s without retries or credentials in the URL', async method => {
  const fetcher = vi.fn(async (_path: string, _options?: RequestInit) => new Response('{"title":"Renamed"}'))
  vi.stubGlobal('fetch', fetcher)
  await apiRequest('/api/v1/chat/sessions/synthetic-id', new AbortController().signal, 'synthetic-session', {
    method, body: { title: 'Renamed' },
  })
  expect(fetcher).toHaveBeenCalledTimes(1)
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/chat/sessions/synthetic-id')
  expect(fetcher.mock.calls[0][1]).toMatchObject({ method, credentials: 'omit', redirect: 'error', cache: 'no-store', headers: { 'X-Jarvis-Key': 'synthetic-session' } })
})

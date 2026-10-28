import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../../api'

export interface ReadProps { credential: string; onUnauthorized: () => void }

// Callers choose when to read: mounting this hook performs no network request.
export function useRead<T>({ credential, onUnauthorized }: ReadProps) {
  const [value, setValue] = useState<T | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [loadedAt, setLoadedAt] = useState<number | null>(null)
  const controller = useRef<AbortController | null>(null)
  const epoch = useRef(0), mounted = useRef(true), expired = useRef(false)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; ++epoch.current; controller.current?.abort() }
  }, [])

  const clear = useCallback(() => {
    ++epoch.current; controller.current?.abort(); controller.current = null
    setValue(null); setError(null); setBusy(false); setLoadedAt(null)
  }, [])
  const run = useCallback(async (read: (credential: string, signal: AbortSignal) => Promise<T>) => {
    if (expired.current) return
    controller.current?.abort()
    const current = new AbortController(), id = ++epoch.current
    controller.current = current
    setValue(null); setError(null); setBusy(true); setLoadedAt(null)
    try {
      const result = await read(credential, current.signal)
      if (!mounted.current || current.signal.aborted || id !== epoch.current) return
      setValue(result); setLoadedAt(Date.now())
    } catch (failure) {
      if (!mounted.current || current.signal.aborted || id !== epoch.current) return
      if (failure instanceof ApiError && failure.status === 401) {
        expired.current = true; setValue(null); setLoadedAt(null); setError(null)
        unauthorized.current()
      } else setError(failure instanceof ApiError ? failure : new ApiError(null, 'response'))
    } finally {
      if (mounted.current && id === epoch.current) { setBusy(false); controller.current = null }
    }
  }, [credential])
  return { value, busy, error, loadedAt, run, clear }
}

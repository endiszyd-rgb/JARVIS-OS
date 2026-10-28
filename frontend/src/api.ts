import type { AuthSession, CoreStatus, Health, Identity, LoginInput, Readiness, Snapshot } from './types'

export class ApiError extends Error {
  status: number | null
  constructor(status: number | null, kind: 'http' | 'network' | 'response' | 'timeout' = 'http') {
    const message = kind === 'timeout' ? 'Serwer nie odpowiedział w wyznaczonym czasie. Spróbuj ponownie.'
      : kind === 'network' ? 'Nie można połączyć się z JARVIS OS. Sprawdź, czy serwer jest uruchomiony.'
        : kind === 'response' ? 'Nie udało się odczytać odpowiedzi serwera. Spróbuj ponownie.'
          : status === 401 ? 'Nieprawidłowe dane dostępu lub zakończona sesja.'
            : status === 403 ? 'To konto nie ma dostępu do tej funkcji.'
              : status === 429 ? 'Zbyt wiele żądań. Odczekaj chwilę i spróbuj ponownie.'
                : status === 503 ? 'JARVIS OS nie jest jeszcze gotowy. Sprawdź konfigurację serwera.'
                  : 'Nie udało się wykonać żądania. Spróbuj ponownie.'
    super(message); this.name = 'ApiError'; this.status = status
  }
}
function object(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === 'object' && !Array.isArray(value) }
function invalid(): never { throw new ApiError(null, 'response') }
function finite(value: unknown): value is number { return typeof value === 'number' && Number.isFinite(value) }

export interface ApiRequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  allowUnready?: boolean
  timeoutMs?: number
}
export async function apiRequest(path: string, signal: AbortSignal, credential?: string, options: ApiRequestOptions = {}): Promise<unknown> {
  const { body, allowUnready = false, timeoutMs = 10000 } = options
  if (!path.startsWith('/') || path.startsWith('//') || !Number.isFinite(timeoutMs) || timeoutMs < 1 || timeoutMs > 120000) return invalid()
  const controller = new AbortController()
  const abort = () => controller.abort()
  if (signal.aborted) abort()
  signal.addEventListener('abort', abort, { once: true })
  let timedOut = false
  const timer = window.setTimeout(() => { timedOut = true; controller.abort() }, timeoutMs)
  try {
    const headers: Record<string, string> = { Accept: 'application/json' }
    if (credential) headers['X-Jarvis-Key'] = credential
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    const response = await fetch(path, { method: options.method ?? (body === undefined ? 'GET' : 'POST'), headers,
      body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal,
      cache: 'no-store', credentials: 'omit', redirect: 'error', mode: 'same-origin' })
    if (!response.ok && !(allowUnready && response.status === 503)) throw new ApiError(response.status)
    try { return await response.json() } catch { return invalid() }
  } catch (error) {
    if (signal.aborted) throw new DOMException('Request aborted', 'AbortError')
    if (timedOut) throw new ApiError(null, 'timeout')
    if (error instanceof ApiError) throw error
    throw new ApiError(null, 'network')
  } finally { window.clearTimeout(timer); signal.removeEventListener('abort', abort) }
}
async function request(path: string, signal: AbortSignal, credential?: string, body?: unknown, allowUnready = false): Promise<unknown> {
  return apiRequest(path, signal, credential, { body, allowUnready })
}
function identity(value: unknown): Identity {
  if (!object(value) || typeof value.id !== 'string' || !['owner_key', 'session'].includes(String(value.kind))
    || !['owner', 'observer', 'home_reader', 'workshop_reader', 'automation_runner'].includes(String(value.role))
    || !Array.isArray(value.scopes) || !value.scopes.every(item => typeof item === 'string')
    || !(value.username === null || typeof value.username === 'string')
    || !(value.expires_at === null || finite(value.expires_at))) return invalid()
  return value as unknown as Identity
}
function status(value: unknown): CoreStatus {
  if (!object(value) || typeof value.mode !== 'string' || !object(value.settings) || !object(value.counts)
    || typeof value.settings.name !== 'string' || typeof value.settings.tone !== 'string'
    || !['demo', 'ollama', 'openai'].includes(String(value.settings.model)) || typeof value.live_devices !== 'boolean'
    || typeof value.autologika_audit !== 'string' || !Array.isArray(value.models) || !value.models.every(item => typeof item === 'string')) return invalid()
  for (const name of ['plugins', 'memory', 'audit', 'proposals', 'automations', 'notifications']) {
    const count = value.counts[name]
    if (!finite(count) || !Number.isSafeInteger(count) || count < 0) return invalid()
  }
  return value as unknown as CoreStatus
}
export async function connect(input: LoginInput, signal: AbortSignal): Promise<AuthSession> {
  let credential: string
  if (input.mode === 'account') {
    const result = await request('/api/v1/auth/login', signal, undefined, { username: input.username, password: input.password })
    if (!object(result) || typeof result.token !== 'string' || !result.token) return invalid()
    credential = result.token
  } else credential = input.key
  const principal = identity(await request('/api/v1/auth/me', signal, credential))
  if ((input.mode === 'account' && principal.kind !== 'session') || (input.mode === 'key' && principal.kind !== 'owner_key')) throw new ApiError(403)
  return { credential, identity: principal }
}
export async function readSnapshot(credential: string, signal: AbortSignal): Promise<Snapshot> {
  const [rawStatus, rawHealth, rawReady] = await Promise.all([
    request('/api/v1/status', signal, credential), request('/health', signal), request('/ready', signal, undefined, undefined, true),
  ])
  if (!object(rawHealth) || rawHealth.status !== 'ok' || typeof rawHealth.version !== 'string') return invalid()
  if (!object(rawReady) || !['ready', 'not_ready'].includes(String(rawReady.status)) || !object(rawReady.checks)
    || typeof rawReady.checks.owner_key !== 'boolean' || typeof rawReady.checks.database !== 'boolean'
    || typeof rawReady.optional_integrations_probed !== 'boolean') return invalid()
  return { status: status(rawStatus), health: rawHealth as unknown as Health, ready: rawReady as unknown as Readiness, loadedAt: Date.now() }
}
export async function endSession(session: AuthSession, signal: AbortSignal): Promise<void> {
  if (session.identity.kind === 'session') await request('/api/v1/auth/logout', signal, session.credential, {})
}

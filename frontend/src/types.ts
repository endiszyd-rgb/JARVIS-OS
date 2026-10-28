export type Role = 'owner' | 'observer' | 'home_reader' | 'workshop_reader' | 'automation_runner'
export interface Identity { id: string; kind: 'owner_key' | 'session'; role: Role; scopes: string[]; username: string | null; expires_at: number | null }
export interface AuthSession { credential: string; identity: Identity }
export interface CoreStatus {
  mode: string
  settings: { name: string; tone: string; model: 'demo' | 'ollama' | 'openai' }
  counts: { plugins: number; memory: number; audit: number; proposals: number; automations: number; notifications: number }
  live_devices: boolean; models: string[]; autologika_audit: string
}
export interface Health { status: 'ok'; version: string }
export interface Readiness { status: 'ready' | 'not_ready'; checks: { owner_key: boolean; database: boolean }; optional_integrations_probed: boolean }
export interface Snapshot { status: CoreStatus; health: Health; ready: Readiness; loadedAt: number }
export type LoginInput = { mode: 'account'; username: string; password: string } | { mode: 'key'; key: string }
export const roleLabels: Record<Role, string> = { owner: 'Właściciel', observer: 'Obserwator', home_reader: 'Odczyt domu', workshop_reader: 'Odczyt warsztatu', automation_runner: 'Harmonogram' }

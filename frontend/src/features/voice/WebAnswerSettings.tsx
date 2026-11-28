import { useEffect, useState } from 'react'
import { Globe, Save, Send } from 'lucide-react'
import { ApiError, apiRequest } from '../../api'
import { FieldLabel } from '../../components/HelpTip'

interface Config { enabled: boolean; provider: 'groq' | 'anthropic'; groq_api_key: string; groq_api_key_set?: boolean; groq_model: string; api_key: string; api_key_set?: boolean; model: string; max_searches: number }
interface Answer { speech: string; kind: string; sources: { title: string; url: string }[] }

const SECRET_MASK = '••••••••'
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const MODELS = [
  ['claude-sonnet-5-5', 'Claude Sonnet — dokładny (zalecany)'],
  ['claude-haiku-5-5', 'Claude Haiku — najszybszy i najtańszy'],
  ['claude-opus-5-5', 'Claude Opus — najdokładniejszy, najdroższy'],
] as const
const GROQ_MODELS = [
  ['groq/compound', 'Compound — kilka wyszukiwań, dokładniejszy (zalecany)'],
  ['groq/compound-mini', 'Compound Mini — jedno wyszukiwanie, szybszy'],
] as const

/** Answers to workshop questions from the internet (Claude + web search) for the Siri shortcut and the panel. */
export function WebAnswerSettings({ credential, onUnauthorized }: { credential: string; onUnauthorized: () => void }) {
  const [draft, setDraft] = useState<Config | null>(null)
  const [revision, setRevision] = useState(0)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<Answer | null>(null)
  const fail = (failure: unknown) => {
    if (failure instanceof ApiError && failure.status === 401) { onUnauthorized(); return }
    const detail = failure instanceof ApiError ? failure.detail ?? '' : ''
    setError(/groq_api_key/.test(detail) ? 'To nie wygląda na klucz Groq (zaczyna się od gsk_).' : /api_key/.test(detail) ? 'To nie wygląda na klucz Claude API (zaczyna się od sk-ant-).'
      : failure instanceof ApiError ? failure.message : 'Nie udało się. Spróbuj ponownie.')
  }
  useEffect(() => {
    const controller = new AbortController()
    apiRequest('/api/v1/config/web-answer', controller.signal, credential).then(value => {
      if (!object(value) || !object(value.config) || !Number.isSafeInteger(value.revision)) throw new ApiError(null, 'response')
      setDraft(value.config as unknown as Config); setRevision(value.revision as number)
    }).catch(failure => { if (!controller.signal.aborted) fail(failure) })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credential])
  if (!draft) return error ? <p className="form-error" role="alert">{error}</p> : null
  async function save() {
    if (!draft) return
    setBusy(true); setError(null); setNote(null)
    try {
      const { api_key_set: _claude, groq_api_key_set: _groq, ...config } = draft
      const value = await apiRequest('/api/v1/config/web-answer', new AbortController().signal, credential, { method: 'PUT', body: { revision, config } })
      if (!object(value) || !object(value.config) || !Number.isSafeInteger(value.revision)) throw new ApiError(null, 'response')
      setDraft(value.config as unknown as Config); setRevision(value.revision as number); setNote('Zapisano.')
    } catch (failure) { fail(failure) } finally { setBusy(false) }
  }
  async function ask() {
    setBusy(true); setError(null); setAnswer(null)
    try {
      const value = await apiRequest('/api/v1/voice/ask', new AbortController().signal, credential, { body: { text: question.trim() }, timeoutMs: 90000 })
      if (!object(value) || typeof value.speech !== 'string') throw new ApiError(null, 'response')
      setAnswer(value as unknown as Answer)
    } catch (failure) { fail(failure) } finally { setBusy(false) }
  }
  const storedKey = draft.api_key === SECRET_MASK
  const storedGroq = draft.groq_api_key === SECRET_MASK
  const groq = draft.provider === 'groq'
  return <div className="settings-block web-answer">
    <h2 className="panel-heading"><Globe aria-hidden="true" />Odpowiedzi z internetu</h2>
    <p className="panel-description">Pytania warsztatowe („moment dokręcania kół Golf 7”) JARVIS sprawdza w internecie i podaje źródło. To dane z internetu, nie z dokumentacji producenta — przy ważnych połączeniach sprawdź wartość.</p>
    <label className="voice-check"><input type="checkbox" checked={draft.enabled} disabled={busy} onChange={event => setDraft({ ...draft, enabled: event.target.checked })} />Odpowiadaj na pytania z internetu</label>
    <div className="gate-grid">
      <div className="form-field"><FieldLabel htmlFor="web-provider" help="Groq jest darmowy (bez karty, do 250 pytań dziennie) i sam szuka w internecie. Claude jest płatny za użycie, ale zwykle dokładniejszy przy danych technicznych. Możesz zapisać oba klucze i przełączać.">Dostawca AI</FieldLabel>
        <select id="web-provider" value={draft.provider} disabled={busy} onChange={event => setDraft({ ...draft, provider: event.target.value as Config['provider'] })}>
          <option value="groq">Groq — darmowy</option><option value="anthropic">Claude — płatny, dokładniejszy</option></select></div>
      {groq ? <>
        <div className="form-field"><FieldLabel htmlFor="web-groq-key" help={<><strong>console.groq.com</strong> → zaloguj się (Google lub e-mail, bez karty) → API Keys → Create API Key. Klucz zaczyna się od <code>gsk_</code>. Darmowy plan: po przekroczeniu limitu JARVIS powie, że limit się skończył — nic nie zapłacisz.</>}>Klucz Groq</FieldLabel>
          <input id="web-groq-key" type="password" autoComplete="new-password" value={storedGroq ? '' : draft.groq_api_key} disabled={busy}
            placeholder={storedGroq ? 'zapisany ✓ — wpisz nowy tylko, aby zmienić' : 'gsk_…'}
            onChange={event => setDraft({ ...draft, groq_api_key: event.target.value.trim() === '' && draft.groq_api_key_set ? SECRET_MASK : event.target.value.trim() })} /></div>
        <div className="form-field"><FieldLabel htmlFor="web-groq-model" help="Compound może wyszukać kilka razy i porównać źródła. Mini wyszukuje raz — odpowiada szybciej.">Model</FieldLabel>
          <select id="web-groq-model" value={draft.groq_model} disabled={busy} onChange={event => setDraft({ ...draft, groq_model: event.target.value })}>
            {GROQ_MODELS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
      </> : <>
        <div className="form-field"><FieldLabel htmlFor="web-key" help={<>Klucz z <strong>console.anthropic.com</strong> → API Keys → Create Key (zaczyna się od <code>sk-ant-</code>). Rozliczane za użycie: każde pytanie to wyszukiwanie + odpowiedź, zwykle kilka groszy. Ustaw tam limit miesięczny.</>}>Klucz Claude API</FieldLabel>
          <input id="web-key" type="password" autoComplete="new-password" value={storedKey ? '' : draft.api_key} disabled={busy}
            placeholder={storedKey ? 'zapisany ✓ — wpisz nowy tylko, aby zmienić' : 'sk-ant-…'}
            onChange={event => setDraft({ ...draft, api_key: event.target.value.trim() === '' && draft.api_key_set ? SECRET_MASK : event.target.value.trim() })} /></div>
        <div className="form-field"><FieldLabel htmlFor="web-model" help="Sonnet dobrze łączy dokładność i cenę. Haiku odpowiada szybciej i taniej, ale częściej się myli przy danych technicznych.">Model</FieldLabel>
          <select id="web-model" value={draft.model} disabled={busy} onChange={event => setDraft({ ...draft, model: event.target.value })}>
            {MODELS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            {!MODELS.some(([value]) => value === draft.model) && <option value={draft.model}>{draft.model}</option>}</select></div>
        <div className="form-field"><FieldLabel htmlFor="web-searches" help="Ile razy na jedno pytanie JARVIS może szukać w internecie. Więcej = dokładniej, ale wolniej i drożej.">Wyszukiwań na pytanie</FieldLabel>
          <input id="web-searches" type="number" min={1} max={5} value={draft.max_searches} disabled={busy} onChange={event => setDraft({ ...draft, max_searches: Number(event.target.value) })} /></div>
      </>}
    </div>
    <div className="gate-actions"><button type="button" className="button primary" disabled={busy} onClick={() => { void save() }}><Save aria-hidden="true" />Zapisz</button></div>
    {note && <p className="workshop-caption" role="status">{note}</p>}
    <div className="web-answer-test">
      <div className="form-field"><label htmlFor="web-question">Pytanie testowe</label>
        <input id="web-question" value={question} maxLength={500} disabled={busy} placeholder="np. moment dokręcania kół Skoda Octavia 3" onChange={event => setQuestion(event.target.value)}
          onKeyDown={event => { if (event.key === 'Enter' && question.trim()) void ask() }} /></div>
      <button type="button" className="button secondary" disabled={busy || !question.trim()} onClick={() => { void ask() }}><Send aria-hidden="true" />{busy ? 'Szukam…' : 'Zapytaj'}</button>
    </div>
    {answer && <div className={'web-answer-result' + (answer.kind === 'error' ? ' is-error' : '')} role="status"><p>{answer.speech}</p>
      {answer.sources.length > 0 && <ul>{answer.sources.map(item => <li key={item.url}><a href={item.url} target="_blank" rel="noreferrer noopener">{item.title}</a></li>)}</ul>}</div>}
    {error && <p className="form-error" role="alert">{error}</p>}
    <p className="workshop-caption">Pytania z telefonu bez rąk: <a href="#/account">Moje konto → Telefon i Siri</a>.</p>
  </div>
}

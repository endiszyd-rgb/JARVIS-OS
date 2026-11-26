import { useEffect, useRef, useState } from 'react'
import { AudioLines, Check, CircleAlert, Save } from 'lucide-react'
import { ApiError } from '../../api'
import { FieldLabel, HelpTip } from '../../components/HelpTip'
import { readVoiceConfig, saveVoiceConfig } from '../gate/api'
import type { VoiceConfig } from '../gate/api'

/** Voice settings (owner): engine, wake word, spoken replies. Listening itself stays in the Voice view. */
export function VoiceSettings({ credential, onUnauthorized }: { credential: string; onUnauthorized: () => void }) {
  const [draft, setDraft] = useState<VoiceConfig | null>(null)
  const [revision, setRevision] = useState(0)
  const [wyoming, setWyoming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized
  const fail = (failure: unknown) => { if (failure instanceof ApiError && failure.status === 401) unauthorized.current(); else setError(failure instanceof ApiError && failure.status === 409 ? 'Ustawienia zmieniły się w międzyczasie — odśwież stronę.' : failure instanceof ApiError ? failure.message : 'Nie udało się zapisać.') }
  useEffect(() => {
    const controller = new AbortController()
    readVoiceConfig(credential, controller.signal).then(value => { setDraft(value.config); setRevision(value.revision); setWyoming(value.wyomingAvailable) })
      .catch(failure => { if (!controller.signal.aborted) fail(failure) })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credential])
  async function save() {
    if (!draft || busy) return
    setBusy(true); setError(null); setNotice(null)
    try { const saved = await saveVoiceConfig(credential, new AbortController().signal, revision, draft); setDraft(saved.config); setRevision(saved.revision); setNotice('Ustawienia głosu zapisane.') }
    catch (failure) { fail(failure) } finally { setBusy(false) }
  }
  if (!draft) return error ? <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div> : <p role="status">Odczytywanie ustawień głosu…</p>
  return <div className="settings-block">
    <h2 className="panel-heading"><AudioLines aria-hidden="true" />Głos</h2>
    {error && <div className="app-error" role="alert"><CircleAlert aria-hidden="true" /><span>{error}</span></div>}
    {notice && <p className="gate-notice" role="status"><Check aria-hidden="true" />{notice}</p>}
    <div className="gate-grid">
      <div className="form-field"><FieldLabel htmlFor="voice-wake" help="Słowo, od którego zaczynasz polecenie przy ciągłym nasłuchu, np. „Jarvis, otwórz bramę”.">Słowo aktywujące</FieldLabel><input id="voice-wake" value={draft.wake_word} maxLength={30} disabled={busy} onChange={event => setDraft({ ...draft, wake_word: event.target.value })} /></div>
      <div className="form-field"><FieldLabel htmlFor="voice-lang" help="Język rozpoznawania mowy i czytania odpowiedzi.">Język</FieldLabel><select id="voice-lang" value={draft.language} disabled={busy} onChange={event => setDraft({ ...draft, language: event.target.value as VoiceConfig['language'] })}><option value="pl-PL">polski</option><option value="en-US">English</option></select></div>
    </div>
    <label className="voice-check"><input type="checkbox" checked={draft.speak_replies} disabled={busy} onChange={event => setDraft({ ...draft, speak_replies: event.target.checked })} />Czytaj odpowiedzi na głos</label>
    <details className="settings-more"><summary>Więcej opcji</summary>
      <div className="gate-grid"><div className="form-field"><FieldLabel htmlFor="voice-engine" help="Przeglądarka (Chrome/Edge) — działa od razu, bez instalacji. Wyoming — rozpoznawanie mowy na własnym komputerze, wymaga osobnej instalacji serwera Wyoming.">Silnik mowy</FieldLabel>
        <select id="voice-engine" value={draft.engine} disabled={busy} onChange={event => setDraft({ ...draft, engine: event.target.value as VoiceConfig['engine'] })}><option value="browser">Przeglądarka (zalecane)</option><option value="wyoming">Wyoming lokalnie{wyoming ? '' : ' — nieskonfigurowane'}</option></select></div></div>
      <label className="voice-check"><input type="checkbox" checked={draft.wake_listening} disabled={busy} onChange={event => setDraft({ ...draft, wake_listening: event.target.checked })} />Reaguj tylko po słowie aktywującym <HelpTip topic="słowo aktywujące" text="Zalecane przy ciągłym nasłuchu — JARVIS ignoruje rozmowy w warsztacie, dopóki nie usłyszy słowa aktywującego." /></label>
      <label className="voice-check"><input type="checkbox" checked={draft.send_to_model} disabled={busy} onChange={event => setDraft({ ...draft, send_to_model: event.target.checked })} />Odpowiadaj też na pytania spoza poleceń <HelpTip topic="pytania do AI" text="Zdania, które nie są poleceniem (brama, części, co dziś), trafią do modelu AI. Wymaga skonfigurowanego modelu w zakładce Asystent." /></label>
    </details>
    <div className="gate-actions"><button type="button" className="button primary" disabled={busy} onClick={() => { void save() }}><Save aria-hidden="true" />Zapisz</button></div>
  </div>
}

import { Cpu, RefreshCw } from 'lucide-react'
import { readIntegrations } from '../home/api'
import type { Integrations } from '../home/api'
import { useRead } from '../home/useRead'
import type { ReadProps } from '../home/useRead'
import './devices.css'

export function DevicesPanel(props: ReadProps) { return <DevicesWorkspace key={props.credential} {...props} /> }
function DevicesWorkspace(props: ReadProps) {
  const read = useRead<Integrations>(props)
  return <section className="panel devices-panel" aria-labelledby="devices-title" aria-busy={read.busy}>
    <div className="devices-toolbar"><div><h2 className="panel-heading" id="devices-title"><Cpu aria-hidden="true" />Urządzenia i możliwości</h2>
      <p className="panel-description">Lokalna konfiguracja dostępnych integracji. Ten odczyt nie łączy się z urządzeniami i nie potwierdza ich dostępności. Bramę konfigurujesz i obsługujesz w widoku <a href="#/gate">Brama</a>.</p></div>
      <button className="button secondary" type="button" disabled={read.busy} onClick={() => { void read.run(readIntegrations) }}><RefreshCw aria-hidden="true" />Odczytaj konfigurację</button></div>
    {read.busy && <p className="devices-caption" role="status">Odczytywanie lokalnej konfiguracji…</p>}
    {read.error && <div className="app-error" role="alert">{read.error.message}</div>}
    {read.value ? <>
      <p className="devices-caption">Źródło: konfiguracja JARVIS · Odczyt: {new Date(read.loadedAt!).toLocaleString('pl-PL')}.</p>
      <dl className="devices-capabilities">
        <div><dt>Home Assistant · odczyt</dt><dd><span className="badge">{read.value.home_readonly_enabled ? 'Włączony w konfiguracji' : 'Wyłączony w konfiguracji'}</span></dd></div>
        <div><dt>Twilio · webhook wiadomości</dt><dd><span className="badge">{read.value.twilio_webhook_enabled ? 'Włączony w konfiguracji' : 'Wyłączony w konfiguracji'}</span></dd></div>
        <div><dt>Brama · sterownik</dt><dd><span className={'badge ' + (read.value.physical_controls ? 'tone-good' : '')}>{read.value.physical_controls ? 'Sprzęt: ' + read.value.gate_driver : read.value.gate_driver === 'disabled' ? 'Wyłączona' : 'Symulator'}</span></dd></div>
        <div><dt>Wysyłka WhatsApp</dt><dd><span className="badge tone-warning">Niedostępna</span></dd></div>
        <div><dt>Połączenia WhatsApp</dt><dd><span className="badge tone-warning">Niedostępne</span></dd></div>
      </dl>
    </> : !read.busy && !read.error && <p className="devices-caption">Wybierz „Odczytaj konfigurację”, aby sprawdzić lokalne flagi możliwości.</p>}
    <div className="devices-links"><a className="link-button" href="#/gate">Brama i sterownik</a><a className="link-button" href="#/voice">Komendy głosowe</a><a className="link-button" href="#/home">Odczyt czujników Home Assistant</a><a className="link-button" href="#/plugins">Pluginy i dozwolone narzędzia</a><a className="link-button" href="/">Poprzedni panel i laboratoria</a></div>
    <p className="devices-caption">MQTT i ESP32 nie mają jeszcze katalogu urządzeń. Brama ma własne API i sterowniki (HTTP, Tuya, Home Assistant, symulator).</p>
  </section>
}

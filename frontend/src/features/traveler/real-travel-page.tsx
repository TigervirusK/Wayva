import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, ExternalLink, LockKeyhole, Plane, RefreshCw, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ProfileGate } from '@/features/trips/trips-pages'
import { travelerApi, type Assistance, type RealCapabilities } from './traveler-api'
import { usePrivateTraveler } from './use-private-traveler'
import { VaultUnlock } from './traveler-settings'
import { RescueModeSwitch } from './rescue-mode-switch'
import './traveler.css'

export function RealTravelPage() {
  const vault = usePrivateTraveler()
  const [capabilities, setCapabilities] = useState<RealCapabilities | null>(null)
  const [capabilityError, setCapabilityError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const [selected, setSelected] = useState('')
  const [assistance, setAssistance] = useState<Assistance | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const identity = `${vault.profile?.id}:${vault.envelope?.revision}:${selected}`
  const current = useRef(identity)
  current.current = identity
  const loaded = useRef<string | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    setCapabilities(null); setCapabilityError(null)
    travelerApi.capabilities(controller.signal).then(setCapabilities).catch(failure => { if (!controller.signal.aborted) setCapabilityError(failure instanceof Error ? failure.message : 'Provider capabilities could not be checked.') })
    return () => controller.abort()
  }, [attempt])
  useEffect(() => { current.current = identity; setAssistance(null); setError(null); setBusy(false); return () => { current.current = '' } }, [identity])
  const visibleAssistance = vault.envelope && loaded.current === identity ? assistance : null
  async function prepare() {
    if (!vault.token || !vault.envelope || !selected || busy) return
    setBusy(true); setError(null)
    try {
      const result = await travelerApi.assistance(vault.token, selected)
      if (current.current === identity) { loaded.current = identity; setAssistance(result) }
    } catch (failure) { if (current.current === identity) setError(failure instanceof Error ? failure.message : 'The handoff could not be prepared.') }
    finally { if (current.current === identity) setBusy(false) }
  }
  return <div className="real-travel-page"><RescueModeSwitch mode="real" />
    <div className="workspace-heading"><p className="eyebrow">REAL TRAVEL / ASSISTED HANDOFF</p><h1>Keep your details together.<br /><span className="serif-word">Take the next step clearly.</span></h1><p>Bring tickets you bought elsewhere. Store their details privately, then contact the airline or original seller through the appropriate channel.</p></div>
    {capabilityError && <div className="trips-error" role="alert"><p>{capabilityError}</p><button onClick={() => setAttempt(value => value + 1)}><RefreshCw size={14} /> Retry capability check</button></div>}
    {capabilities ? <><section className="real-provider-status" role="status"><ShieldCheck size={26} /><div><h2>Assisted only · live providers are not connected</h2><p>{capabilities.message}</p><p>Opening an airline link does not submit your details or book anything.</p></div></section>
      <details className="real-stage-details"><summary>See the live-recovery stages and what is still required</summary><ol className="real-stages">{capabilities.stages.map((stage, index) => <li key={stage.id}><span>{index + 1}</span><div><strong>{stage.label}</strong><p>{stage.reason}</p></div><small>{stage.status === 'not_connected' ? 'Not connected' : 'Unavailable'}</small></li>)}</ol></details></> : !capabilityError && <p className="trips-loading" role="status">Checking connected capabilities…</p>}
    <section className="traveler-settings real-assistance"><div className="private-heading"><div><p className="eyebrow">YOUR EXISTING TICKET</p><h2>Prepare an airline handoff.</h2><p>Details entered by you remain unverified. Your original seller may need to handle changes even if you can view the ticket on the airline’s website.</p></div><Plane size={27} strokeWidth={1.4} /></div>
      <ProfileGate>{vault.error && <div className="trips-error" role="alert"><p>{vault.error}</p><button disabled={vault.busy} onClick={vault.reload}>Reload private details</button></div>}
      {vault.loading ? <p className="trips-loading" role="status">Checking your private vault…</p> : vault.envelope ? <><div className="private-session"><span>Private details unlocked · entries are not provider-verified</span><Button size="sm" variant="outline" disabled={vault.busy || busy} onClick={() => void vault.lock()}><LockKeyhole size={14} /> Lock private details</Button></div>
        {vault.envelope.data.bookings.length ? <form className="trips-form" onSubmit={event => { event.preventDefault(); void prepare() }}><label htmlFor="real-flight-select">Choose saved flight details<select id="real-flight-select" aria-label="Choose saved flight details" value={selected} disabled={busy} required onChange={event => setSelected(event.target.value)}><option value="">Choose a flight</option>{vault.envelope.data.bookings.map(booking => <option key={booking.id} value={booking.id}>{booking.flight_number} · {booking.origin} → {booking.destination} · {booking.departure_date}</option>)}</select></label><Button type="submit" disabled={busy || !selected}>{busy ? 'Preparing handoff…' : 'Prepare manual handoff'}<ArrowRight size={15} /></Button></form> : <p className="private-help">No existing flight details are saved yet. Add them in Settings, then return here.</p>}
        <Link className="text-link private-settings-link" to="/settings#private-traveler">Add or edit private flight details <ArrowRight size={14} /></Link>
      </> : vault.status?.exists ? <VaultUnlock exists busy={vault.busy} authenticate={vault.authenticate} /> : vault.status && <div className="private-help"><p>Start in Settings to create a password-encrypted traveler vault and add tickets you already bought.</p><Button asChild variant="outline"><Link to="/settings#private-traveler">Set up private traveler details <LockKeyhole size={15} /></Link></Button></div>}
      {error && <div className="trips-error" role="alert">{error}</div>}
      {visibleAssistance && <article className="real-handoff"><span className="real-unverified-label">USER-ENTERED · NOT VERIFIED · NOT BOOKED BY WAYVA</span><h3>{visibleAssistance.airline_name}</h3>{visibleAssistance.contact_original_seller && <p className="real-seller-note">Your recorded original seller is <strong>{visibleAssistance.original_seller}</strong>. Contact them for changes; an airline page may only let you view this reservation.</p>}<ol>{visibleAssistance.steps.map(step => <li key={step}>{step}</li>)}</ol>
        {visibleAssistance.official_airline_url && <Button asChild><a href={visibleAssistance.official_airline_url} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">Open official airline website <ExternalLink size={15} /></a></Button>}
        <p className="private-help">{visibleAssistance.disclosure}</p><p className="private-help">No ticket details are automatically copied into the demo or applied to your itinerary. Automatic repair requires a verified replacement and a connected workflow.</p>
      </article>}
      </ProfileGate>
    </section>
  </div>
}

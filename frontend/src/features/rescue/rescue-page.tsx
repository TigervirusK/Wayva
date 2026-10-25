import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUpRight, Check, CheckCircle2, Clock3, History, Hotel, MapPin, Plane, RefreshCw, ShieldCheck, TriangleAlert, Wallet, Car, Footprints } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useBuddy } from '@/components/buddy/floating-buddy'
import { useTrips } from '@/features/trips'
import { ProfileGate } from '@/features/trips/trips-pages'
import { formatMoney } from '@/features/trips/trips-api'
import { rescueApi, type RecoveryPlan, type RescueState } from './rescue-api'
import './rescue.css'
import { RescueModeSwitch } from '@/features/traveler/rescue-mode-switch'

const icons = { flight: Plane, pickup: Car, hotel: Hotel, tour: Footprints }
const strategyNames = { fastest: 'Fastest recovery', cheapest: 'Cheapest recovery', balanced: 'Balanced recovery' }
const when = (value: string) => new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Tokyo', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value))
const message = (failure: unknown) => failure instanceof Error ? failure.message : 'The request could not be completed. Refresh to check your saved state.'

function ReservationChain({ state }: { state: RescueState }) {
  return <section className="rescue-section" aria-labelledby="chain-title"><div className="rescue-section-heading"><div><p className="eyebrow">01 / THE CHAIN REACTION</p><h2 id="chain-title">One change touches the whole journey.</h2></div><span className="rescue-time-note">All schedule times: Tokyo (JST)</span></div>
    <ol className="rescue-chain">{state.reservations.map((reservation, index) => {
      const Icon = icons[reservation.kind]
      const edge = state.dependencies.find(edge => edge.target_id === reservation.id)
      return <li key={reservation.id} className={`rescue-node rescue-node-${reservation.status}`}>
        {index > 0 && <span className="rescue-connector" aria-hidden="true"><ArrowRight size={18} /></span>}
        <div className="rescue-node-top"><span className="rescue-node-icon"><Icon size={22} strokeWidth={1.5} /></span><span className={`rescue-status rescue-status-${reservation.status}`}>{reservation.status === 'at_risk' ? 'At risk' : reservation.status === 'cancelled' ? 'Cancelled' : 'Confirmed · demo'}</span></div>
        <h3>{reservation.title.replace('Mock ', '').replace('mock ', '')}</h3><p><MapPin size={12} />{reservation.location}</p>
        <time dateTime={reservation.kind === 'flight' ? reservation.end_at : reservation.start_at}>{reservation.kind === 'flight' ? 'Arrives ' : ''}{when(reservation.kind === 'flight' ? reservation.end_at : reservation.start_at)}</time>
        <p className="rescue-dependency">{edge ? edge.reason : 'The starting point: a fictional connection from Chicago to Tokyo.'}</p>
        <small>{reservation.booking_reference} · simulated</small>
      </li>
    })}</ol>
    <p className="rescue-graph-note"><ArrowDown size={15} /> Arrows show saved dependencies. “At risk” means it needs review; a recovery may preserve the original time.</p>
  </section>
}

function PlanCard({ plan, selected, currency, onSelect, disabled }: { plan: RecoveryPlan; selected: boolean; currency: string; onSelect: () => void; disabled: boolean }) {
  const Icon = plan.strategy === 'fastest' ? Clock3 : plan.strategy === 'cheapest' ? Wallet : ShieldCheck
  return <article className={`rescue-option ${selected ? 'rescue-option-selected' : ''} ${!plan.available ? 'rescue-option-blocked' : ''}`}>
    <div className="rescue-option-label"><Icon size={18} /><span>{strategyNames[plan.strategy]}</span>{plan.strategy === 'balanced' && <span className="rescue-middle-label">MIDDLE GROUND</span>}</div>
    <h3>{plan.title}</h3><p className="rescue-option-explanation">{plan.explanation}</p>
    <div className="rescue-option-price"><strong>+{formatMoney(plan.extra_cost, currency)}</strong><span>extra for this simulated repair</span></div>
    <dl><div><dt>Tokyo arrival</dt><dd>{when(plan.arrival_at)}</dd></div><div><dt>Arrival delay</dt><dd>{plan.delay_hours} hours</dd></div><div><dt>Schedule changes</dt><dd>{plan.schedule_changes}</dd></div><div><dt>Walking tour</dt><dd>{plan.tour_moved ? 'Moved to allow rest' : 'Original time protected'}</dd></div></dl>
    {!plan.available && <p className="rescue-option-warning"><TriangleAlert size={15} />{plan.blocked_reason}</p>}
    {plan.status === 'failed' && <p className="rescue-option-warning" role="status">{plan.error}</p>}
    <Button variant={selected ? 'default' : 'outline'} disabled={disabled || !plan.available || plan.status !== 'pending'} aria-pressed={selected} onClick={onSelect}>{plan.status === 'failed' ? 'Attempt failed' : plan.status === 'applied' ? 'Repair applied' : plan.status === 'stale' ? 'Out of date' : selected ? 'Selected for review' : 'Review this option'}{selected ? <Check size={15} /> : <ArrowRight size={15} />}</Button>
  </article>
}

function Review({ plan, state, busy, apply, cancel }: { plan: RecoveryPlan; state: RescueState; busy: boolean; apply: (failure: boolean) => void; cancel: () => void }) {
  const [approved, setApproved] = useState(false)
  const [failure, setFailure] = useState(false)
  return <section className="rescue-review" aria-labelledby="review-title"><div className="rescue-section-heading"><div><p className="eyebrow">03 / YOUR CALL</p><h2 id="review-title">Here’s exactly what will change.</h2></div><ShieldCheck size={30} strokeWidth={1.3} /></div>
    <div className="rescue-review-lines">{plan.actions.map(action => <div className="rescue-review-line" key={action.reservation_id}><div><strong>{action.title}</strong><span>{action.action.replaceAll('_', ' ')}</span></div><div><span className="rescue-before">{when(action.kind === 'flight' ? action.before_end_at : action.before_start_at)}</span><ArrowRight size={14} /><strong>{when(action.kind === 'flight' ? action.end_at : action.start_at)}</strong></div><span>+{formatMoney(action.extra_cost, state.currency)}</span></div>)}</div>
    <div className="rescue-review-total"><span>Total additional estimate</span><strong>+{formatMoney(plan.extra_cost, state.currency)}</strong></div>
    <p className="rescue-review-note">{plan.tradeoffs.join(' ')} Approval updates these simulated reservations and their linked saved itinerary items. It does not book or change a real flight, hotel, pickup, or tour.</p>
    <label className="rescue-checkbox"><input type="checkbox" checked={approved} disabled={busy} onChange={event => setApproved(event.target.checked)} /><span>I approve these simulated changes and the additional estimate.</span></label>
    <details className="rescue-failure-test"><summary>Try the provider-failure demonstration</summary><label className="rescue-checkbox"><input type="checkbox" checked={failure} disabled={busy} onChange={event => setFailure(event.target.checked)} /><span>Make the mock pickup provider fail. The repair will be rolled back and logged; you can then choose another option.</span></label></details>
    <div className="rescue-review-actions"><Button disabled={busy || !approved} onClick={() => apply(failure)}>{busy ? 'Saving simulated repair…' : 'Approve & apply simulated repair'}<CheckCircle2 size={16} /></Button><Button variant="ghost" disabled={busy} onClick={cancel}>Back to options</Button></div>
  </section>
}

function AuditTrail({ state }: { state: RescueState }) {
  return <section className="rescue-section rescue-history" aria-labelledby="history-title"><div className="rescue-section-heading"><div><p className="eyebrow">THE RECEIPTS</p><h2 id="history-title">Every change, accounted for.</h2></div><History size={23} strokeWidth={1.4} /></div><ol>{[...state.audit].reverse().map(log => <li key={log.id} className={log.result === 'failed' ? 'rescue-audit-failed' : ''}><span className="rescue-audit-icon">{log.result === 'failed' ? <TriangleAlert size={15} /> : <Check size={15} />}</span><div><strong>{log.action.replaceAll('_', ' ')}</strong><p>{log.details.message}</p><time dateTime={log.created_at}>{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(log.created_at))} · your device time</time></div></li>)}</ol></section>
}

export function RescuePage() {
  const { tripId } = useParams<{ tripId: string }>()
  const { token, profile, selectTrip, loadTrip, refreshTrips } = useTrips()
  const navigate = useNavigate()
  const { openBuddy } = useBuddy()
  const [state, setState] = useState<RescueState | null>(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const lock = useRef(false)
  const generation = useRef(0)
  const loadedIdentity = useRef<string | null>(null)
  const identity = `${profile?.id}:${tripId ?? 'intro'}`
  const identityRef = useRef<string | null>(identity)
  identityRef.current = identity
  const reviewRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    generation.current += 1
    identityRef.current = identity
    setState(null); setSelected(null); setError(null); setBusy(false); lock.current = false
    if (!token || !profile || !tripId) { setLoading(false); return () => { identityRef.current = null } }
    const controller = new AbortController()
    setLoading(true)
    rescueApi.get(token, tripId, controller.signal).then(result => { if (!controller.signal.aborted) { loadedIdentity.current = identity; setState(result) } })
      .catch(failure => { if (!controller.signal.aborted) setError(message(failure)) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => { controller.abort(); identityRef.current = null }
  }, [token, profile?.id, tripId, attempt, identity])
  useEffect(() => { if (selected) reviewRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }) }, [selected])

  async function create(fresh = false) {
    if (!token || lock.current) return
    const requestGeneration = generation.current
    const isCurrent = () => identityRef.current === identity && generation.current === requestGeneration
    lock.current = true; setBusy(true); setError(null)
    try {
      const result = await rescueApi.create(token, fresh)
      if (!isCurrent()) return
      selectTrip(result.trip_id); void refreshTrips()
      navigate(`/trips/${result.trip_id}/rescue`)
    } catch (failure) { if (isCurrent()) setError(message(failure)) }
    finally { if (isCurrent()) { lock.current = false; setBusy(false) } }
  }

  async function run(operation: () => Promise<RescueState>) {
    if (lock.current || !tripId) return
    const requestGeneration = generation.current
    const isCurrent = () => identityRef.current === identity && generation.current === requestGeneration
    lock.current = true; setBusy(true); setError(null)
    try {
      const result = await operation()
      if (!isCurrent()) return
      loadedIdentity.current = identity
      setState(result); setSelected(null)
      void loadTrip(tripId).catch(() => undefined); void refreshTrips()
    } catch (failure) {
      if (isCurrent()) {
        setError(message(failure)); setSelected(null)
        // Re-read saved state after a refused/stale action, without retrying writes.
        if (token) { try { const result = await rescueApi.get(token, tripId); if (isCurrent()) { loadedIdentity.current = identity; setState(result) } } catch { /* Keep the actionable original error. */ } }
      }
    } finally { if (isCurrent()) { lock.current = false; setBusy(false) } }
  }
  const current = state?.trip_id === tripId && loadedIdentity.current === identity ? state : null
  const resolved = current?.disruption?.status === 'resolved'
  const latestPlans = current?.plans.filter(plan => plan.status !== 'stale') ?? []
  const plan = latestPlans.find(plan => plan.id === selected && plan.status === 'pending' && plan.available)
  const order = { fastest: 0, balanced: 1, cheapest: 2 }
  const sortedPlans = [...latestPlans].sort((a, b) => order[a.strategy] - order[b.strategy])
  const regenerate = current && current.disruption?.status === 'open' && latestPlans.length === 0
  return <div className="rescue-page">
    <RescueModeSwitch mode="demo" />
    {tripId && <Link className="trips-back-link" to={`/trips/${tripId}`}><ArrowLeft size={14} /> Back to trip itinerary</Link>}
    <div className="rescue-hero"><div><span className="rescue-demo-label"><ShieldCheck size={14} /> DOMINO RESCUE · SIMULATED BOOKINGS</span><h1>One setback.<br /><span>A way forward.</span></h1><p>A cancelled flight shouldn’t unravel the whole trip. See the chain reaction, weigh the tradeoffs, and choose your next move.</p></div><div className="rescue-hero-mark" aria-hidden="true"><span /><ShieldCheck size={65} strokeWidth={1} /><span className="rescue-mark-line" /><Plane size={25} strokeWidth={1.2} /></div></div>
    <ProfileGate>
      {error && <div className="trips-error" role="alert"><p>{error}</p>{tripId && <button disabled={busy} onClick={() => setAttempt(value => value + 1)}><RefreshCw size={14} /> Refresh saved state</button>}</div>}
      {loading && <p className="trips-loading" role="status"><RefreshCw size={16} />Opening the saved recovery workspace…</p>}
      {(!tripId || (current && !current.scenario_ready)) && <section className="rescue-intro"><p className="eyebrow">A WORKING HACKATHON DEMONSTRATION</p><h2>Try a trip that can bounce back.</h2><p>Create a separate fictional Tokyo trip with a Chicago connection, airport pickup, hotel check-in, and walking tour. Cancel the connection to see what happens next.</p><ol><li><span>01</span><strong>See what’s at risk</strong><p>Follow the saved dependencies beyond the cancelled flight.</p></li><li><span>02</span><strong>Compare real tradeoffs</strong><p>Three fictional flights, checked against rest time, itinerary conflicts, and budget.</p></li><li><span>03</span><strong>Approve the repair</strong><p>Save mock booking changes, update the itinerary, and inspect the activity log.</p></li></ol><Button disabled={busy} onClick={() => void create()}>{busy ? 'Opening demo…' : 'Open rescue demo'}<ArrowUpRight size={16} /></Button><p className="rescue-small-print">This button creates or reopens a separate demo trip in your local profile. Existing trips are preserved. No real reservations or purchases.</p></section>}
      {current?.scenario_ready && <>
        <div className="rescue-trip-caption"><span><MapPin size={15} />{current.trip_name}</span><button className="text-link" onClick={() => { selectTrip(tripId!); openBuddy('Explain the current recovery status and tradeoffs for my selected simulated trip. Do not change anything.', 'rescue') }}>Explain it with Way <ArrowUpRight size={14} /></button><Link to={`/trips/${tripId}`} className="text-link">Saved itinerary <ArrowUpRight size={14} /></Link></div>
        <div className={`rescue-situation ${resolved ? 'rescue-situation-resolved' : current.disruption ? 'rescue-situation-alert' : ''}`} role="status">{resolved ? <CheckCircle2 size={27} /> : current.disruption ? <TriangleAlert size={27} /> : <Plane size={27} />}<div><h2>{resolved ? 'Your simulated trip is back on track.' : current.disruption ? 'Connection cancelled. Three plans need attention.' : 'Everything is connected. See it in action.'}</h2><p>{resolved ? 'The approved changes are saved in the reservations and itinerary. The activity log below shows what happened.' : current.disruption ? 'The pickup, check-in, and tour depend on this arrival. Compare a coordinated repair before changing them.' : 'Simulate the cancellation of your fictional Chicago–Tokyo flight. This changes only this demo’s saved flight and risk status.'}</p></div>{!current.disruption && <Button disabled={busy} onClick={() => void run(() => rescueApi.simulate(token!, tripId!))}>{busy ? 'Saving cancellation…' : 'Simulate flight cancellation'}<ArrowRight size={15} /></Button>}</div>
        <ReservationChain state={current} />
        {current.disruption?.status === 'open' && <section className="rescue-section" aria-labelledby="options-title"><div className="rescue-section-heading"><div><p className="eyebrow">02 / YOUR WAYS FORWARD</p><h2 id="options-title">Different priorities. Clear choices.</h2><p className="rescue-section-copy">Ranked by arrival, additional cost, and changes to the rest of the trip. Fictional inventory, with deterministic schedule and budget checks.</p></div>{(latestPlans.length === 0) && <Button disabled={busy} onClick={() => void run(() => rescueApi.options(token!, tripId!))}>{busy ? 'Checking options…' : regenerate && current.plans.length ? 'Recalculate recovery options' : 'Compare recovery options'}<ArrowRight size={15} /></Button>}</div>
          {sortedPlans.length > 0 && <div className="rescue-options">{sortedPlans.map(item => <PlanCard key={item.id} plan={item} selected={selected === item.id} currency={current.currency} onSelect={() => setSelected(item.id)} disabled={busy} />)}</div>}
          {latestPlans.length > 0 && latestPlans.every(item => item.status === 'failed') && <p className="rescue-option-warning">All attempted options failed. Create a fresh demo to run the demonstration again.</p>}
        </section>}
        <div ref={reviewRef}>{plan && <Review key={plan.id} plan={plan} state={current} busy={busy} cancel={() => setSelected(null)} apply={failure => void run(() => rescueApi.approve(token!, tripId!, plan.id, failure))} />}</div>
        <AuditTrail state={current} />
        {(resolved || latestPlans.some(item => item.status === 'failed')) && <div className="rescue-repeat"><div><h3>Want to demonstrate another outcome?</h3><p>A fresh demo adds a new fictional trip and keeps this one’s history.</p></div><Button variant="outline" disabled={busy} onClick={() => void create(true)}>Create fresh demo <RefreshCw size={15} /></Button></div>}
      </>}
    </ProfileGate>
  </div>
}

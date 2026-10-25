import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowUpRight, CalendarDays, Check, Clock3, Compass, MapPin, Pencil, Plus, RefreshCw, Trash2, UserRound, Users, Wallet, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTrips } from './trips-provider'
import { formatDate, formatMoney, localToday, type Currency, type ItemInput, type ItineraryItem, type TripDetail, type TripInput, type TripSummary } from './trips-api'
import './trips.css'
import { AccountAccess } from '@/features/accounts/account-page'

const currencies: Currency[] = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'INR']
const errorMessage = (failure: unknown) => failure instanceof Error ? failure.message : 'Your changes could not be saved. Please try again.'

function ErrorNotice({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="trips-error" role="alert"><p>{message}</p>{retry && <button type="button" onClick={retry}><RefreshCw size={13} /> Try again</button>}</div>
}

function LoadingNotice({ children }: { children: ReactNode }) {
  return <p className="trips-loading" role="status"><RefreshCw size={15} />{children}</p>
}

export function ProfileGate({ children }: { children: ReactNode }) {
  const { profile, profileLoading, profileError, retryProfile } = useTrips()
  if (profileLoading) return <LoadingNotice>Opening your account…</LoadingNotice>
  if (profile) return children
  if (profileError) return <ErrorNotice message={profileError} retry={retryProfile} />
  return <AccountAccess />
}

function StorageNotice() {
  const { storageAvailable, accountUsername } = useTrips()
  return !storageAvailable ? <div className="trips-recovery" role="status">{accountUsername ? 'This browser cannot remember your selected trip. Your account records stay on the server; sign in again if your session ends.' : 'This browser cannot save the local profile token. Your trips stay on the backend, but this unlinked profile may lose access after refresh. Connect it to an account to reopen it with a login.'}</div> : null
}

function tripValues(trip?: TripDetail): TripInput {
  return trip ? { name: trip.name, destination: trip.destination, departure_location: trip.departure_location, start_date: trip.start_date, end_date: trip.end_date, travelers: trip.travelers, budget: trip.budget, currency: trip.currency, status: trip.status }
    : { name: '', destination: '', departure_location: '', start_date: '', end_date: '', travelers: 1, budget: '0.00', currency: 'USD', status: 'planned' }
}

function validateMoney(value: string): boolean {
  return /^\d+(\.\d{1,2})?$/.test(value) && Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 10000000
}

function TripForm({ trip, onSaved, onCancel }: { trip?: TripDetail; onSaved: (trip: TripDetail) => void; onCancel: () => void }) {
  const { saveTrip } = useTrips()
  const [form, setForm] = useState<TripInput>(() => tripValues(trip))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const prefix = useId()
  const currencyLocked = !!trip?.itinerary.length
  const setField = <K extends keyof TripInput,>(key: K, value: TripInput[K]) => setForm((previous) => ({ ...previous, [key]: value }))
  return <section className="trips-form-panel" aria-labelledby={`${prefix}-heading`}><div className="trips-panel-heading"><div><p className="trips-kicker">THE NEXT CHAPTER</p><h2 id={`${prefix}-heading`}>{trip ? 'Edit your trip' : 'Make room for a new adventure.'}</h2></div><button type="button" className="trips-icon-button" aria-label="Cancel trip form" disabled={busy} onClick={onCancel}><X size={19} /></button></div>
    <form className="trips-form" aria-busy={busy} onSubmit={async (event) => {
      event.preventDefault()
      if (busy) return
      if (!form.name.trim() || !form.destination.trim()) { setError('Give your trip a name and destination.'); return }
      const duration = (Date.parse(`${form.end_date}T12:00:00Z`) - Date.parse(`${form.start_date}T12:00:00Z`)) / 86400000 + 1
      if (!Number.isFinite(duration) || duration < 1 || duration > 366) { setError('Choose an end date on or after the start date, with no more than 366 days in the trip.'); return }
      if (!Number.isInteger(form.travelers) || form.travelers < 1 || form.travelers > 50) { setError('Choose between 1 and 50 travelers.'); return }
      if (!validateMoney(form.budget)) { setError('Enter a budget from 0 to 10,000,000, with no more than two decimal places.'); return }
      setBusy(true); setError(null)
      try {
        const result = await saveTrip(trip?.id ?? null, { ...form, name: form.name.trim(), destination: form.destination.trim(), departure_location: form.departure_location.trim(), budget: Number(form.budget).toFixed(2) })
        onSaved(result)
      } catch (failure) { setError(errorMessage(failure)) } finally { setBusy(false) }
    }}>
      <fieldset disabled={busy}><legend className="trips-sr-only">Trip details</legend><div className="trips-form-grid">
        <label className="trips-wide" htmlFor={`${prefix}-name`}>Trip name<input id={`${prefix}-name`} value={form.name} onChange={(event) => setField('name', event.target.value)} required maxLength={120} placeholder="Give this journey a name" /></label>
        <label htmlFor={`${prefix}-destination`}>Destination<input id={`${prefix}-destination`} value={form.destination} onChange={(event) => setField('destination', event.target.value)} required maxLength={120} placeholder="City, region, or country" /></label>
        <label htmlFor={`${prefix}-departure`}>Departure location <span className="trips-optional">(optional)</span><input id={`${prefix}-departure`} value={form.departure_location} onChange={(event) => setField('departure_location', event.target.value)} maxLength={120} placeholder="Where you’re starting" /></label>
        <label htmlFor={`${prefix}-start`}>Start date<input id={`${prefix}-start`} type="date" value={form.start_date} onChange={(event) => setField('start_date', event.target.value)} required /></label>
        <label htmlFor={`${prefix}-end`}>End date<input id={`${prefix}-end`} type="date" value={form.end_date} min={form.start_date || undefined} onChange={(event) => setField('end_date', event.target.value)} required /></label>
        <label htmlFor={`${prefix}-travelers`}>Travelers<input id={`${prefix}-travelers`} type="number" min={1} max={50} step={1} value={form.travelers} onChange={(event) => setField('travelers', Number(event.target.value))} required /></label>
        <label htmlFor={`${prefix}-budget`}>Budget<input id={`${prefix}-budget`} inputMode="decimal" value={form.budget} onChange={(event) => setField('budget', event.target.value)} required maxLength={12} aria-describedby={`${prefix}-money-help`} /></label>
        <label htmlFor={`${prefix}-currency`}>Currency<select id={`${prefix}-currency`} value={form.currency} disabled={currencyLocked || busy} onChange={(event) => setField('currency', event.target.value as Currency)}>{currencies.map((currency) => <option key={currency} value={currency}>{currency}</option>)}</select></label>
        <label htmlFor={`${prefix}-status`}>Trip status<select id={`${prefix}-status`} value={form.status} onChange={(event) => setField('status', event.target.value as TripInput['status'])}><option value="planned">Planned</option><option value="active">Active</option><option value="completed">Completed</option></select></label>
      </div></fieldset>
      <p id={`${prefix}-money-help`} className="trips-form-note">Budget is the total for the whole trip. Use up to two decimal places.{currencyLocked && ' Currency stays fixed while itinerary items exist.'}{trip && ' Date changes must keep every saved activity inside the trip.'}</p>
      {error && <ErrorNotice message={error} />}<div className="trips-form-actions"><Button type="submit" disabled={busy}>{busy ? 'Saving trip…' : trip ? 'Save changes' : 'Save trip'}<Check size={15} /></Button><Button type="button" variant="ghost" disabled={busy} onClick={onCancel}>Cancel</Button></div>
    </form>
  </section>
}

function TripCard({ trip }: { trip: TripSummary }) {
  const { selectedTripId, selectTrip } = useTrips()
  const selected = selectedTripId === trip.id
  return <article className={`saved-trip-card ${selected ? 'saved-trip-selected' : ''}`}><div className="saved-trip-top"><span className="trips-round-icon"><Compass size={24} strokeWidth={1.3} /></span><span className={`trips-status trips-status-${trip.status}`}>{trip.status}</span></div><h2><Link to={`/trips/${trip.id}`} onClick={() => selectTrip(trip.id)}>{trip.name}</Link></h2><p className="saved-trip-destination"><MapPin size={13} />{trip.destination}</p><dl className="saved-trip-facts"><div><dt><CalendarDays size={14} /><span className="trips-sr-only">Dates</span></dt><dd>{formatDate(trip.start_date)} — {formatDate(trip.end_date)}</dd></div><div><dt><Users size={14} /><span className="trips-sr-only">Travelers</span></dt><dd>{trip.travelers} {trip.travelers === 1 ? 'traveler' : 'travelers'}<span> · {trip.item_count} {trip.item_count === 1 ? 'activity' : 'activities'}</span></dd></div><div><dt><Wallet size={14} /><span className="trips-sr-only">Budget</span></dt><dd>{formatMoney(trip.budget, trip.currency)}<span> total budget</span></dd></div></dl><div className="saved-trip-actions"><Link className="trips-text-link" to={`/trips/${trip.id}`} onClick={() => selectTrip(trip.id)}>Open trip <ArrowUpRight size={15} /></Link><button type="button" aria-pressed={selected} onClick={() => selectTrip(trip.id)}>{selected && <Check size={12} />}{selected ? 'Selected for Way' : 'Use with Way'}</button></div></article>
}

export function MyTripsPage() {
  const { profile, trips, loading, error, refreshTrips } = useTrips()
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()
  const formRef = useRef<HTMLDivElement>(null)
  useEffect(() => { if (creating) formRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }) }, [creating])
  return <div className="trips-feature"><div className="trips-page-heading"><div><p className="trips-kicker">MY TRIPS</p><h1>Your trips.<br /><em>All together.</em></h1><p>Real plans, saved for the moments ahead.</p></div>{profile && !creating && <Button onClick={() => setCreating(true)}><Plus size={16} /> New trip</Button>}</div><ProfileGate><StorageNotice />{creating && <div ref={formRef}><TripForm onCancel={() => setCreating(false)} onSaved={(trip) => { setCreating(false); navigate(`/trips/${trip.id}`) }} /></div>}{loading && <LoadingNotice>Loading your saved trips…</LoadingNotice>}{error && <ErrorNotice message={error} retry={() => void refreshTrips()} />}{!loading && !error && trips.length === 0 && !creating && <section className="trips-empty"><span className="trips-round-icon"><MapPin size={32} strokeWidth={1.2} /></span><h2>A little space for somewhere new.</h2><p>You haven’t saved a trip yet. Start with the dates, the destination, and the people coming along.</p><Button onClick={() => setCreating(true)}><Plus size={15} /> Create your first trip</Button></section>}{trips.length > 0 && <><div className="trips-list-heading"><p>{trips.length} saved {trips.length === 1 ? 'trip' : 'trips'}<span> · {profile?.display_name}’s collection</span></p><button type="button" disabled={loading} onClick={() => void refreshTrips()}><RefreshCw size={13} /> Refresh trips</button></div><div className="saved-trips-grid">{trips.map((trip) => <TripCard key={trip.id} trip={trip} />)}</div></>}</ProfileGate></div>
}

function ActivityForm({ trip, item, onSaved, onCancel }: { trip: TripDetail; item?: ItineraryItem; onSaved: () => void; onCancel: () => void }) {
  const { saveItem } = useTrips()
  const [form, setForm] = useState<ItemInput>(() => item ? { date: item.date, start_time: item.start_time, end_time: item.end_time, title: item.title, description: item.description, location: item.location, estimated_cost: item.estimated_cost, item_type: item.item_type, status: item.status } : { date: trip.start_date, start_time: '09:00', end_time: '10:00', title: '', description: '', location: '', estimated_cost: '0.00', item_type: 'activity', status: 'planned' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const prefix = useId()
  const setField = <K extends keyof ItemInput,>(key: K, value: ItemInput[K]) => setForm((previous) => ({ ...previous, [key]: value }))
  return <section className="trips-form-panel" aria-labelledby={`${prefix}-heading`}><div className="trips-panel-heading"><div><p className="trips-kicker">MAKE THE DAY YOURS</p><h2 id={`${prefix}-heading`}>{item ? 'Edit activity' : 'Add an activity'}</h2></div><button type="button" className="trips-icon-button" aria-label="Cancel activity form" disabled={busy} onClick={onCancel}><X size={19} /></button></div><form className="trips-form" aria-busy={busy} onSubmit={async (event) => {
    event.preventDefault()
    if (busy) return
    if (!form.title.trim()) { setError('Give this activity a title.'); return }
    if (form.date < trip.start_date || form.date > trip.end_date) { setError('Choose a date inside this trip’s dates.'); return }
    if (!form.start_time || !form.end_time || form.end_time <= form.start_time) { setError('Choose an end time after the start time. For overnight plans, use a separate activity on each date.'); return }
    if (!validateMoney(form.estimated_cost)) { setError('Enter an estimated cost from 0 to 10,000,000, with up to two decimal places.'); return }
    setBusy(true); setError(null)
    try { await saveItem(trip.id, item?.id ?? null, { ...form, title: form.title.trim(), description: form.description.trim(), location: form.location.trim(), estimated_cost: Number(form.estimated_cost).toFixed(2) }); onSaved() }
    catch (failure) { setError(errorMessage(failure)) } finally { setBusy(false) }
  }}><fieldset disabled={busy}><legend className="trips-sr-only">Activity details</legend><div className="trips-form-grid">
    <label className="trips-wide" htmlFor={`${prefix}-title`}>Activity title<input id={`${prefix}-title`} value={form.title} onChange={(event) => setField('title', event.target.value)} required maxLength={160} placeholder="Something to look forward to" /></label>
    <label htmlFor={`${prefix}-date`}>Date<input id={`${prefix}-date`} type="date" value={form.date} min={trip.start_date} max={trip.end_date} onChange={(event) => setField('date', event.target.value)} required /></label>
    <label htmlFor={`${prefix}-location`}>Location <span className="trips-optional">(optional)</span><input id={`${prefix}-location`} value={form.location} onChange={(event) => setField('location', event.target.value)} maxLength={200} placeholder="A place or address" /></label>
    <label htmlFor={`${prefix}-start`}>Start time<input id={`${prefix}-start`} type="time" value={form.start_time} onChange={(event) => setField('start_time', event.target.value)} required /></label>
    <label htmlFor={`${prefix}-end`}>End time<input id={`${prefix}-end`} type="time" value={form.end_time} onChange={(event) => setField('end_time', event.target.value)} required /></label>
    <label htmlFor={`${prefix}-cost`}>Estimated cost ({trip.currency})<input id={`${prefix}-cost`} inputMode="decimal" value={form.estimated_cost} onChange={(event) => setField('estimated_cost', event.target.value)} maxLength={12} required /></label>
    <label htmlFor={`${prefix}-type`}>Item type<select id={`${prefix}-type`} value={form.item_type} onChange={(event) => setField('item_type', event.target.value as ItemInput['item_type'])}><option value="activity">Activity</option><option value="food">Food</option><option value="transport">Transport</option><option value="accommodation">Accommodation</option><option value="other">Other</option></select></label>
    <label htmlFor={`${prefix}-status`}>Activity status<select id={`${prefix}-status`} value={form.status} onChange={(event) => setField('status', event.target.value as ItemInput['status'])}><option value="planned">Planned</option><option value="cancelled">Cancelled</option></select></label>
    <label className="trips-wide" htmlFor={`${prefix}-notes`}>Notes <span className="trips-optional">(optional)</span><textarea id={`${prefix}-notes`} value={form.description} onChange={(event) => setField('description', event.target.value)} maxLength={2000} rows={3} placeholder="Any details you’d like to keep" /></label>
  </div></fieldset><p className="trips-form-note">Times are local to the destination. Costs are estimates, not confirmed prices. Cancelled activities don’t count toward estimated spending.</p>{error && <ErrorNotice message={error} />}<div className="trips-form-actions"><Button type="submit" disabled={busy}>{busy ? 'Saving activity…' : item ? 'Save activity changes' : 'Save activity'}<Check size={15} /></Button><Button type="button" variant="ghost" disabled={busy} onClick={onCancel}>Cancel</Button></div></form></section>
}

export function TripDetailPage() {
  const { tripId } = useParams<{ tripId: string }>()
  const { profile, viewedTrip, viewTrip, selectedTripId, selectTrip, tripLoading, tripError, loadTrip, removeItem, mutationLoading } = useTrips()
  const [editingTrip, setEditingTrip] = useState(false)
  const [activityEditor, setActivityEditor] = useState<ItineraryItem | 'new' | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const editorRef = useRef<HTMLDivElement>(null)
  const openedTrip = useRef<string | null>(null)
  useEffect(() => {
    if (!profile?.id || !tripId) return
    viewTrip(tripId)
    const key = `${profile.id}:${tripId}`
    if (openedTrip.current !== key) { openedTrip.current = key; selectTrip(tripId) }
    return () => viewTrip(null)
  }, [profile?.id, tripId, selectTrip, viewTrip])
  useEffect(() => { setEditingTrip(false); setActivityEditor(null); setDeleteError(null); setNotice(null) }, [tripId])
  useEffect(() => { if (activityEditor || editingTrip) editorRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }) }, [activityEditor, editingTrip])
  const trip = viewedTrip?.id === tripId ? viewedTrip : null
  const orderedItems = trip ? [...trip.itinerary].sort((a, b) => `${a.date} ${a.start_time}`.localeCompare(`${b.date} ${b.start_time}`)) : []
  return <div className="trips-feature"><Link className="trips-back-link" to="/trips"><ArrowLeft size={14} /> My Trips</Link><ProfileGate>{!trip && (tripError ? <ErrorNotice message={tripError} retry={() => { if (tripId) void loadTrip(tripId).catch(() => undefined) }} /> : <LoadingNotice>{tripLoading ? 'Opening your saved trip…' : 'Preparing your trip…'}</LoadingNotice>)}{trip && <>
    <div className="trip-detail-hero"><div><p className="trips-kicker">YOUR SAVED JOURNEY</p><h1>{trip.name}</h1><p className="trip-detail-destination"><MapPin size={16} />{trip.destination}</p></div><span className={`trips-status trips-status-${trip.status}`}>{trip.status}</span></div>
    <div className="trip-detail-meta"><span><CalendarDays size={15} />{formatDate(trip.start_date)} — {formatDate(trip.end_date)}</span><span><Users size={15} />{trip.travelers} {trip.travelers === 1 ? 'traveler' : 'travelers'}</span>{trip.departure_location && <span>From {trip.departure_location}</span>}<Button size="sm" variant="outline" disabled={mutationLoading} onClick={() => { setEditingTrip(true); setActivityEditor(null); setNotice(null) }}><Pencil size={13} /> Edit trip</Button></div>
    {selectedTripId === trip.id ? <p className="trips-pip-context"><Check size={13} /> Selected for Way · Your buddy can use this saved trip for context.</p> : <button type="button" className="trips-pip-context trips-pip-context-button" onClick={() => selectTrip(trip.id)}><Plus size={13} /> Use this trip with Way</button>}<StorageNotice />{notice && <p className="trips-success" role="status"><Check size={14} />{notice}</p>}
    <div className="trip-budget-summary"><div><span><Wallet size={14} /> Trip budget</span><strong>{formatMoney(trip.budget, trip.currency)}</strong></div><div><span>Estimated spending</span><strong>{formatMoney(trip.estimated_total, trip.currency)}</strong></div><div className={Number(trip.remaining_budget) < 0 ? 'trips-over-budget' : ''}><span>Remaining budget</span><strong>{formatMoney(trip.remaining_budget, trip.currency)}</strong></div></div><p className="trip-budget-note">All amounts are in {trip.currency}. Estimates include planned activities only; nothing here is a confirmed booking.</p>
    <section className="trip-rescue-entry"><div><strong>Domino Rescue</strong><p>See how a cancelled flight affects a connected trip and review an approved simulated repair.</p></div><Button asChild variant="outline" size="sm"><Link to={`/trips/${trip.id}/rescue`}>Open rescue workspace <ArrowUpRight size={14} /></Link></Button></section>
    <div ref={editorRef}>{editingTrip && <TripForm trip={trip} onCancel={() => setEditingTrip(false)} onSaved={() => { setEditingTrip(false); setNotice('Trip changes saved.') }} />}{activityEditor && <ActivityForm key={activityEditor === 'new' ? 'new' : activityEditor.id} trip={trip} item={activityEditor === 'new' ? undefined : activityEditor} onCancel={() => setActivityEditor(null)} onSaved={() => { setActivityEditor(null); setNotice('Activity saved to your itinerary.') }} />}</div>
    <section className="trip-itinerary" aria-labelledby="itinerary-title"><div className="trips-section-heading"><div><p className="trips-kicker">ONE DAY AT A TIME</p><h2 id="itinerary-title">Your itinerary</h2></div><Button size="sm" disabled={!!deleting || mutationLoading} onClick={() => { setActivityEditor('new'); setEditingTrip(false); setNotice(null) }}><Plus size={14} /> Add activity</Button></div>{deleteError && <ErrorNotice message={deleteError} />}{orderedItems.length === 0 ? <div className="trips-itinerary-empty"><Clock3 size={28} strokeWidth={1.2} /><h3>A fresh page for your days.</h3><p>Add your first activity, a meal, or a moment to explore.</p></div> : <div className="trip-timeline">{orderedItems.map((item, index) => <div key={item.id}>{(index === 0 || orderedItems[index - 1].date !== item.date) && <h3 className="trip-day-heading">{formatDate(item.date, { weekday: 'long', month: 'long', day: 'numeric' })}</h3>}<article className={`trip-activity-card ${item.status === 'cancelled' ? 'trip-activity-cancelled' : ''}`}><div className="trip-activity-time"><Clock3 size={13} /><span>{item.start_time} — {item.end_time}</span></div><div className="trip-activity-content"><div className="trip-activity-title"><h4>{item.title}</h4><span className={`trips-status trips-status-${item.status}`}>{item.status === 'cancelled' ? 'cancelled' : item.item_type}</span></div>{item.location && <p className="trip-activity-location"><MapPin size={12} />{item.location}</p>}{item.description && <p className="trip-activity-description">{item.description}</p>}<p className="trip-activity-cost">{formatMoney(item.estimated_cost, trip.currency)}<span> estimated{item.status === 'cancelled' ? ' · excluded from spending' : ''}</span></p></div><div className="trip-activity-actions"><button type="button" disabled={!!deleting || mutationLoading} aria-label={`Edit ${item.title}`} onClick={() => { setActivityEditor(item); setEditingTrip(false); setNotice(null) }}><Pencil size={14} /> Edit</button><button type="button" disabled={!!deleting || mutationLoading} aria-label={`Remove ${item.title}`} onClick={async () => {
      if (deleting || !window.confirm(`Remove “${item.title}” from this itinerary? This removes the saved activity; it does not cancel a booking.`)) return
      setDeleting(item.id); setDeleteError(null); setNotice(null)
      try { await removeItem(trip.id, item.id); if (activityEditor !== 'new' && activityEditor?.id === item.id) setActivityEditor(null); setNotice('Activity removed from your itinerary.') }
      catch (failure) { setDeleteError(errorMessage(failure)) } finally { setDeleting(null) }
    }}><Trash2 size={14} />{deleting === item.id ? 'Removing…' : 'Remove'}</button></div></article></div>)}</div>}</section>
  </>}</ProfileGate></div>
}

export function DashboardTrips() {
  const { profile, trips, activeTrip, selectedTripId, loading, error, refreshTrips, selectTrip } = useTrips()
  const selectedTrip = selectedTripId && activeTrip?.id === selectedTripId ? activeTrip : null
  const today = localToday()
  const current = trips.filter((trip) => trip.status !== 'completed' && trip.start_date <= today && trip.end_date >= today)
  const upcoming = trips.filter((trip) => trip.status !== 'completed' && trip.start_date > today).sort((a, b) => a.start_date.localeCompare(b.start_date)).slice(0, 3)
  const next = selectedTrip?.itinerary.filter((item) => item.status === 'planned' && item.date >= today).sort((a, b) => `${a.date} ${a.start_time}`.localeCompare(`${b.date} ${b.start_time}`))[0]
  return <section className="trips-feature dashboard-saved-trips"><div className="trips-section-heading"><div><p className="trips-kicker">YOUR PLANS, IN ONE PLACE</p><h2>{profile ? `${profile.display_name}’s next chapters` : 'Make a little room for travel.'}</h2></div>{profile && <Link className="trips-text-link" to="/trips">My Trips <ArrowUpRight size={15} /></Link>}</div><ProfileGate><StorageNotice />{loading && <LoadingNotice>Loading your saved plans…</LoadingNotice>}{error && <ErrorNotice message={error} retry={() => void refreshTrips()} />}{!loading && !error && trips.length === 0 && <div className="dashboard-trips-empty"><Compass size={26} strokeWidth={1.3} /><div><h3>Your first journey starts with a few details.</h3><p>Create a trip, save an activity, and bring Way into the plan.</p></div><Button asChild variant="outline" size="sm"><Link to="/trips">Start a trip <Plus size={14} /></Link></Button></div>}{trips.length > 0 && <div className="dashboard-trip-columns"><div><h3>Happening now</h3>{current.length ? current.slice(0, 2).map((trip) => <Link className="dashboard-trip-link" key={trip.id} to={`/trips/${trip.id}`} onClick={() => selectTrip(trip.id)}><span><strong>{trip.name}</strong><small>{trip.destination} · through {formatDate(trip.end_date, { month: 'short', day: 'numeric' })}</small></span><ArrowUpRight size={15} /></Link>) : <p className="dashboard-no-plan">No trip is scheduled for today.</p>}<h3>Coming up</h3>{upcoming.length ? upcoming.map((trip) => <Link className="dashboard-trip-link" key={trip.id} to={`/trips/${trip.id}`} onClick={() => selectTrip(trip.id)}><span><strong>{trip.name}</strong><small>{trip.destination} · {formatDate(trip.start_date)}</small></span><ArrowUpRight size={15} /></Link>) : <p className="dashboard-no-plan">No upcoming trips yet. Your saved trips are in My Trips.</p>}</div><div className="dashboard-next-activity"><span className="trips-round-icon"><Clock3 size={23} /></span><p className="trips-kicker">FIRST PLANNED ACTIVITY FROM TODAY</p>{next && selectedTrip ? <><h3>{next.title}</h3><p>{formatDate(next.date)} · {next.start_time} — {next.end_time}</p>{next.location && <p><MapPin size={12} />{next.location}</p>}<Link className="trips-text-link" to={`/trips/${selectedTrip.id}`}>Open itinerary <ArrowUpRight size={14} /></Link></> : <><h3>A little breathing room.</h3><p>{selectedTrip ? 'No planned activities on or after today in this trip.' : 'Open a saved trip to see its next planned activity.'}</p></>}<small>Dates use this browser’s calendar. Activity times are local to the destination.</small></div></div>}</ProfileGate></section>
}

export function ProfileSettings() {
  const { profile, renameProfile } = useTrips()
  const [name, setName] = useState(profile?.display_name ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const prefix = useId()
  useEffect(() => setName(profile?.display_name ?? ''), [profile?.display_name])
  return <section className="trips-feature trips-profile-settings"><ProfileGate><div className="trips-section-heading"><div><p className="trips-kicker">YOUR TRAVELER PROFILE</p><h2>Your traveler profile</h2></div><UserRound size={24} strokeWidth={1.3} /></div><p className="trips-settings-description">Your saved trips belong to this traveler profile. Manage your username and password in My Account; private traveler details keep their separate vault password.</p><StorageNotice /><form className="trips-form" aria-busy={busy} onSubmit={async (event) => { event.preventDefault(); if (busy) return; if (!name.trim()) { setError('Please enter a display name.'); return }; setBusy(true); setError(null); setSaved(false); try { await renameProfile(name); setSaved(true) } catch (failure) { setError(errorMessage(failure)) } finally { setBusy(false) } }}><label htmlFor={`${prefix}-profile-name`}>Profile name<input id={`${prefix}-profile-name`} value={name} onChange={(event) => { setName(event.target.value); setSaved(false) }} required maxLength={80} autoComplete="nickname" disabled={busy} /></label>{error && <ErrorNotice message={error} />}{saved && <p className="trips-success" role="status"><Check size={13} /> Profile name saved.</p>}<div className="trips-form-actions"><Button type="submit" size="sm" disabled={busy || name.trim() === profile?.display_name}>{busy ? 'Saving name…' : 'Save profile name'}<Check size={14} /></Button></div></form><p className="trips-form-note">A linked account lets you reopen this profile by signing in. Existing unlinked local profiles can be connected through My Account.</p></ProfileGate></section>
}

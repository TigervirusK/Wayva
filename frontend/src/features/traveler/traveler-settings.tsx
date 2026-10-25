import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, Check, LockKeyhole, Plus, RefreshCw, ShieldCheck, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ProfileGate } from '@/features/trips/trips-pages'
import { useTrips } from '@/features/trips'
import { airlines, type PrivateBooking, type TravelerDetails, type VaultData } from './traveler-api'
import { usePrivateTraveler } from './use-private-traveler'
import './traveler.css'

export function VaultUnlock({ exists, busy, authenticate }: { exists: boolean; busy: boolean; authenticate: (password: string) => Promise<boolean> }) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [mismatch, setMismatch] = useState(false)
  const id = useId()
  return <form className="trips-form private-unlock" autoComplete="off" onSubmit={async event => {
    event.preventDefault(); if (busy) return
    if (!exists && password !== confirm) { setMismatch(true); return }
    try { await authenticate(password) } finally { setPassword(''); setConfirm('') }
  }}><p>{exists ? 'Unlock your encrypted traveler and booking details with your vault password.' : 'Create a separate password to encrypt your traveler and booking details. Keep it safe: there is no forgotten-password recovery for this local vault.'}</p>
    <label htmlFor={`${id}-password`}>{exists ? 'Vault password' : 'Create vault password'}<input id={`${id}-password`} type="password" minLength={12} maxLength={128} required disabled={busy} value={password} onChange={event => { setPassword(event.target.value); setMismatch(false) }} autoComplete={exists ? 'current-password' : 'new-password'} /></label>
    {!exists && <label htmlFor={`${id}-confirm`}>Confirm vault password<input id={`${id}-confirm`} type="password" minLength={12} maxLength={128} required disabled={busy} value={confirm} onChange={event => { setConfirm(event.target.value); setMismatch(false) }} autoComplete="new-password" /></label>}
    {mismatch && <p className="trips-error" role="alert">The passwords do not match.</p>}<span className="private-help">Use at least 12 characters. Unlock sessions expire after 15 minutes or a backend restart.</span><Button type="submit" disabled={busy}>{busy ? 'Opening private details…' : exists ? 'Unlock private details' : 'Create private traveler vault'}<LockKeyhole size={15} /></Button>
  </form>
}

function VaultEditor({ data, busy, save, changePassword }: { data: VaultData; busy: boolean; save: (data: VaultData) => Promise<boolean>; changePassword: (current: string, next: string) => Promise<boolean> }) {
  const { trips } = useTrips()
  const [form, setForm] = useState<VaultData>(data)
  const [saved, setSaved] = useState(false)
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [passwordChanged, setPasswordChanged] = useState(false)
  const id = useId()
  const setTraveler = (key: keyof TravelerDetails, value: string) => { setSaved(false); setForm(previous => ({ ...previous, traveler: { ...previous.traveler, [key]: value } })) }
  const setBooking = (bookingId: string, key: keyof PrivateBooking, value: string | null) => { setSaved(false); setForm(previous => ({ ...previous, bookings: previous.bookings.map(booking => booking.id === bookingId ? { ...booking, [key]: value } : booking) })) }
  const fields: { key: keyof TravelerDetails; label: string; type?: string; max: number; placeholder?: string }[] = [
    { key: 'given_names', label: 'Given names (as on your ticket)', max: 100 }, { key: 'family_name', label: 'Family name (as on your ticket)', max: 100 },
    { key: 'email', label: 'Contact email', type: 'email', max: 254 }, { key: 'phone', label: 'Contact phone', type: 'tel', max: 16, placeholder: '+12025550123' },
    { key: 'home_airport', label: 'Home airport code', max: 3, placeholder: 'CMH' }, { key: 'country_of_residence', label: 'Country of residence code', max: 2, placeholder: 'US' },
  ]
  return <><form className="trips-form private-editor" autoComplete="off" aria-busy={busy} onSubmit={async event => { event.preventDefault(); if (busy) return; setSaved(await save(form)) }}>
    <fieldset disabled={busy}><legend>Your traveler details</legend><p className="private-help">These contact fields are optional. Enter only what you want to keep for a future authorized booking workflow.</p><div className="trips-form-grid">{fields.map(field => <label key={field.key} htmlFor={`${id}-${field.key}`}>{field.label}<input id={`${id}-${field.key}`} type={field.type ?? 'text'} maxLength={field.max} placeholder={field.placeholder} value={form.traveler[field.key]} onChange={event => setTraveler(field.key, ['home_airport', 'country_of_residence'].includes(field.key) ? event.target.value.toUpperCase() : event.target.value)} /></label>)}
      <label htmlFor={`${id}-currency`}>Preferred currency<select id={`${id}-currency`} aria-label="Preferred currency" value={form.traveler.preferred_currency} onChange={event => setTraveler('preferred_currency', event.target.value)}>{['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'INR'].map(currency => <option key={currency}>{currency}</option>)}</select></label>
    </div></fieldset>
    <fieldset disabled={busy}><legend>Tickets you already booked elsewhere</legend><p className="private-help">Save your airline and original seller details here. Entries remain unverified; entering them does not authorize a booking change. Use a separate entry for each flight segment.</p>
      {form.bookings.map((booking, index) => <div className="private-booking" key={booking.id}><div className="private-booking-heading"><h3>Flight details {index + 1}</h3><span>User-entered · not verified</span><button className="trips-text-link" type="button" aria-label={`Remove saved flight details ${index + 1}`} onClick={() => { setSaved(false); setForm(previous => ({ ...previous, bookings: previous.bookings.filter(item => item.id !== booking.id) })) }}><Trash2 size={14} /> Remove</button></div><div className="trips-form-grid">
        <label htmlFor={`${id}-${booking.id}-airline`}>Airline<select id={`${id}-${booking.id}-airline`} aria-label="Airline" value={booking.airline} onChange={event => setBooking(booking.id, 'airline', event.target.value)}>{airlines.map(airline => <option value={airline.code} key={airline.code}>{airline.name}</option>)}</select></label>
        <label htmlFor={`${id}-${booking.id}-number`}>Flight number<input id={`${id}-${booking.id}-number`} value={booking.flight_number} maxLength={10} required placeholder="UA123" onChange={event => setBooking(booking.id, 'flight_number', event.target.value.toUpperCase().replaceAll(' ', ''))} /></label>
        <label htmlFor={`${id}-${booking.id}-date`}>Departure date at origin<input id={`${id}-${booking.id}-date`} type="date" required value={booking.departure_date} onChange={event => setBooking(booking.id, 'departure_date', event.target.value)} /></label>
        <label htmlFor={`${id}-${booking.id}-reference`}>Booking reference / confirmation code<input id={`${id}-${booking.id}-reference`} maxLength={30} required value={booking.booking_reference} onChange={event => setBooking(booking.id, 'booking_reference', event.target.value.toUpperCase())} /></label>
        <label htmlFor={`${id}-${booking.id}-origin`}>Origin airport code<input id={`${id}-${booking.id}-origin`} maxLength={3} minLength={3} required placeholder="ORD" value={booking.origin} onChange={event => setBooking(booking.id, 'origin', event.target.value.toUpperCase())} /></label>
        <label htmlFor={`${id}-${booking.id}-destination`}>Destination airport code<input id={`${id}-${booking.id}-destination`} maxLength={3} minLength={3} required placeholder="HND" value={booking.destination} onChange={event => setBooking(booking.id, 'destination', event.target.value.toUpperCase())} /></label>
        <label htmlFor={`${id}-${booking.id}-seller`}>Where did you buy the ticket?<select id={`${id}-${booking.id}-seller`} aria-label="Where did you buy the ticket?" value={booking.original_seller} onChange={event => setBooking(booking.id, 'original_seller', event.target.value)}><option value="airline">Directly from the airline</option><option value="travel_agency">Travel agency / booking website</option><option value="other">Other seller</option></select></label>
        <label htmlFor={`${id}-${booking.id}-seller-name`}>Original seller name<input id={`${id}-${booking.id}-seller-name`} value={booking.seller_name} maxLength={100} onChange={event => setBooking(booking.id, 'seller_name', event.target.value)} placeholder="Airline or agency name" /></label>
        <label className="trips-wide" htmlFor={`${id}-${booking.id}-trip`}>Link to a saved trip (optional)<select id={`${id}-${booking.id}-trip`} aria-label="Link to a saved trip (optional)" value={booking.trip_id ?? ''} onChange={event => setBooking(booking.id, 'trip_id', event.target.value || null)}><option value="">Unassigned</option>{trips.filter(trip => !trip.name.includes('Domino Rescue demo')).map(trip => <option value={trip.id} key={trip.id}>{trip.name}</option>)}</select></label>
      </div></div>)}
      <Button type="button" variant="outline" disabled={busy || form.bookings.length >= 20} onClick={() => { setSaved(false); setForm(previous => ({ ...previous, bookings: [...previous.bookings, { id: crypto.randomUUID(), trip_id: null, airline: 'UA', flight_number: '', departure_date: '', origin: '', destination: '', booking_reference: '', original_seller: 'airline', seller_name: '' }] })) }}><Plus size={15} /> Add existing flight details</Button>
    </fieldset>
    {saved && <p className="trips-success" role="status"><Check size={15} /> Private details saved encrypted. Booking details remain unverified.</p>}
    <div className="trips-form-actions"><Button type="submit" disabled={busy}>{busy ? 'Saving encrypted details…' : 'Save private details'}<ShieldCheck size={15} /></Button><Link className="text-link" to="/rescue/real">Open Real Travel assistance <ArrowUpRight size={14} /></Link></div>
    <p className="private-help">Remove an entry and save to delete it from your vault. This never cancels a ticket. Your private details are not added to Way’s context or browser storage.</p>
  </form>
  <details className="private-password-change"><summary>Change vault password</summary><form className="trips-form" onSubmit={async event => { event.preventDefault(); if (busy) return; try { setPasswordChanged(await changePassword(oldPassword, newPassword)) } finally { setOldPassword(''); setNewPassword('') } }}>
    <label htmlFor={`${id}-old-password`}>Current vault password<input id={`${id}-old-password`} type="password" required maxLength={128} disabled={busy} autoComplete="current-password" value={oldPassword} onChange={event => setOldPassword(event.target.value)} /></label>
    <label htmlFor={`${id}-new-password`}>New vault password<input id={`${id}-new-password`} type="password" required minLength={12} maxLength={128} disabled={busy} autoComplete="new-password" value={newPassword} onChange={event => setNewPassword(event.target.value)} /></label>
    {passwordChanged && <p className="trips-success" role="status">Vault password changed.</p>}<Button type="submit" variant="outline" disabled={busy}>Change password</Button><p className="private-help">Password changes use the last saved details. Save any edited fields first.</p>
  </form></details></>
}

export function TravelerSettings() {
  const vault = usePrivateTraveler()
  if (!vault.profile) return null
  return <section id="private-traveler" className="trips-feature traveler-settings"><div className="private-heading"><div><p className="eyebrow">PRIVATE TRAVELER DETAILS</p><h2>Your details. Ready when you need them.</h2><p>Keep contact information and tickets bought elsewhere in a password-encrypted local vault.</p></div><LockKeyhole size={26} strokeWidth={1.4} /></div>
    <ProfileGate><div className="private-boundary"><ShieldCheck size={19} /><p>No card numbers, passport scans, or airline passwords are collected. These details are not sent to Way or a booking provider. A saved reference does not grant permission to change a ticket.</p></div>
      {vault.error && <div className="trips-error" role="alert"><p>{vault.error}</p><button disabled={vault.busy} onClick={vault.reload}><RefreshCw size={14} /> Reload private details</button></div>}
      {vault.envelope && vault.notice && <p className="trips-success" role="status"><Check size={15} /> {vault.notice}</p>}
      {vault.loading ? <p role="status" className="trips-loading">Checking your private vault…</p> : vault.envelope ? <><div className="private-session"><span>Unlocked · automatically locks within {Math.ceil(vault.envelope.expires_in_seconds / 60)} minutes</span><Button variant="outline" size="sm" disabled={vault.busy} onClick={() => void vault.lock()}><LockKeyhole size={14} /> Lock private details</Button></div><VaultEditor key={`${vault.profile?.id}:${vault.envelope.revision}`} data={vault.envelope.data} busy={vault.busy} save={vault.save} changePassword={vault.changePassword} /></> : vault.status && <VaultUnlock exists={vault.status.exists} busy={vault.busy} authenticate={vault.authenticate} />}
      <p className="private-help private-production-note">This is a local privacy foundation. Local account sign-in is available. Production security, provider authorization, live monitoring, payment, and rebooking remain unfinished.</p>
    </ProfileGate>
  </section>
}

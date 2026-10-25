import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown, Clock3, LoaderCircle, MapPin, RefreshCw, ShieldCheck, Sparkles, X } from 'lucide-react'
import type { TripDetail } from '@/features/trips'
import { approveItineraryProposal, getItineraryProposal, rejectItineraryProposal, PlanningApiError, type ItineraryProposal, type ProposedActivity } from './planning-api'
import './planning.css'
import { perPersonAllowance, safePlanningQuality, safeReferenceUrl, subtractMoney } from '@/lib/planning-display'

export interface ItineraryProposalCardProps {
  proposal: ItineraryProposal
  profileToken: string
  currency?: string
  onUpdated: (proposal: ItineraryProposal) => void
  onApplied: (trip: TripDetail) => void | Promise<void>
  onRegenerate: () => void
  regenerating?: boolean
}

function amount(value: string | number, currency?: string): string {
  if (!currency) return `${new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value))} in trip currency`
  return new Intl.NumberFormat(undefined, { style: 'currency', currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value))
}

function dayLabel(date: string): string {
  return new Intl.DateTimeFormat(undefined, { weekday: 'short', month: 'short', day: 'numeric' }).format(new Date(`${date}T12:00:00`))
}

export function ItineraryProposalCard({ proposal, profileToken, currency: fallbackCurrency, onUpdated, onApplied, onRegenerate, regenerating = false }: ItineraryProposalCardProps) {
  const currency = proposal.currency ?? fallbackCurrency
  const quality = safePlanningQuality(proposal.quality)
  const [working, setWorking] = useState<'approve' | 'reject' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false)
  const [refreshError, setRefreshError] = useState(false)
  const requestRef = useRef<AbortController | null>(null)
  const lockRef = useRef(false)
  const mountedRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    setWorking(null); setError(null); setConflict(false); setRefreshError(false); lockRef.current = false
    return () => { mountedRef.current = false; requestRef.current?.abort() }
  }, [proposal.id])

  const groups = new Map<string, ProposedActivity[]>()
  for (const item of [...proposal.activities].sort((a, b) => `${a.date} ${a.start_time}`.localeCompare(`${b.date} ${b.start_time}`))) groups.set(item.date, [...(groups.get(item.date) ?? []), item])
  const pending = proposal.status === 'pending' && !conflict
  const busy = !!working || regenerating
  const stale = proposal.status === 'stale' || conflict

  const act = async (action: 'approve' | 'reject') => {
    if (lockRef.current || !pending || regenerating) return
    lockRef.current = true
    setWorking(action); setError(null); setRefreshError(false)
    const controller = new AbortController()
    requestRef.current = controller
    try {
      if (action === 'approve') {
        const result = await approveItineraryProposal(proposal.trip_id, proposal.id, profileToken, controller.signal)
        if (!mountedRef.current || controller.signal.aborted) return
        onUpdated(result.proposal)
        try { await onApplied(result.trip) } catch { if (mountedRef.current) setRefreshError(true) }
      } else {
        const result = await rejectItineraryProposal(proposal.trip_id, proposal.id, profileToken, controller.signal)
        if (mountedRef.current && !controller.signal.aborted) onUpdated(result)
      }
    } catch (failure) {
      if (!mountedRef.current || controller.signal.aborted) return
      setError(failure instanceof Error ? failure.message : 'The proposal could not be updated. Please try again.')
      if (failure instanceof PlanningApiError && failure.status === 409) {
        setConflict(true)
        try {
          const current = await getItineraryProposal(proposal.trip_id, proposal.id, profileToken, controller.signal)
          if (mountedRef.current && !controller.signal.aborted) {
            onUpdated(current)
            if (current.status === 'approved' || current.status === 'rejected') {
              setConflict(false)
              setError(current.status === 'approved' ? 'This proposal was already saved. Reopen the trip to refresh its activities.' : null)
            }
          }
        } catch { /* Preserve the conflict and offer a new proposal when refresh is unavailable. */ }
      }
    } finally {
      if (requestRef.current === controller) {
        lockRef.current = false
        if (mountedRef.current) setWorking(null)
      }
    }
  }

  return <section className={`itinerary-proposal itinerary-proposal-${proposal.status}`} aria-label="Itinerary proposal review" aria-busy={busy}>
    <div className="proposal-topline"><span className={`proposal-mode ${proposal.mode === 'demo' ? 'proposal-mode-demo' : ''}`}><Sparkles size={12} />{proposal.mode === 'demo' ? 'Curated demo · not AI' : proposal.mode === 'ollama' ? 'Local AI proposal' : 'AI proposal'}</span><span className="proposal-status">{proposal.superseded_by ? 'Replaced by newer draft' : stale ? 'Needs a fresh look' : proposal.status === 'pending' ? 'Review first' : proposal.status === 'approved' ? 'Saved' : 'Rejected'}</span></div>
    <h3 className="proposal-title">{proposal.title}</h3><p className="proposal-summary">{proposal.summary}</p>
    <p className="proposal-estimate-label"><ShieldCheck size={12} /> Suggestions only · group spending allowances, not venue quotes</p>
    {quality && <details className="proposal-quality"><summary>Place checks, costs & assumptions</summary><p>{quality.trip_days} calendar days inclusive · {quality.travelers} travelers · daily window {quality.daily_window}.</p><p>{quality.buffer_policy}</p><p>Flight arrival and departure times are unknown. Travel-day free time is an assumption.</p><p>Place references check identity or area only. Future opening hours, availability, menus, and routes are unverified.</p><ul>{quality.places.map(place => <li key={place.index}><strong>{proposal.activities[place.index]?.title ?? place.name}</strong>: {place.status === 'reference_matched' ? `Name/city reference: ${place.name}, ${place.area}, ${place.city}` : place.status === 'area_reference' ? `Area reference only: ${place.area}, ${place.city}; individual venue unverified` : 'Place identity and location unverified'}.{safeReferenceUrl(place.source_url) && <a href={safeReferenceUrl(place.source_url)!} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer"> Check reference</a>}</li>)}</ul>{quality.warnings.length > 0 && <ul>{quality.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul>}<dl>{Object.entries(quality.by_category).map(([kind, cost]) => <div key={kind}><dt>{kind === 'activity' ? 'Sightseeing' : kind === 'food' ? 'Meals' : kind}</dt><dd>{amount(cost, currency)} group allowance</dd></div>)}</dl><p>{quality.exclusions} A meal allowance does not mean a venue can serve you at that price. No currency conversion or live quote is provided.</p></details>}
    {!quality && <p className="proposal-footer-note">This draft has no stored place-reference report. Check every venue and route yourself.</p>}

    <div className="proposal-days">{[...groups].map(([date, activities], index) => <details key={date} className="proposal-day" open={index === 0}><summary><span>{dayLabel(date)}</span><span>{activities.length} {activities.length === 1 ? 'stop' : 'stops'}<ChevronDown size={13} /></span></summary><ol>{activities.map((item, itemIndex) => <li key={`${date}-${item.start_time}-${itemIndex}`}><div className="proposal-activity-time"><Clock3 size={11} />{item.start_time} — {item.end_time}</div><h4>{item.title}</h4>{item.location && <p className="proposal-location"><MapPin size={11} />{item.location}</p>}{item.description && <p className="proposal-activity-description">{item.description}</p>}<span className="proposal-activity-cost">{amount(item.estimated_cost, currency)}<small> estimated</small></span></li>)}</ol></details>)}</div>

    <div className="proposal-budget"><span className="proposal-budget-heading">THE BUDGET PICTURE · WHOLE GROUP</span><dl><div><dt>Already planned</dt><dd>{amount(subtractMoney(proposal.resulting_estimated_total, proposal.estimated_total), currency)}</dd></div><div><dt>Proposed additions</dt><dd>+ {amount(proposal.estimated_total, currency)}</dd></div>{quality && <div><dt>Additions per person, approx.</dt><dd>{amount(perPersonAllowance(proposal.estimated_total, quality.travelers), currency)}</dd></div>}<div className="proposal-budget-total"><dt>After approval</dt><dd>{amount(proposal.resulting_estimated_total, currency)}</dd></div><div className={Number(proposal.remaining_budget) < 0 ? 'proposal-budget-over' : ''}><dt>Remaining budget</dt><dd>{amount(proposal.remaining_budget, currency)}</dd></div></dl></div>
    {proposal.notes.length > 0 && <ul className="proposal-notes" aria-label="Planning notes">{proposal.notes.map((note, index) => <li key={index}>{note}</li>)}</ul>}

    {error && <p className="proposal-error" role="alert">{error}</p>}
    {refreshError && <p className="proposal-error" role="alert">Your proposal was saved, but the trip view could not refresh. Reopen the trip to see the saved activities.</p>}
    {proposal.status === 'approved' && <p className="proposal-result" role="status"><Check size={14} /> Saved to itinerary</p>}
    {proposal.status === 'rejected' && <p className="proposal-result proposal-result-muted" role="status"><X size={14} />{proposal.superseded_by ? 'Replaced by a newer draft · itinerary unchanged' : 'Proposal rejected · itinerary unchanged'}</p>}
    {stale && <p className="proposal-stale" role="status">Proposal is out of date. Your trip needs a fresh proposal before these activities can be saved.</p>}

    <div className="proposal-actions">{pending ? <><button type="button" className="proposal-approve" disabled={busy || !profileToken} onClick={() => void act('approve')}>{working === 'approve' ? <LoaderCircle size={14} className="proposal-spinner" /> : <Check size={14} />}{working === 'approve' ? 'Saving activities…' : 'Approve and save'}</button><button type="button" className="proposal-reject" disabled={busy || !profileToken} onClick={() => void act('reject')}>{working === 'reject' ? <LoaderCircle size={13} className="proposal-spinner" /> : <X size={13} />}{working === 'reject' ? 'Rejecting…' : 'Reject proposal'}</button></> : <button type="button" className="proposal-regenerate" disabled={busy} onClick={onRegenerate}><RefreshCw size={13} className={regenerating ? 'proposal-spinner' : ''} />{regenerating ? 'Generating a fresh proposal…' : 'Generate a fresh proposal'}</button>}</div>
    <p className="proposal-footer-note">Saving adds these activities to your existing itinerary. It does not make reservations.</p>
  </section>
}

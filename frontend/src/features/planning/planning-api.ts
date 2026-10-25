import type { Currency, TripDetail } from '@/features/trips'
import type { PlanningQuality } from '@/lib/planning-display'

export interface ProposedActivity {
  date: string
  start_time: string
  end_time: string
  title: string
  description: string
  location: string
  estimated_cost: string
  item_type: 'activity' | 'food' | 'transport' | 'accommodation' | 'other'
}

export interface ItineraryProposal {
  id: string
  trip_id: string
  status: 'pending' | 'approved' | 'rejected' | 'stale'
  mode: 'demo' | 'openai' | 'ollama'
  currency: Currency
  request: string
  title: string
  summary: string
  activities: ProposedActivity[]
  notes: string[]
  estimated_total: string
  resulting_estimated_total: string
  remaining_budget: string
  created_at: string
  approved_at: string | null
  superseded_by?: string | null
  quality?: PlanningQuality | null
}

export type Proposal = ItineraryProposal
export type ProposalApproval = { proposal: ItineraryProposal; trip: TripDetail }

export class PlanningApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}

const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')

async function planningRequest<T>(path: string, token: string, method: 'GET' | 'POST', body?: unknown, signal?: AbortSignal, timeout = 20000): Promise<T> {
  const controller = new AbortController()
  let timedOut = false
  const abort = () => controller.abort()
  if (signal?.aborted) abort()
  signal?.addEventListener('abort', abort, { once: true })
  const timer = window.setTimeout(() => { timedOut = true; controller.abort() }, timeout)
  try {
    const response = await fetch(`${apiBase}${path}`, {
      method, signal: controller.signal,
      headers: { Accept: 'application/json', 'X-Profile-Token': token, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!response.ok) {
      let message = response.status === 409 ? 'The trip changed since this proposal was made. Generate a fresh proposal before saving.'
        : response.status === 401 ? 'Your account session could not be opened. Sign in again before continuing.'
          : response.status === 429 ? 'The AI provider is busy. Please wait a moment, then try again.'
            : response.status === 504 ? 'The itinerary request took too long. Please try again.'
              : 'This proposal request could not be completed. Please try again.'
      if (response.headers.get('content-type')?.includes('application/json')) {
        try {
          const data: unknown = await response.json()
          if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string' && data.detail.trim().length > 0 && data.detail.length <= 500 && !/[<>\u0000-\u001f]/.test(data.detail)) message = data.detail
        } catch { /* Keep a predictable explanation when an intermediary returns an invalid body. */ }
      }
      throw new PlanningApiError(message, response.status)
    }
    return await response.json() as T
  } catch (failure) {
    if (failure instanceof PlanningApiError) throw failure
    if (signal?.aborted) throw new DOMException('The proposal request was cancelled.', 'AbortError')
    if (timedOut) throw new PlanningApiError('The request took too long to confirm. Check the saved proposal before retrying.', 504)
    throw new PlanningApiError('The backend could not finish this proposal request. Check the connection and try again.', 0)
  } finally {
    window.clearTimeout(timer)
    signal?.removeEventListener('abort', abort)
  }
}

const proposalPath = (tripId: string, proposalId?: string) => `/trips/${encodeURIComponent(tripId)}/proposals${proposalId ? `/${encodeURIComponent(proposalId)}` : ''}`

export function createItineraryProposal(tripId: string, request: string, profileToken: string, signal?: AbortSignal): Promise<ItineraryProposal> {
  const trimmed = request.trim()
  if (!trimmed || trimmed.length > 2000) return Promise.reject(new PlanningApiError('Describe the itinerary you want in 1 to 2,000 characters.', 422))
  // A complete multi-day plan with meal stops needs more time than a normal read.
  return planningRequest(proposalPath(tripId), profileToken, 'POST', { request: trimmed }, signal, 300000)
}

export function getItineraryProposal(tripId: string, proposalId: string, profileToken: string, signal?: AbortSignal): Promise<ItineraryProposal> {
  return planningRequest(proposalPath(tripId, proposalId), profileToken, 'GET', undefined, signal)
}

export function listItineraryProposals(tripId: string, profileToken: string, signal?: AbortSignal): Promise<ItineraryProposal[]> {
  return planningRequest(proposalPath(tripId), profileToken, 'GET', undefined, signal)
}

export function approveItineraryProposal(tripId: string, proposalId: string, profileToken: string, signal?: AbortSignal): Promise<ProposalApproval> {
  return planningRequest(`${proposalPath(tripId, proposalId)}/approve`, profileToken, 'POST', undefined, signal)
}

export function rejectItineraryProposal(tripId: string, proposalId: string, profileToken: string, signal?: AbortSignal): Promise<ItineraryProposal> {
  return planningRequest(`${proposalPath(tripId, proposalId)}/reject`, profileToken, 'POST', undefined, signal)
}

export interface Reservation {
  id: string; key: string; kind: 'flight' | 'pickup' | 'hotel' | 'tour'; title: string
  location: string; provider: string; simulated: boolean; booking_reference: string
  start_at: string; end_at: string; estimated_cost: string
  status: 'confirmed' | 'at_risk' | 'cancelled'; itinerary_item_id: string | null
}
export interface RecoveryAction {
  reservation_id: string; kind: Reservation['kind']; title: string; action: string
  before_start_at: string; before_end_at: string; start_at: string; end_at: string
  estimated_cost: string; extra_cost: string; booking_reference: string
}
export interface RecoveryPlan {
  id: string; strategy: 'fastest' | 'cheapest' | 'balanced'
  status: 'pending' | 'applied' | 'failed' | 'stale'; title: string; explanation: string
  flight: string; arrival_at: string; delay_hours: number; extra_cost: string; schedule_changes: number
  tour_moved: boolean; actions: RecoveryAction[]; available: boolean; blocked_reason: string | null
  tradeoffs: string[]; error: string | null; approved_at: string | null; executed_at: string | null
}
export interface RescueState {
  trip_id: string; trip_name: string; currency: string; timezone: string; simulated: boolean; scenario_ready: boolean
  reservations: Reservation[]
  dependencies: { source_id: string; target_id: string; reason: string }[]
  disruption: { id: string; status: 'open' | 'resolved'; kind: string; reservation_id: string; details: { message: string; affected_ids: string[] }; created_at: string } | null
  plans: RecoveryPlan[]
  audit: { id: number; action: string; result: string; details: { message: string }; plan_id: string | null; created_at: string }[]
}

const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')
async function request<T>(token: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController()
  const abort = () => controller.abort()
  if (signal?.aborted) abort()
  signal?.addEventListener('abort', abort, { once: true })
  const timeout = window.setTimeout(abort, 20000)
  try {
    const response = await fetch(`${base}${path}`, {
      method: body === undefined ? 'GET' : 'POST', signal: controller.signal,
      headers: { Accept: 'application/json', 'X-Profile-Token': token, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!response.ok) {
      let message = response.status === 401 ? 'Your account session could not be opened. Sign in again to reconnect.' : 'The rescue request could not be completed. Retry or refresh to check the saved state.'
      try {
        const data: unknown = await response.json()
        if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string' && data.detail.length < 600 && !/[<>]/.test(data.detail)) message = data.detail
      } catch { /* Use the bounded fallback. */ }
      throw new Error(message)
    }
    return await response.json() as T
  } catch (failure) {
    if (controller.signal.aborted && !signal?.aborted) throw new Error('The request took too long. Refresh to check whether the change was saved before trying again.')
    if (failure instanceof TypeError) throw new Error('The backend could not be reached. Check the connection, then refresh.')
    throw failure
  } finally { window.clearTimeout(timeout); signal?.removeEventListener('abort', abort) }
}
const path = (id: string) => `/trips/${encodeURIComponent(id)}/rescue`
export const rescueApi = {
  create: (token: string, fresh = false) => request<{ trip_id: string; created: boolean }>(token, '/rescue/demo', { fresh }),
  get: (token: string, id: string, signal?: AbortSignal) => request<RescueState>(token, path(id), undefined, signal),
  simulate: (token: string, id: string) => request<RescueState>(token, `${path(id)}/simulate-cancellation`, {}),
  options: (token: string, id: string) => request<RescueState>(token, `${path(id)}/options`, {}),
  approve: (token: string, id: string, plan: string, simulate_failure: boolean) => request<RescueState>(token, `${path(id)}/plans/${encodeURIComponent(plan)}/approve-execute`, { approved: true, simulate_failure }),
}

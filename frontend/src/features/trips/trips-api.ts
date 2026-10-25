export type Currency = 'USD' | 'EUR' | 'GBP' | 'JPY' | 'CAD' | 'AUD' | 'INR'
export type TripStatus = 'planned' | 'active' | 'completed'
export type ItemType = 'activity' | 'food' | 'transport' | 'accommodation' | 'other'
export type ItemStatus = 'planned' | 'cancelled'

export interface Profile {
  id: string
  display_name: string
  communication_style: string
  created_at: string
}

export interface TripInput {
  name: string
  destination: string
  departure_location: string
  start_date: string
  end_date: string
  travelers: number
  budget: string
  currency: Currency
  status: TripStatus
}

export interface TripSummary extends TripInput {
  id: string
  owner_id: string
  created_at: string
  updated_at: string
  estimated_total: string
  remaining_budget: string
  item_count: number
}

export interface ItemInput {
  date: string
  start_time: string
  end_time: string
  title: string
  description: string
  location: string
  estimated_cost: string
  item_type: ItemType
  status: ItemStatus
}

export interface ItineraryItem extends ItemInput {
  id: string
  trip_id: string
}

export interface TripDetail extends TripSummary {
  itinerary: ItineraryItem[]
}

export class TripsApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}

const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')

async function request<T>(path: string, options: { token?: string; method?: string; body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.token) headers['X-Profile-Token'] = options.token
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  const controller = new AbortController()
  let timedOut = false
  const cancel = () => controller.abort()
  if (options.signal?.aborted) cancel()
  options.signal?.addEventListener('abort', cancel, { once: true })
  const timer = window.setTimeout(() => { timedOut = true; controller.abort() }, 20000)
  let response: Response
  try {
    response = await fetch(`${apiBase}${path}`, {
      method: options.method ?? 'GET', headers, signal: controller.signal,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  } catch (error) {
    if (timedOut) throw new TripsApiError('The request took too long. Check the connection and try again.', 0)
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new TripsApiError('The backend could not be reached. Check the connection and try again.', 0)
  } finally {
    window.clearTimeout(timer)
    options.signal?.removeEventListener('abort', cancel)
  }
  if (!response.ok) {
    let message = response.status === 401
      ? 'Your account or local profile could not be opened. Sign in again.'
      : response.status === 404 ? 'That trip or activity could not be found for this profile.'
        : 'Your changes could not be saved. Please try again.'
    if (response.headers.get('content-type')?.includes('application/json')) {
      try {
        const data: unknown = await response.json()
        if (typeof data === 'object' && data !== null && 'detail' in data) {
          if (typeof data.detail === 'string' && data.detail.length <= 600 && !/[<>]/.test(data.detail)) message = data.detail
          else if (Array.isArray(data.detail)) {
            const details = data.detail.slice(0, 4).flatMap((item: unknown) => {
              if (typeof item !== 'object' || item === null || !('msg' in item) || typeof item.msg !== 'string') return []
              const field = 'loc' in item && Array.isArray(item.loc) ? item.loc.filter((part) => part !== 'body').join(' ').replaceAll('_', ' ') : 'Input'
              return [`${field}: ${item.msg.slice(0, 180)}`]
            })
            if (details.length) message = details.join('. ')
          }
        }
      } catch { /* Preserve a clear fallback when an intermediary returns a non-JSON error. */ }
    }
    throw new TripsApiError(message, response.status)
  }
  return response.json() as Promise<T>
}

const tripPath = (id: string) => `/trips/${encodeURIComponent(id)}`

export const tripsApi = {
  createProfile: (display_name: string) => request<{ profile: Profile; token: string }>('/profiles', { method: 'POST', body: { display_name } }),
  getProfile: (token: string, signal?: AbortSignal) => request<Profile>('/profiles/me', { token, signal }),
  renameProfile: (token: string, display_name: string) => request<Profile>('/profiles/me', { token, method: 'PATCH', body: { display_name } }),
  list: (token: string, signal?: AbortSignal) => request<TripSummary[]>('/trips', { token, signal }),
  get: (token: string, id: string, signal?: AbortSignal) => request<TripDetail>(tripPath(id), { token, signal }),
  create: (token: string, input: TripInput) => request<TripDetail>('/trips', { token, method: 'POST', body: input }),
  update: (token: string, id: string, input: TripInput) => request<TripDetail>(tripPath(id), { token, method: 'PUT', body: input }),
  saveItem: (token: string, id: string, itemId: string | null, input: ItemInput) => request<TripDetail>(`${tripPath(id)}/itinerary${itemId ? `/${encodeURIComponent(itemId)}` : ''}`, { token, method: itemId ? 'PUT' : 'POST', body: input }),
  removeItem: (token: string, id: string, itemId: string) => request<TripDetail>(`${tripPath(id)}/itinerary/${encodeURIComponent(itemId)}`, { token, method: 'DELETE' }),
}

export function formatMoney(amount: string, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(amount))
}

export function formatDate(date: string, options: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', year: 'numeric' }): string {
  return new Intl.DateTimeFormat(undefined, options).format(new Date(`${date}T12:00:00`))
}

export function localToday(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

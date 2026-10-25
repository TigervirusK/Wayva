export interface TravelerDetails {
  given_names: string; family_name: string; email: string; phone: string
  home_airport: string; country_of_residence: string; preferred_currency: string
}
export type AirlineCode = 'AA' | 'UA' | 'DL' | 'BA' | 'NH' | 'JL' | 'OTHER'
export interface PrivateBooking {
  id: string; trip_id: string | null; airline: AirlineCode; flight_number: string; departure_date: string
  origin: string; destination: string; booking_reference: string
  original_seller: 'airline' | 'travel_agency' | 'other'; seller_name: string
}
export interface VaultData { traveler: TravelerDetails; bookings: PrivateBooking[] }
export interface VaultEnvelope { revision: string; data: VaultData; expires_in_seconds: number }
export interface VaultStatus { exists: boolean; unlocked: boolean; expires_in_seconds: number; production_account_ready: false }
export interface RealCapabilities {
  mode: 'real'; access: 'assisted_only'; provider_connected: boolean; assisted_handoff: boolean
  encrypted_settings: boolean; flight_monitoring: boolean; live_flight_search: boolean; rebooking: boolean
  provider_confirmation: boolean; automatic_itinerary_repair: boolean; external_changes: boolean
  production_account_ready: boolean; message: string; airlines: { code: AirlineCode; name: string }[]
  stages: { id: string; label: string; status: string; reason: string }[]
}
export interface Assistance {
  booking_id: string; verification_status: string; booking_status: string; provider_confirmed: boolean
  airline_name: string; official_airline_url: string | null; original_seller: string
  contact_original_seller: boolean; steps: string[]; disclosure: string
}
export const airlines: { code: AirlineCode; name: string }[] = [
  { code: 'AA', name: 'American Airlines' }, { code: 'UA', name: 'United Airlines' },
  { code: 'DL', name: 'Delta Air Lines' }, { code: 'BA', name: 'British Airways' },
  { code: 'NH', name: 'ANA' }, { code: 'JL', name: 'Japan Airlines' }, { code: 'OTHER', name: 'Other airline' },
]
export class PrivateApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}
const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')
async function request<T>(path: string, token?: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController()
  const abort = () => controller.abort()
  if (signal?.aborted) abort()
  signal?.addEventListener('abort', abort, { once: true })
  const timer = window.setTimeout(abort, 20000)
  try {
    const response = await fetch(`${base}${path}`, { method, signal: controller.signal, cache: 'no-store', credentials: 'same-origin',
      headers: { Accept: 'application/json', ...(token ? { 'X-Profile-Token': token } : {}), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!response.ok) {
      let message = 'Private details could not be loaded or saved. Check the connection and retry.'
      try {
        const data = await response.json() as { detail?: unknown }
        if (typeof data.detail === 'string' && data.detail.length < 600 && !/[<>]/.test(data.detail)) message = data.detail
        else if (Array.isArray(data.detail)) {
          message = data.detail.slice(0, 3).map((error: { msg?: string; loc?: unknown[] }) => `${(error.loc ?? []).slice(1).join(' ')}: ${typeof error.msg === 'string' ? error.msg.slice(0, 180) : 'Check this field.'}`).join('. ')
        }
      } catch { /* Never echo a response body or a submitted secret. */ }
      throw new PrivateApiError(message, response.status)
    }
    return await response.json() as T
  } catch (failure) {
    if (controller.signal.aborted && !signal?.aborted) throw new PrivateApiError('The private request timed out. Reload to check the saved state before retrying.', 0)
    if (failure instanceof TypeError) throw new PrivateApiError('The backend could not be reached. Check the connection.', 0)
    throw failure
  } finally { window.clearTimeout(timer); signal?.removeEventListener('abort', abort) }
}
const path = '/private-traveler'
export const travelerApi = {
  status: (token: string, signal?: AbortSignal) => request<VaultStatus>(`${path}/status`, token, 'GET', undefined, signal),
  read: (token: string, signal?: AbortSignal) => request<VaultEnvelope>(path, token, 'GET', undefined, signal),
  create: (token: string, password: string) => request<VaultEnvelope>(`${path}/create`, token, 'POST', { password }),
  unlock: (token: string, password: string) => request<VaultEnvelope>(`${path}/unlock`, token, 'POST', { password }),
  lock: (token: string) => request<{ locked: boolean }>(`${path}/lock`, token, 'POST', {}),
  save: (token: string, revision: string, data: VaultData) => request<VaultEnvelope>(path, token, 'PUT', { revision, data }),
  changePassword: (token: string, current_password: string, password: string) => request<VaultEnvelope>(`${path}/change-password`, token, 'POST', { current_password, password }),
  capabilities: (signal?: AbortSignal) => request<RealCapabilities>('/rescue/real/capabilities', undefined, 'GET', undefined, signal),
  assistance: (token: string, booking_id: string) => request<Assistance>(`${path}/rescue-assistance`, token, 'POST', { booking_id }),
}

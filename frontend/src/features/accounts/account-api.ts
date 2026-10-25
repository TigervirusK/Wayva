import type { Profile } from '@/features/trips/trips-api'

export interface AccountSession {
  account: { username: string }
  profile: Profile
  csrf_token: string
  expires_at: string
  idle_timeout_seconds: number
}
export class AccountApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}
const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')
async function request<T>(path: string, method = 'GET', body?: unknown, proof?: string | null, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController()
  const abort = () => controller.abort()
  if (signal?.aborted) abort()
  signal?.addEventListener('abort', abort, { once: true })
  const timer = window.setTimeout(abort, 20000)
  try {
    const response = await fetch(`${base}/auth${path}`, { method, cache: 'no-store', credentials: 'same-origin', signal: controller.signal,
      headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }), ...(proof ? { 'X-Profile-Token': proof } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!response.ok) {
      let message = 'Your account request could not be completed. Check the connection and retry.'
      try {
        const data = await response.json() as { detail?: unknown }
        if (typeof data.detail === 'string' && data.detail.length < 600 && !/[<>]/.test(data.detail)) message = data.detail
        else if (Array.isArray(data.detail)) message = data.detail.slice(0, 3).map((entry: { msg?: string }) => typeof entry.msg === 'string' ? entry.msg.slice(0, 180) : 'Check the account form.').join(' ')
      } catch { /* Never echo a body or a password. */ }
      throw new AccountApiError(message, response.status)
    }
    return await response.json() as T
  } catch (failure) {
    if (controller.signal.aborted && !signal?.aborted) throw new AccountApiError('The account request timed out. Check your sign-in status before retrying.', 0)
    if (failure instanceof TypeError) throw new AccountApiError('The backend could not be reached. Check the connection.', 0)
    throw failure
  } finally { window.clearTimeout(timer); signal?.removeEventListener('abort', abort) }
}
export const accountApi = {
  session: (signal?: AbortSignal) => request<AccountSession>('/session', 'GET', undefined, undefined, signal),
  login: (username: string, password: string) => request<AccountSession>('/login', 'POST', { username, password }),
  register: (username: string, password: string, display_name: string, link_current_profile: boolean, legacy?: string | null) => request<AccountSession>('/register', 'POST', { username, password, display_name, link_current_profile }, legacy),
  logout: (proof: string | null) => request<{ signed_out: boolean }>('/logout', 'POST', {}, proof),
  changePassword: (proof: string, current_password: string, new_password: string) => request<AccountSession>('/change-password', 'POST', { current_password, new_password }, proof),
}
export const accountProof = (session: AccountSession) => `account-session:${session.csrf_token}`

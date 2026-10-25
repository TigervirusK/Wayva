export type BuddyFeature = 'dream' | 'memory' | 'rescue' | 'sidequest' | 'harmony' | 'split'
export type BuddyMode = 'demo' | 'openai' | 'ollama'
import type { ItineraryProposal } from '@/features/planning'

export interface BuddyMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface BuddyConfig {
  mode: BuddyMode
  name: 'Way'
  max_message_length: number
  ai_ready: boolean
  setup_required: boolean
}

export interface BuddyReply {
  reply: string
  mode: BuddyMode
  proposal: ItineraryProposal | null
}

const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')

export class BuddyApiError extends Error {}

function isMode(value: unknown): value is BuddyMode {
  return value === 'demo' || value === 'openai' || value === 'ollama'
}

async function backendError(response: Response, fallback: string): Promise<BuddyApiError> {
  // These HTTP errors have deliberately sanitized, actionable backend messages.
  // Reject arbitrary bodies, HTML, structured validation errors, and long details.
  const safeStatuses = new Set([400, 401, 403, 408, 409, 422, 429, 502, 503, 504])
  if (safeStatuses.has(response.status) && response.headers.get('content-type')?.includes('application/json')) {
    try {
      const data: unknown = await response.json()
      if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string') {
        const detail = data.detail.trim()
        if (detail.length > 0 && detail.length <= 300 && !/[<>\u0000-\u001f]/.test(detail)) return new BuddyApiError(detail)
      }
    } catch { /* Use the predictable status-specific message for malformed bodies. */ }
  }
  return new BuddyApiError(fallback)
}

export async function getBuddyConfig(signal: AbortSignal): Promise<BuddyConfig> {
  const response = await fetch(`${apiBase}/buddy/config`, { signal, headers: { Accept: 'application/json' } })
  if (!response.ok) throw await backendError(response, 'Chat mode could not be loaded. Check the backend connection and try again.')
  const data: unknown = await response.json()
  if (
    typeof data !== 'object' || data === null ||
    !('mode' in data) || !isMode(data.mode) ||
    !('name' in data) || data.name !== 'Way' ||
    !('max_message_length' in data) || typeof data.max_message_length !== 'number' ||
    !Number.isInteger(data.max_message_length) || data.max_message_length < 1 || data.max_message_length > 2000 ||
    !('ai_ready' in data) || typeof data.ai_ready !== 'boolean' ||
    !('setup_required' in data) || typeof data.setup_required !== 'boolean'
  ) throw new BuddyApiError('The backend returned an unexpected chat configuration. Please retry the connection.')
  return data as BuddyConfig
}

export async function sendBuddyMessage(
  messages: BuddyMessage[],
  feature: BuddyFeature | null,
  signal: AbortSignal,
  tripId: string | null = null,
  profileToken: string | null = null,
): Promise<BuddyReply> {
  const response = await fetch(`${apiBase}/buddy/chat`, {
    method: 'POST',
    signal,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...(profileToken ? { 'X-Profile-Token': profileToken } : {}) },
    body: JSON.stringify({ messages, feature, trip_id: tripId }),
  })
  if (!response.ok) {
    const fallback = response.status === 429
      ? 'Way is getting a lot of requests. Give it a moment, then retry your message.'
      : response.status === 408 || response.status === 504
        ? 'Way took too long to reply. Your draft is still here; please try again.'
        : response.status === 401 || response.status === 403
          ? 'Your account session could not be opened. Sign in again to discuss this trip.'
          : response.status === 503
            ? 'Way is unavailable right now. Check the backend connection, then retry your message.'
            : 'Way could not finish this reply. Your draft is still here so you can try again.'
    throw await backendError(response, fallback)
  }
  const data: unknown = await response.json()
  if (
    typeof data !== 'object' || data === null ||
    !('reply' in data) || typeof data.reply !== 'string' || !data.reply.trim() ||
    !('mode' in data) || !isMode(data.mode) ||
    !('proposal' in data) || (data.proposal !== null && (typeof data.proposal !== 'object' ||
      !('id' in data.proposal) || typeof data.proposal.id !== 'string' ||
      !('trip_id' in data.proposal) || typeof data.proposal.trip_id !== 'string' ||
      !('activities' in data.proposal) || !Array.isArray(data.proposal.activities)))
  ) throw new BuddyApiError('Way received an unexpected reply. Your draft is still here; please try again.')
  return data as BuddyReply
}

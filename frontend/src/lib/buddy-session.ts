import type { ItineraryProposal, ProposedActivity } from '@/features/planning'
import type { BuddyFeature, BuddyMessage } from './buddy-api'

export type ChatMessage = BuddyMessage & { id: number; proposal?: ItineraryProposal }
export type BuddyThread = {
  messages: ChatMessage[]
  draft: string
  feature: BuddyFeature | null
  restorePending: boolean
}

const STORAGE_KEY = 'triprescue.pip-threads.v1'
const MAX_STORAGE = 600000
const MAX_THREAD = 170000
const MAX_THREADS = 12
const features = new Set(['dream', 'memory', 'rescue', 'sidequest', 'harmony', 'split'])
const currencies = new Set(['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'INR'])
const itemTypes = new Set(['activity', 'food', 'transport', 'accommodation', 'other'])
type StoredThread = BuddyThread & { savedAt: number }
type SavedThreads = Record<string, StoredThread>

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function text(value: unknown, limit: number, minimum = 0): value is string {
  return typeof value === 'string' && value.length >= minimum && value.length <= limit
}

function money(value: unknown): value is string {
  return text(value, 20, 1) && /^-?\d{1,12}(?:\.\d{1,2})?$/.test(value)
}

function activity(value: unknown): value is ProposedActivity {
  return record(value) && text(value.date, 10, 10) && /^\d{4}-\d{2}-\d{2}$/.test(value.date)
    && Number.isFinite(Date.parse(`${value.date}T12:00:00`))
    && text(value.start_time, 5, 5) && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value.start_time)
    && text(value.end_time, 5, 5) && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value.end_time)
    && text(value.title, 160, 1) && text(value.description, 1200) && text(value.location, 200)
    && money(value.estimated_cost) && typeof value.item_type === 'string' && itemTypes.has(value.item_type)
}

function proposal(value: unknown, tripId: string | null): value is ItineraryProposal {
  return tripId !== null && record(value) && value.trip_id === tripId && text(value.id, 80, 1)
    && (value.status === 'pending' || value.status === 'approved' || value.status === 'rejected' || value.status === 'stale')
    && (value.mode === 'demo' || value.mode === 'openai' || value.mode === 'ollama') && typeof value.currency === 'string' && currencies.has(value.currency)
    && text(value.request, 2000, 1) && text(value.title, 160, 1) && text(value.summary, 1200, 1)
    && Array.isArray(value.activities) && value.activities.length <= 120 && value.activities.every(activity)
    && Array.isArray(value.notes) && value.notes.length <= 12 && value.notes.every((note) => text(note, 500))
    && money(value.estimated_total) && money(value.resulting_estimated_total) && money(value.remaining_budget)
    && text(value.created_at, 40, 1) && Number.isFinite(Date.parse(value.created_at))
    && (value.approved_at === null || (text(value.approved_at, 40, 1) && Number.isFinite(Date.parse(value.approved_at))))
    && (value.superseded_by === undefined || value.superseded_by === null || text(value.superseded_by, 80, 1))
}

function message(value: unknown, tripId: string | null): value is ChatMessage {
  return record(value) && Number.isSafeInteger(value.id) && Number(value.id) > 0
    && (value.role === 'user' || value.role === 'assistant') && text(value.content, 2000, 1)
    && (value.proposal === undefined || (value.role === 'assistant' && proposal(value.proposal, tripId)))
}

function emptyThread(): BuddyThread {
  return { messages: [], draft: '', feature: null, restorePending: true }
}

function readThreads(): Record<string, unknown> {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw || raw.length > MAX_STORAGE) return {}
    const stored: unknown = JSON.parse(raw)
    return record(stored) && stored.version === 1 && record(stored.threads) ? stored.threads : {}
  } catch { return {} }
}

function parseThread(value: unknown, tripId: string | null): StoredThread | null {
  if (!record(value) || !Array.isArray(value.messages) || value.messages.length > 40
    || !value.messages.every((item) => message(item, tripId)) || !text(value.draft, 2000)
    || !(value.feature === null || (typeof value.feature === 'string' && features.has(value.feature)))
    || typeof value.restorePending !== 'boolean' || typeof value.savedAt !== 'number' || !Number.isFinite(value.savedAt)) return null
  // Rebuild known fields so arbitrary cached properties never enter API history.
  return {
    messages: value.messages.map((item) => ({ id: item.id, role: item.role, content: item.content,
      ...(item.proposal ? { proposal: item.proposal } : {}) })),
    draft: value.draft, feature: value.feature as BuddyFeature | null,
    restorePending: value.restorePending, savedAt: value.savedAt,
  }
}

export function readBuddyThread(contextKey: string, tripId: string | null): BuddyThread {
  return parseThread(readThreads()[contextKey], tripId) ?? emptyThread()
}

export function saveBuddyThread(contextKey: string, tripId: string | null, thread: BuddyThread): void {
  try {
    const messages = thread.messages.slice(-40)
    const current = { ...thread, messages, savedAt: Date.now() }
    while (messages.length && JSON.stringify(current).length > MAX_THREAD) messages.shift()
    const checked = parseThread(current, tripId)
    if (!checked) return
    const saved: SavedThreads = {}
    for (const [key, candidate] of Object.entries(readThreads())) {
      // Keys are identifiers, never credentials. A guest cannot share a trip thread.
      if (!/^(?:[a-zA-Z0-9-]{1,80}):(?:[a-zA-Z0-9-]{1,80})$/.test(key)) continue
      const split = key.indexOf(':')
      const candidateTrip = key.slice(split + 1)
      const parsed = parseThread(candidate, candidateTrip === 'general' ? null : candidateTrip)
      if (parsed) saved[key] = parsed
    }
    saved[contextKey] = checked
    const ordered = Object.keys(saved).filter((key) => key !== contextKey).sort((a, b) => saved[a].savedAt - saved[b].savedAt)
    const serialize = () => JSON.stringify({ version: 1, threads: saved })
    while (ordered.length && (Object.keys(saved).length > MAX_THREADS || serialize().length > MAX_STORAGE)) delete saved[ordered.shift()!]
    sessionStorage.setItem(STORAGE_KEY, serialize())
  } catch { /* Chat still works when browser storage is denied or full. */ }
}

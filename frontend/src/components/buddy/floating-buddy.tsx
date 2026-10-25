import {
  createContext, useCallback, useContext, useEffect, useRef, useState,
  type CSSProperties, type KeyboardEvent, type ReactNode, type RefObject,
} from 'react'
import {
  ArrowUp, Check, ChevronDown, Compass, HeartHandshake, LoaderCircle,
  MessageCircle, Plus, RefreshCw, ShieldCheck, Sparkles, Split, WandSparkles,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTrips } from '@/features/trips'
import { ItineraryProposalCard, listItineraryProposals, type ItineraryProposal } from '@/features/planning'
import {
  BuddyApiError, getBuddyConfig, sendBuddyMessage,
  type BuddyConfig, type BuddyFeature, type BuddyMessage,
} from '@/lib/buddy-api'
import { readBuddyThread, saveBuddyThread, type ChatMessage } from '@/lib/buddy-session'
import './floating-buddy.css'
import { inclusiveDays } from '@/lib/planning-display'
import { formatMoney } from '@/features/trips/trips-api'

export type { BuddyFeature } from '@/lib/buddy-api'

type BuddyContextValue = {
  isOpen: boolean
  openBuddy: (prompt?: string, feature?: BuddyFeature) => void
  closeBuddy: () => void
  draft: string
  updateDraft: (value: string) => void
  feature: BuddyFeature | null
  chooseFeature: (feature: BuddyFeature | null) => void
  messages: ChatMessage[]
  pendingMessage: string | null
  sending: boolean
  send: (requestOverride?: string) => Promise<void>
  sendError: string | null
  newChat: () => void
  config: BuddyConfig | null
  configLoading: boolean
  configError: string | null
  retryConfig: () => void
  focusRequest: number
  launcherRef: RefObject<HTMLButtonElement | null>
  tripName: string | null
  tripContextPending: boolean
  clearTripContext: () => void
  availableTrips: { id: string; name: string }[]
  selectedTripId: string | null
  selectTripContext: (id: string | null) => void
  updateProposal: (messageId: number, proposal: ItineraryProposal) => void
  refreshSavedTrip: (tripId: string) => Promise<void>
}

const BuddyContext = createContext<BuddyContextValue | null>(null)

export const buddyStarters = [
  { feature: 'dream', label: 'Dream-to-Trip', prompt: 'Help me think through a peaceful five-day Japan trip with food, nature, and photography.', icon: WandSparkles },
  { feature: 'memory', label: 'Travel Buddy memory', prompt: 'I prefer quieter places and a relaxed morning. How would those preferences shape a trip?', icon: MessageCircle },
  { feature: 'rescue', label: 'Domino Rescue', prompt: 'My connecting flight was canceled. Help me understand what to check next.', icon: ShieldCheck },
  { feature: 'sidequest', label: 'SideQuest', prompt: 'I have 90 minutes free in Japan. Help me think of a small adventure for under $30.', icon: Compass },
  { feature: 'harmony', label: 'Group Harmony', prompt: 'Three friends love nature, anime, and food. How can we balance our different interests?', icon: HeartHandshake },
  { feature: 'split', label: 'SplitQuest', prompt: 'Some of us want shopping and others want a museum. Help us think through splitting up and meeting again.', icon: Split },
] satisfies { feature: BuddyFeature; label: string; prompt: string; icon: typeof Compass }[]

export function BuddyProvider({ children }: { children: ReactNode }) {
  const { profile, token, activeTrip, selectedTripId, selectTrip, trips, loadTrip, refreshTrips } = useTrips()
  const contextKey = profile ? `${profile.id}:${selectedTripId ?? 'general'}` : 'guest:general'
  const [initialThread] = useState(() => readBuddyThread(contextKey, profile ? selectedTripId : null))
  const [loadedContextKey, setLoadedContextKey] = useState(contextKey)
  const tripContextPending = (!!selectedTripId && activeTrip?.id !== selectedTripId) || loadedContextKey !== contextKey
  const [isOpen, setIsOpen] = useState(false)
  const [draft, setDraft] = useState(initialThread.draft)
  const [feature, setFeature] = useState<BuddyFeature | null>(initialThread.feature)
  const [messages, setMessages] = useState<ChatMessage[]>(initialThread.messages)
  const [pendingMessage, setPendingMessage] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const [config, setConfig] = useState<BuddyConfig | null>(null)
  const [configLoading, setConfigLoading] = useState(true)
  const [configError, setConfigError] = useState<string | null>(null)
  const [configAttempt, setConfigAttempt] = useState(0)
  const [focusRequest, setFocusRequest] = useState(0)
  const launcherRef = useRef<HTMLButtonElement>(null)
  const returnFocusRef = useRef<HTMLElement | null>(null)
  const openRef = useRef(false)
  const sendingRef = useRef(false)
  const activeRequestRef = useRef<AbortController | null>(null)
  const mountedRef = useRef(false)
  const nextMessageId = useRef(Math.max(0, ...initialThread.messages.map((message) => message.id)))
  const contextKeyRef = useRef(contextKey)
  const contextGeneration = useRef(0)
  const restorePendingRef = useRef(initialThread.restorePending)
  const restoreRevision = useRef(0)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false; activeRequestRef.current?.abort() }
  }, [])

  useEffect(() => {
    if (contextKeyRef.current === contextKey) return
    contextKeyRef.current = contextKey
    contextGeneration.current += 1
    activeRequestRef.current?.abort()
    activeRequestRef.current = null
    sendingRef.current = false
    setSending(false)
    setPendingMessage(null)
    const restored = readBuddyThread(contextKey, profile ? selectedTripId : null)
    restorePendingRef.current = restored.restorePending
    restoreRevision.current += 1
    nextMessageId.current = Math.max(nextMessageId.current, ...restored.messages.map((message) => message.id))
    setMessages(restored.messages)
    setDraft(restored.draft)
    setFeature(restored.feature)
    setLoadedContextKey(contextKey)
    setSendError(null)
  }, [contextKey, profile, selectedTripId])

  useEffect(() => {
    if (loadedContextKey !== contextKey) return
    saveBuddyThread(contextKey, profile ? selectedTripId : null, {
      messages, draft, feature, restorePending: restorePendingRef.current,
    })
  }, [contextKey, loadedContextKey, profile, selectedTripId, messages, draft, feature])

  useEffect(() => {
    if (!selectedTripId || !token || !profile) return
    const controller = new AbortController()
    const generation = contextGeneration.current
    const revision = restoreRevision.current
    listItineraryProposals(selectedTripId, token, controller.signal).then((proposals) => {
      if (controller.signal.aborted || generation !== contextGeneration.current || revision !== restoreRevision.current) return
      const pending = proposals.filter((proposal) => proposal.status === 'pending').slice(0, 3).reverse()
      setMessages((previous) => {
        const refreshed = previous.map((message) => {
          const current = message.proposal && proposals.find((proposal) => proposal.id === message.proposal?.id)
          return current ? { ...message, proposal: current } : message
        })
        if (!restorePendingRef.current) return refreshed
        return [...refreshed, ...pending.filter((proposal) => !refreshed.some((message) => message.proposal?.id === proposal.id)).map((proposal) => ({
          id: ++nextMessageId.current, role: 'assistant' as const, content: 'Here is a saved itinerary proposal you can review.', proposal,
        }))]
      })
    }).catch(() => { /* Chat remains available if proposal history cannot be loaded. */ })
    return () => controller.abort()
  }, [contextKey, selectedTripId, token, profile])

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const timer = window.setTimeout(() => controller.abort(), 8000)
    setConfigLoading(true)
    setConfigError(null)
    setConfig(null)
    getBuddyConfig(controller.signal)
      .then((result) => { if (active) setConfig(result) })
      .catch((error: unknown) => {
        if (active) setConfigError(error instanceof BuddyApiError ? error.message : 'Chat mode could not be loaded. Start the backend, then retry the connection.')
      })
      .finally(() => { window.clearTimeout(timer); if (active) setConfigLoading(false) })
    return () => { active = false; window.clearTimeout(timer); controller.abort() }
  }, [configAttempt])

  const openBuddy = useCallback((prompt?: string, requestedFeature?: BuddyFeature) => {
    if (!openRef.current) {
      returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    }
    openRef.current = true
    setIsOpen(true)
    if (prompt !== undefined && !sendingRef.current) {
      setDraft(prompt.slice(0, 2000))
      setFeature(requestedFeature ?? null)
      setSendError(null)
    }
    setFocusRequest((value) => value + 1)
  }, [])

  const closeBuddy = useCallback(() => {
    openRef.current = false
    setIsOpen(false)
    window.requestAnimationFrame(() => {
      const target = returnFocusRef.current
      if (target?.isConnected && target !== document.body) target.focus({ preventScroll: true })
      else launcherRef.current?.focus({ preventScroll: true })
    })
  }, [])

  useEffect(() => {
    if (!isOpen) return
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape' && !event.isComposing) { event.preventDefault(); closeBuddy() }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [isOpen, closeBuddy])

  const updateDraft = useCallback((value: string) => {
    if (sendingRef.current) return
    setDraft(value.slice(0, 2000))
    setSendError(null)
  }, [])

  const chooseFeature = useCallback((value: BuddyFeature | null) => {
    if (!sendingRef.current) setFeature(value)
  }, [])

  const newChat = useCallback(() => {
    if (sendingRef.current) return
    // Clearing a conversation does not reject a server draft, but it must not
    // immediately fill the cleared transcript again, including after refresh.
    restorePendingRef.current = false
    restoreRevision.current += 1
    setMessages([])
    setDraft('')
    setFeature(null)
    setSendError(null)
    setFocusRequest((value) => value + 1)
  }, [])

  const send = async (requestOverride?: string) => {
    const content = (requestOverride ?? draft).trim()
    if (sendingRef.current || configLoading || !config || !content || tripContextPending) return
    if (content.length > config.max_message_length) {
      setSendError(`Please keep your message under ${config.max_message_length.toLocaleString()} characters.`)
      return
    }
    sendingRef.current = true
    restoreRevision.current += 1
    setSending(true)
    setSendError(null)
    setPendingMessage(content)
    const controller = new AbortController()
    const generation = contextGeneration.current
    activeRequestRef.current = controller
    // Selected-trip requests may generate a full daily itinerary with meal stops.
    const timer = window.setTimeout(() => controller.abort(), config.mode === 'ollama' ? 300000 : selectedTripId ? 180000 : 60000)
    try {
      // Keep complete recent turns within the backend's context limits.
      // The displayed transcript remains intact for this visit.
      const history: BuddyMessage[] = [...messages.slice(-18).map(({ role, content: text }) => ({ role, content: text.trim().slice(0, 2000) })), { role: 'user', content }]
      while (history.reduce((total, message) => total + message.content.length, 0) > 12000) history.splice(0, 2)
      const result = await sendBuddyMessage(history, feature, controller.signal, selectedTripId, selectedTripId ? token : null)
      if (!mountedRef.current || generation !== contextGeneration.current) return
      setMessages((previous) => [...previous.map((message) => result.mode !== 'demo' && result.proposal && message.proposal?.status === 'pending'
        && message.proposal.trip_id === result.proposal.trip_id
        ? { ...message, proposal: { ...message.proposal, status: 'rejected' as const, superseded_by: result.proposal.id } }
        : message),
        { id: ++nextMessageId.current, role: 'user', content },
        { id: ++nextMessageId.current, role: 'assistant', content: result.reply, ...(result.proposal ? { proposal: result.proposal } : {}) },
      ])
      setConfig((previous) => previous ? { ...previous, mode: result.mode, ai_ready: result.mode !== 'demo', setup_required: result.mode === 'demo' } : previous)
      setDraft('')
      setFeature(null)
    } catch (error: unknown) {
      if (mountedRef.current && generation === contextGeneration.current) {
        setSendError(error instanceof BuddyApiError ? error.message : controller.signal.aborted
          ? 'Way took too long to reply. Your draft is still here; please try again.'
          : 'Way could not finish this reply. Check your connection and retry your message.')
      }
    } finally {
      window.clearTimeout(timer)
      if (generation === contextGeneration.current) {
        sendingRef.current = false
        activeRequestRef.current = null
        if (mountedRef.current) { setSending(false); setPendingMessage(null) }
      }
    }
  }

  return <BuddyContext.Provider value={{ isOpen, openBuddy, closeBuddy, draft: loadedContextKey === contextKey ? draft : '', updateDraft, feature, chooseFeature, messages: loadedContextKey === contextKey ? messages : [], pendingMessage, sending, send, sendError, newChat, config, configLoading, configError, retryConfig: () => setConfigAttempt((value) => value + 1), focusRequest, launcherRef, tripName: activeTrip?.id === selectedTripId ? activeTrip.name : null, tripContextPending, clearTripContext: () => selectTrip(null), availableTrips: trips.map(({ id, name }) => ({ id, name })), selectedTripId, selectTripContext: selectTrip, updateProposal: (messageId, proposal) => setMessages((previous) => previous.map((message) => message.id === messageId ? { ...message, proposal } : message)), refreshSavedTrip: async (tripId) => { await loadTrip(tripId); await refreshTrips() } }}>{children}</BuddyContext.Provider>
}

export function useBuddy() {
  const buddy = useContext(BuddyContext)
  if (!buddy) throw new Error('useBuddy must be used inside BuddyProvider.')
  return buddy
}

export function BuddyAvatar({ className = '' }: { className?: string }) {
  return <span className={`pip-avatar ${className}`} aria-hidden="true">
    <span className="pip-shadow" /><span className="pip-backpack"><span /></span>
    <span className="pip-foot pip-foot-left" /><span className="pip-foot pip-foot-right" />
    <span className="pip-arm pip-arm-left" /><span className="pip-arm pip-arm-right" />
    <span className="pip-leaf pip-leaf-left" /><span className="pip-leaf pip-leaf-right" />
    <span className="pip-body"><span className="pip-face"><span className="pip-eye pip-eye-left" /><span className="pip-eye pip-eye-right" /><span className="pip-cheek pip-cheek-left" /><span className="pip-cheek pip-cheek-right" /><span className="pip-smile" /></span><span className="pip-scarf" /></span>
  </span>
}

function StarterPrompts() {
  const { openBuddy, sending } = useBuddy()
  return <div className="pip-starters">{buddyStarters.map(({ feature, label, prompt, icon: Icon }) => <button type="button" key={feature} aria-label={label} disabled={sending} onClick={() => openBuddy(prompt, feature)}><Icon size={15} /><span>{label}</span><span className="pip-starter-arrow" aria-hidden="true">↗</span></button>)}</div>
}

function ChatText({ content }: { content: string }) {
  // Render common model emphasis as React text nodes; HTML remains escaped.
  return <>{content.split(/(\*\*[^*\n]+\*\*|`[^`\n]+`)/g).map((part, index) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={index}>{part.slice(2, -2)}</strong>
      : part.startsWith('`') && part.endsWith('`') ? <code key={index}>{part.slice(1, -1)}</code>
        : part,
  )}</>
}

function ChatMode() {
  const { config, configLoading } = useBuddy()
  return <span className={`pip-mode ${config?.ai_ready ? 'pip-mode-live' : ''}`} role="status"><span />{configLoading ? 'Checking chat mode' : !config ? 'Chat unavailable' : config.mode === 'demo' ? 'Demo mode · not live AI' : config.mode === 'ollama' ? config.ai_ready ? 'Local AI · no API key' : 'Local AI needs to start' : config.ai_ready ? 'AI configured' : 'AI setup required'}</span>
}

export function FloatingBuddy() {
  const buddy = useBuddy()
  const { token, activeTrip, selectedTripId } = useTrips()
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const transcriptRef = useRef<HTMLDivElement>(null)
  const lastScrolledMessage = useRef<number | null>(null)
  const [viewport, setViewport] = useState({ height: window.visualViewport?.height ?? window.innerHeight, top: window.visualViewport?.offsetTop ?? 0 })

  useEffect(() => {
    const viewport = window.visualViewport
    const updateViewport = () => setViewport({ height: viewport?.height ?? window.innerHeight, top: viewport?.offsetTop ?? 0 })
    viewport?.addEventListener('resize', updateViewport)
    viewport?.addEventListener('scroll', updateViewport)
    window.addEventListener('resize', updateViewport)
    return () => { viewport?.removeEventListener('resize', updateViewport); viewport?.removeEventListener('scroll', updateViewport); window.removeEventListener('resize', updateViewport) }
  }, [])

  useEffect(() => {
    if (buddy.isOpen) textareaRef.current?.focus({ preventScroll: true })
  }, [buddy.isOpen, buddy.focusRequest])

  useEffect(() => {
    const transcript = transcriptRef.current
    if (!buddy.isOpen || !transcript) return
    const latest = buddy.messages.at(-1)
    if (latest?.proposal && latest.id !== lastScrolledMessage.current && !buddy.pendingMessage && !buddy.sendError) {
      const target = transcript.querySelector(`[data-message-id="${latest.id}"] .itinerary-proposal`) ?? transcript.querySelector(`[data-message-id="${latest.id}"]`)
      if (target) transcript.scrollTop += target.getBoundingClientRect().top - transcript.getBoundingClientRect().top - 4
    } else if (!latest?.proposal || buddy.pendingMessage || buddy.sendError) {
      transcript.scrollTop = transcript.scrollHeight
    }
    lastScrolledMessage.current = latest?.id ?? null
  }, [buddy.isOpen, buddy.messages, buddy.pendingMessage, buddy.sendError])

  const onComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
      event.preventDefault()
      void buddy.send()
    }
  }

  const selectedStarter = buddyStarters.find((starter) => starter.feature === buddy.feature)
  const canSend = !!buddy.config && !buddy.configLoading && !buddy.sending && !buddy.tripContextPending && !!buddy.draft.trim()
  const viewportStyle = { '--pip-viewport-height': `${viewport.height}px`, '--pip-viewport-top': `${viewport.top}px` } as CSSProperties

  return <div className="pip-widget" style={viewportStyle}>
    <button ref={buddy.launcherRef} type="button" className={`pip-launcher ${buddy.isOpen ? 'pip-launcher-open' : ''}`} aria-label="Chat with Way" aria-haspopup="dialog" aria-expanded={buddy.isOpen} aria-controls={buddy.isOpen ? 'pip-chat-panel' : undefined} onClick={() => buddy.isOpen ? buddy.closeBuddy() : buddy.openBuddy()}>
      <span className="pip-launcher-label">Chat with Way<Sparkles size={12} /></span><BuddyAvatar />
    </button>

    {buddy.isOpen && <section id="pip-chat-panel" className="pip-chat-panel" role="dialog" aria-labelledby="pip-chat-title" aria-describedby="pip-chat-capability">
      <header className="pip-chat-header"><div className="pip-header-avatar"><BuddyAvatar /></div><div className="pip-header-heading"><h2 id="pip-chat-title">Way, your travel buddy</h2><p>A little company for the journey.</p></div><button type="button" className="pip-icon-button" aria-label="Minimize chat" title="Minimize chat" onClick={buddy.closeBuddy}><ChevronDown size={20} /></button></header>
      <div className="pip-chat-toolbar"><ChatMode /><button type="button" className="pip-new-chat" onClick={buddy.newChat} disabled={buddy.sending}><Plus size={13} /> New chat</button></div>

      <div className="pip-trip-context">
        {buddy.tripContextPending ? <><span role="status">Loading selected trip…</span><button type="button" onClick={buddy.clearTripContext}>General chat</button></>
          : buddy.tripName ? <><span title={buddy.tripName}>Discussing: <strong>{buddy.tripName}</strong></span><button type="button" onClick={buddy.clearTripContext}>General chat</button></>
          : <><span>General travel chat</span><Link to="/trips" onClick={buddy.closeBuddy}>Choose a saved trip ↗</Link></>}
      </div>
      {buddy.availableTrips.length > 0 && <label className="pip-trip-picker">Plan for<select aria-label="Trip for itinerary" value={buddy.selectedTripId ?? ''} onChange={(event) => buddy.selectTripContext(event.target.value || null)}><option value="">General travel chat</option>{buddy.availableTrips.map((trip) => <option key={trip.id} value={trip.id}>{trip.name}</option>)}</select></label>}
      {activeTrip?.id === selectedTripId && <details className="pip-saved-facts"><summary>Saved trip facts · {inclusiveDays(activeTrip.start_date, activeTrip.end_date)} calendar days</summary><p>{activeTrip.destination} · from {activeTrip.departure_location || 'departure city not supplied'}<br />{activeTrip.start_date} through {activeTrip.end_date}, inclusive · {activeTrip.travelers} travelers<br />{formatMoney(activeTrip.budget, activeTrip.currency)} whole-group budget · {formatMoney(activeTrip.remaining_budget, activeTrip.currency)} remaining in listed estimates<br />Flight arrival/departure times unknown. Prices and routes need checking.</p></details>}
      <Link className="pip-rescue-link" to={buddy.selectedTripId ? `/trips/${buddy.selectedTripId}/rescue` : '/rescue'} onClick={buddy.closeBuddy}><ShieldCheck size={14} /> Domino Rescue <span>Compare a simulated trip repair ↗</span></Link>

      {buddy.config?.setup_required && (buddy.config.mode === 'openai'
        ? <details className="pip-ai-setup"><summary>Connect AI for personalized ideas</summary><p>The cloud provider needs private setup. Run this from the project folder:</p><code>.\backend\.venv\Scripts\python.exe .\backend\configure_ai.py</code><p>Enter your key privately, restart the backend, then check the connection.</p><button type="button" onClick={buddy.retryConfig}>Check AI connection</button></details>
        : <details className="pip-ai-setup"><summary>{buddy.config.mode === 'ollama' ? 'Start your free local AI' : 'Use free local AI for personalized ideas'}</summary><p>Local AI runs on this computer without an API key or AI usage fees. Run this from the project folder:</p><code>powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-local-ai.ps1</code>{buddy.config.mode === 'demo' && <><p>To select the local provider, also run:</p><code>.\backend\.venv\Scripts\python.exe .\backend\configure_local_ai.py</code><p>Restart the backend after changing the provider.</p></>}<p>The model must be downloaded first. Local replies can take longer while the model starts.</p><button type="button" onClick={buddy.retryConfig}>Check local AI</button></details>)}

      {buddy.configError && <div className="pip-config-error" role="alert"><p>{buddy.configError}</p><button type="button" disabled={buddy.configLoading} onClick={buddy.retryConfig}><RefreshCw size={13} /> Retry connection</button></div>}

      <div ref={transcriptRef} className="pip-chat-transcript" role="log" aria-label="Conversation with Way" aria-live="polite" aria-relevant="additions text">
        {buddy.messages.length === 0 && !buddy.pendingMessage && <div className="pip-welcome"><span className="pip-welcome-eyebrow"><Sparkles size={13} /> A GOOD PLACE TO START</span><h3>Hey, I’m Way.<br />Where are we headed?</h3><p>Tell me what’s on your mind, or pick an idea to start with. You can edit it before sending.</p><StarterPrompts /></div>}
        {buddy.messages.map((message) => <div key={message.id} data-message-id={message.id} className={`pip-message pip-message-${message.role}`}><span className="pip-message-author">{message.role === 'assistant' ? 'Way' : 'You'}</span><p>{message.role === 'assistant' ? <ChatText content={message.content} /> : message.content}</p>{message.proposal && token && <ItineraryProposalCard proposal={message.proposal} profileToken={token} onUpdated={(proposal) => buddy.updateProposal(message.id, proposal)} onApplied={(trip) => buddy.refreshSavedTrip(trip.id)} onRegenerate={() => { void buddy.send(`Suggest a different itinerary for this trip. ${message.proposal?.request ?? ''}`.slice(0, 2000)) }} regenerating={buddy.sending} />}</div>)}
        {buddy.pendingMessage && <><div className="pip-message pip-message-user pip-message-pending"><span className="pip-message-author">You · sending</span><p>{buddy.pendingMessage}</p></div><div className="pip-thinking" role="status"><span /><span /><span /><span className="pip-sr-only">Way is thinking</span></div></>}
        {buddy.sendError && <div className="pip-send-error" role="alert"><p>{buddy.sendError}</p><button type="button" onClick={() => void buddy.send()} disabled={!canSend}><RefreshCw size={13} /> Retry message</button></div>}
      </div>

      {buddy.messages.length > 0 && <details className="pip-more-ideas"><summary><Sparkles size={12} /> Explore all six ideas</summary><StarterPrompts /></details>}

      <form className="pip-composer" onSubmit={(event) => { event.preventDefault(); void buddy.send() }}>
        {selectedStarter && <div className="pip-feature-context"><Check size={12} /><span>{selectedStarter.label}</span><button type="button" aria-label="Clear feature context" disabled={buddy.sending} onClick={() => buddy.chooseFeature(null)}>Clear</button></div>}
        <div className="pip-input-wrap"><label className="pip-sr-only" htmlFor="pip-message-input">Your message to Way</label><textarea id="pip-message-input" ref={textareaRef} value={buddy.draft} onChange={(event) => buddy.updateDraft(event.target.value)} onKeyDown={onComposerKeyDown} readOnly={buddy.sending} maxLength={buddy.config?.max_message_length ?? 2000} placeholder="A place, a feeling, a little travel question…" rows={2} aria-describedby="pip-message-help" /><button type="submit" className="pip-send-button" aria-label="Send message" title="Send message" disabled={!canSend}>{buddy.sending ? <LoaderCircle size={18} className="pip-spinner" /> : <ArrowUp size={19} />}</button></div>
        <div id="pip-message-help" className="pip-composer-help"><span>Enter to send · Shift + Enter for a new line</span><span>{buddy.draft.length.toLocaleString()} / {(buddy.config?.max_message_length ?? 2000).toLocaleString()}</span></div>
      </form>
      <p id="pip-chat-capability" className="pip-capability">Chat stays in this tab. New chat clears it.<br />Suggestions need your approval before saving.</p>
    </section>}
  </div>
}

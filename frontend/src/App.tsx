import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, NavLink, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import {
  ArrowRight, ArrowUpRight, Check, ChevronRight, Compass, ExternalLink,
  HeartHandshake, LayoutDashboard, Map, MapPin, Menu, MessageCircle, Mountain,
  RefreshCw, Route as RouteIcon, Settings, ShieldCheck, Sparkles,
  Split, Sprout, Users, WandSparkles, X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { getHealth, type HealthResponse } from '@/lib/api'
import { BuddyAvatar, BuddyProvider, FloatingBuddy, useBuddy, type BuddyFeature } from '@/components/buddy/floating-buddy'
import { DashboardTrips, MyTripsPage, ProfileSettings, TripDetailPage, TripsProvider, useTrips } from '@/features/trips'
import { RescuePage } from '@/features/rescue/rescue-page'
import { TravelerSettings } from '@/features/traveler/traveler-settings'
import { RealTravelPage } from '@/features/traveler/real-travel-page'
import { AccountPage, AccountSettings } from '@/features/accounts/account-page'

type Connection = {
  loading: boolean
  health: HealthResponse | null
  error: string | null
  refresh: () => void
}

const ConnectionContext = createContext<Connection | null>(null)

function ConnectionProvider({ children }: { children: ReactNode }) {
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<Omit<Connection, 'refresh'>>({ loading: true, health: null, error: null })

  useEffect(() => {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 8000)
    let active = true
    setState({ loading: true, health: null, error: null })
    getHealth(controller.signal)
      .then((health) => { if (active) setState({ loading: false, health, error: null }) })
      .catch(() => {
        if (active) setState({ loading: false, health: null, error: 'We couldn’t reach the backend. Check that it is running, then try again.' })
      })
      .finally(() => window.clearTimeout(timeout))
    return () => { active = false; window.clearTimeout(timeout); controller.abort() }
  }, [attempt])

  return (
    <ConnectionContext.Provider value={{ ...state, refresh: () => setAttempt((value) => value + 1) }}>
      {children}
    </ConnectionContext.Provider>
  )
}

function useConnection() {
  const value = useContext(ConnectionContext)
  if (!value) throw new Error('ConnectionProvider is required.')
  return value
}

function Brand() {
  return <Link className="brand" to="/" aria-label="Wayva home"><span className="brand-mark"><img src="/wayva-mark.svg" alt="" width="36" height="36" /></span>Wayva<span className="brand-dot">.</span></Link>
}

function ScrollToPage() {
  const { pathname, hash } = useLocation()
  const previousPath = useRef(pathname)
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'instant' })
    else window.scrollTo({ top: 0, behavior: 'instant' })
    if (previousPath.current !== pathname && !hash) {
      const main = document.getElementById('main-content')
      main?.setAttribute('tabindex', '-1')
      main?.focus({ preventScroll: true })
    }
    previousPath.current = pathname
  }, [pathname, hash])
  return null
}

function SiteHeader() {
  const { accountUsername } = useTrips()
  const [open, setOpen] = useState(false)
  const { openBuddy } = useBuddy()
  const location = useLocation()
  useEffect(() => setOpen(false), [location])
  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Brand />
        <nav className="desktop-nav" aria-label="Main navigation">
          <NavLink className="trips-nav-link" to="/trips"><Map size={14} /> My Trips</NavLink>
          <Link to="/#experience">The experience</Link>
          <Link to="/#how-it-works">How it works</Link>
          <NavLink to="/dashboard">Workspace <ArrowUpRight size={13} /></NavLink>
        </nav>
        <Link className="header-trips-shortcut" to="/trips"><Map size={14} /> My Trips</Link>
        <Link className="header-account-link" to="/account" title={accountUsername ?? undefined}>{accountUsername ? `Account: ${accountUsername}` : 'Sign in'}</Link><div className="header-actions"><span className="preview-label"><span /> Your companion, a click away</span><Button className="header-cta" onClick={() => openBuddy()}>Talk to Way <MessageCircle size={16} /></Button></div>
        <Button className="mobile-menu-button" variant="ghost" size="icon" onClick={() => setOpen(!open)} aria-label={open ? 'Close navigation' : 'Open navigation'} aria-expanded={open} aria-controls="mobile-navigation">{open ? <X /> : <Menu />}</Button>
      </div>
      {open && <nav id="mobile-navigation" className="mobile-nav" aria-label="Mobile navigation"><NavLink to="/account">{accountUsername ? 'My Account' : 'Sign in / Create account'} <ShieldCheck size={16} /></NavLink><NavLink to="/trips">My Trips <Map size={16} /></NavLink><Link to="/#experience">The experience</Link><Link to="/#how-it-works">How it works</Link><Link to="/dashboard">Open workspace <ArrowUpRight size={16} /></Link></nav>}
    </header>
  )
}

const features = [
  { id: 'dream', prompt: 'Help me think through my dream trip.', name: 'Dream-to-Trip', title: 'Start with a feeling. Find your somewhere.', text: 'An itinerary shaped around what you love, the time you have, and the way you like to travel.', icon: WandSparkles, phase: 'AI trip planning' },
  { id: 'memory', prompt: 'How can you remember my travel preferences?', name: 'Travel Buddy', title: 'A companion that gets your kind of trip.', text: 'A conversation that carries your preferences and trip context along for the journey.', icon: MessageCircle, phase: 'Personal memory' },
  { id: 'rescue', prompt: 'My flight was canceled. Help me think through what to do next.', name: 'Domino Rescue', title: 'When plans change, find a way forward.', text: 'See how a disruption affects your trip and review a recovery plan before anything changes.', icon: ShieldCheck, phase: 'Trip recovery' },
  { id: 'sidequest', prompt: 'I have 90 minutes free. Help me think of a little adventure.', name: 'SideQuest', title: 'Leave a little room for the unexpected.', text: 'Turn a free afternoon into a small adventure that fits your interests, time, and budget.', icon: Compass, phase: 'Spontaneous adventures' },
  { id: 'harmony', prompt: 'Our group has different interests. Help us find common ground.', name: 'Group Harmony', title: 'Different people. One great adventure.', text: 'Find common ground across everyone’s interests, pace, and budget, with the tradeoffs explained.', icon: HeartHandshake, phase: 'Group planning' },
  { id: 'split', prompt: 'Help our group explore separately and meet back up later.', name: 'SplitQuest', title: 'Go your own way. Meet back for the stories.', text: 'Explore in smaller groups with separate plans and a practical time and place to reunite.', icon: Split, phase: 'Shared journeys' },
]

function LandingPage() {
  const [selected, setSelected] = useState(0)
  const { openBuddy } = useBuddy()
  const feature = features[selected]
  const FeatureIcon = feature.icon
  return (
    <>
      <main id="main-content">
        <section className="hero page-width" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow"><span className="tiny-spark"><Sparkles size={14} /></span> WAYVA / A WORLD OF POSSIBILITY</p>
            <h1 id="hero-title">Your journey,<br /><span className="serif-word">reimagined.</span></h1>
            <p className="hero-description">Meet Way, your AI travel companion. Shape your next adventure, explore the possibilities, and find a way forward when plans change.</p>
            <div className="hero-actions"><Button size="lg" className="primary-link" onClick={() => openBuddy()}>Meet your travel buddy <MessageCircle size={18} /></Button><Link className="text-link" to="/trips">My Trips <ArrowUpRight size={15} /></Link></div>
            <div className="hero-footnote"><span className="footnote-line" /><span>One little companion, wherever you browse.<br /><strong>Look for Way in the corner.</strong></span></div>
          </div>
          <div className="hero-visual-wrap">
          <span className="journal-edition" aria-hidden="true"><span /> FIELD NOTES / A WORLD OF POSSIBILITY</span>
          <figure className="hero-visual">
            <img src="/images/mount-fuji.jpg" alt="Mount Fuji reflected in the peaceful waters of Lake Kawaguchi in Japan" width="1600" height="1067" fetchPriority="high" />
            <div className="photo-topline"><span><MapPin size={13} /> A little inspiration</span><span className="photo-compass"><Compass size={24} strokeWidth={1.2} /></span></div>
            <figcaption className="photo-caption"><span className="photo-caption-kicker">FIND YOUR KIND OF SOMEWHERE</span><span className="photo-caption-title">The world can wait.<br />This moment can’t.</span><span className="photo-place"><MapPin size={14} /> Lake Kawaguchi, Japan</span></figcaption>
            <div className="photo-index"><span>01</span><span className="photo-index-line" /><span>INSPIRATION</span></div>
          </figure>
          <div className="photo-field-note" aria-hidden="true"><span className="field-note-icon"><Mountain size={23} strokeWidth={1.4} /></span><span><small>A LITTLE INSPIRATION</small><strong>Leave room for wonder.</strong></span><svg className="field-note-route" viewBox="0 0 75 33" fill="none"><path d="M4 25C19 25 12 5 30 9S41 30 54 20s10-15 17-15" stroke="currentColor" strokeWidth="1.3" strokeDasharray="3 3" /><circle cx="4" cy="25" r="2.5" fill="currentColor" /><circle cx="71" cy="5" r="3" stroke="currentColor" /></svg></div>
          </div>
        </section>

        <section className="values-strip page-width" aria-label="Our approach">
          <div><Sprout size={21} /><span>More you.<small>Plans with personality.</small></span></div>
          <div><Users size={21} /><span>More together.<small>Everyone in the picture.</small></span></div>
          <div><RouteIcon size={21} /><span>More possibilities.<small>Room to change course.</small></span></div>
          <p>Good trips aren’t just planned.<br /><span>They’re lived.</span></p>
        </section>

        <section id="experience" className="experience-section page-width" aria-labelledby="experience-title">
          <div className="section-heading"><div><p className="eyebrow">ALL THROUGH YOUR BUDDY</p><h2 id="experience-title">One companion.<br /><span className="serif-word">So many ways to go.</span></h2></div><p>A buddy to plan with. A way to bounce back.<br /><span className="development-note">Try Domino Rescue’s connected recovery demo.</span></p></div>
          <div className="experience-grid">
            <div className="feature-selector" role="tablist" aria-label="Planned Wayva features" aria-orientation="vertical">
              {features.map((item, index) => {
                const Icon = item.icon
                return <button key={item.name} id={`feature-tab-${index}`} role="tab" aria-selected={selected === index} aria-controls="feature-panel" tabIndex={selected === index ? 0 : -1} className={`feature-tab ${selected === index ? 'selected' : ''}`} onClick={() => setSelected(index)} onKeyDown={(event) => {
                  const next = event.key === 'ArrowDown' ? (index + 1) % features.length : event.key === 'ArrowUp' ? (index - 1 + features.length) % features.length : event.key === 'Home' ? 0 : event.key === 'End' ? features.length - 1 : null
                  if (next !== null) { event.preventDefault(); setSelected(next); document.getElementById(`feature-tab-${next}`)?.focus() }
                }}><span className="feature-number">0{index + 1}</span><Icon size={18} /><span>{item.name}</span><ArrowUpRight className="feature-arrow" size={17} /></button>
              })}
            </div>
            <div className="feature-panel" id="feature-panel" role="tabpanel" aria-labelledby={`feature-tab-${selected}`} tabIndex={0}>
              <div className="feature-panel-top"><span className="feature-chip"><FeatureIcon size={15} /> {feature.phase}</span><span className="future-tag">{feature.id === 'rescue' ? 'WORKING SIMULATION' : feature.id === 'dream' ? 'TRY WITH WAY' : 'COMING LATER'}</span></div>
              <div className="feature-illustration" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit orbit-three" /><span className="orbit-stop stop-one"><MapPin size={20} /></span><span className="orbit-stop stop-two"><Mountain size={21} /></span><span className="orbit-stop stop-three"><Sparkles size={18} /></span><span className="orbit-center"><FeatureIcon size={35} strokeWidth={1.5} /></span></div>
              <h3>{feature.title}</h3><p>{feature.text}</p>{feature.id === 'rescue' ? <Link className="text-link feature-chat-link" to="/rescue">Try Domino Rescue <ShieldCheck size={16} /></Link> : <button className="text-link feature-chat-link" onClick={() => openBuddy(feature.prompt, feature.id as BuddyFeature)}>Talk to Way about this <MessageCircle size={16} /></button>}
            </div>
          </div>
        </section>

        <section id="how-it-works" className="how-section" aria-labelledby="how-title"><div className="page-width"><div className="section-heading"><div><p className="eyebrow">THE JOURNEY WE’RE BUILDING</p><h2 id="how-title">Less back and forth.<br /><span className="serif-word">More out and about.</span></h2></div><span className="outline-label">You always have the final say.</span></div><ol className="journey-steps"><li><span>01 / DREAM</span><h3>Tell us your kind of trip.</h3><p>The big ideas, the small preferences, and the people coming along.</p></li><li><span>02 / SHAPE</span><h3>Make the plan your own.</h3><p>Review the suggestions, find your balance, and choose what feels right.</p></li><li><span>03 / GO</span><h3>Leave space for the good stuff.</h3><p>A spontaneous detour. A shared discovery. A new way forward.</p></li></ol></div></section>
        <section className="closing-section page-width"><span className="closing-mark"><img src="/wayva-mark.svg" alt="" width="48" height="48" /></span><h2>Every good story<br />starts with <span className="serif-word">a hello.</span></h2><p>Your little travel companion is right here.</p><Button size="lg" className="primary-link" onClick={() => openBuddy()}>Say hello to Way <MessageCircle size={18} /></Button></section>
      </main>
      <Footer />
    </>
  )
}

function Footer() {
  return <footer className="site-footer page-width"><div><Brand /><p>Your journey, reimagined.</p></div><div className="footer-right"><Link to="/settings">Connection & settings <ArrowUpRight size={13} /></Link><span>University hackathon · Your buddy, a click away</span><a href="https://unsplash.com/photos/J_7o0_1S-PM" target="_blank" rel="noreferrer">Photography by Alberto Gallego / Unsplash <ExternalLink size={11} /></a></div></footer>
}

const workspaceLinks = [
  { path: '/dashboard', label: 'Overview', icon: LayoutDashboard },
  { path: '/trips', label: 'My Trips', icon: Map },
  { path: '/rescue', label: 'Domino Rescue', icon: ShieldCheck },
  { path: '/buddy', label: 'AI Travel Buddy', icon: MessageCircle },
  { path: '/explore', label: 'Explore / SideQuest', icon: Compass },
  { path: '/groups', label: 'Groups', icon: Users },
  { path: '/account', label: 'My Account', icon: ShieldCheck },
  { path: '/settings', label: 'Settings', icon: Settings },
]

function ConnectionPill() {
  const { loading, health } = useConnection()
  return <span className={`connection-pill ${health ? 'connected' : loading ? 'checking' : 'offline'}`} role="status"><span />{loading ? 'Checking connection' : health ? 'Backend connected' : 'Backend unavailable'}</span>
}

function WorkspaceLayout() {
  return <div className="workspace-layout"><aside className="workspace-sidebar"><div className="sidebar-label">YOUR TRAVEL JOURNAL</div><nav aria-label="Workspace navigation">{workspaceLinks.map(({ path, label, icon: Icon }) => <NavLink to={path} key={path}><Icon size={18} /><span>{label}</span><ChevronRight size={14} /></NavLink>)}</nav><div className="sidebar-note"><MessageCircle size={20} /><strong>Your buddy comes along.</strong><p>Click Way in the corner to keep the conversation going while you explore.</p><Link to="/buddy">Meet your travel buddy <ArrowUpRight size={13} /></Link></div><Link className="sidebar-home" to="/">Back to the beginning <ArrowUpRight size={14} /></Link></aside><main id="main-content" className="workspace-main"><div className="workspace-topline"><span className="eyebrow">WAYVA / YOUR NEXT CHAPTER</span><ConnectionPill /></div><Outlet /></main></div>
}

function DashboardPage() {
  return <>
    <div className="workspace-heading"><p className="eyebrow">WELCOME TO YOUR NEXT CHAPTER</p><h1>A world of possibilities.<br /><span className="serif-word">A home for your plans.</span></h1><p>Save a journey, shape your days, and bring Way into the conversation.</p></div>
    <DashboardTrips />
    <section className="next-up"><div><span className="eyebrow">YOUR TRAVEL COMPANION</span><h2>A little company, wherever you’re headed.</h2></div><div className="next-up-links">{[{ to: '/buddy', icon: MessageCircle, label: 'Talk to your Travel Buddy', text: 'Way can read the trip you select.' }, { to: '/explore', icon: Compass, label: 'A little more exploration', text: 'SideQuest is coming in a future phase.' }, { to: '/groups', icon: Users, label: 'Better with your people', text: 'Group planning is coming later.' }].map(({ to, icon: Icon, label, text }) => <Link key={to} to={to}><Icon size={21} /><span><strong>{label}</strong><small>{text}</small></span><ArrowUpRight size={17} /></Link>)}</div></section>
    <section className="connection-card dashboard-connection"><span className="eyebrow">APPLICATION CONNECTION</span><h2>Made to connect.</h2><p>A live check of the backend and SQLite connection.</p><ConnectionDetails compact /><Link className="text-link" to="/settings">Connection details <ArrowUpRight size={15} /></Link></section>
  </>
}

function ConnectionDetails({ compact = false }: { compact?: boolean }) {
  const { loading, health, error, refresh } = useConnection()
  return <div className="connection-details" aria-live="polite" aria-busy={loading}><dl><div><dt>API service</dt><dd>{loading ? 'Checking…' : health ? <><Check size={14} /> Available</> : 'Unavailable'}</dd></div><div><dt>SQLite database</dt><dd>{loading ? 'Checking…' : health ? <><Check size={14} /> Connected</> : 'Not verified'}</dd></div>{!compact && <div><dt>API version</dt><dd>{health?.version ?? '—'}</dd></div>}</dl>{error && <p className="connection-error" role="alert">{error}</p>}<Button variant="outline" size="sm" onClick={refresh} disabled={loading}><RefreshCw size={14} className={loading ? 'is-spinning' : ''} />{loading ? 'Checking…' : 'Check again'}</Button></div>
}

const comingPages = {
  explore: { label: 'EXPLORE / SIDEQUEST', title: 'Take the scenic detour.', text: 'SideQuest will turn spare time into a mini-adventure, using your location, interests, schedule, and spending limit.', icon: Compass, items: ['Find activities that fit your free time', 'Review stops and estimated costs', 'Approve an adventure for your itinerary'] },
  groups: { label: 'GROUPS', title: 'Your people. All on the same page.', text: 'Group Harmony and SplitQuest will help balance everyone’s wishes, explore separately when it makes sense, and bring you back together.', icon: Users, items: ['Bring group interests and budgets together', 'Understand the compromises in a shared plan', 'Explore in subgroups with a reunion plan'] },
}

function ComingPage({ page }: { page: keyof typeof comingPages }) {
  const data = comingPages[page]
  const Icon = data.icon
  const { openBuddy } = useBuddy()
  const feature = features.find((item) => item.id === (page === 'explore' ? 'sidequest' : 'harmony'))!
  return <><div className="workspace-heading"><p className="eyebrow">{data.label}</p><h1>{data.title}</h1><p>{data.text}</p></div><section className="coming-page"><div className="coming-illustration"><Icon size={52} strokeWidth={1.1} /><span><Sprout size={20} /></span></div><span className="status-label">TRAVEL TOOLS COMING LATER</span><h2>A little more growing to do.</h2><p>You can talk through your ideas with Way now. These connected travel tools will be added in a later phase.</p><ul>{data.items.map((item) => <li key={item}><span /><span>{item}</span></li>)}</ul><div className="coming-page-actions"><Button onClick={() => openBuddy(feature.prompt, feature.id as BuddyFeature)}>Talk it through with Way <MessageCircle size={16} /></Button><Link className="text-link" to="/dashboard">Back to your overview <ArrowRight size={14} /></Link></div></section></>
}

function BuddyPage() {
  const { openBuddy } = useBuddy()
  return <>
    <div className="workspace-heading"><p className="eyebrow">YOUR AI TRAVEL BUDDY</p><h1>A little companion.<br /><span className="serif-word">A world to talk about.</span></h1><p>Your ideas, questions, and what-ifs all start with the same little buddy. Way stays with you on every page.</p></div>
    <section className="buddy-home-card" aria-labelledby="meet-pip-title">
      <div className="buddy-home-portrait"><BuddyAvatar /></div>
      <span className="status-label">A HELLO IS ALL IT TAKES</span>
      <h2 id="meet-pip-title">Hi, I’m Way. Where are we headed?</h2>
      <p>Click me in the corner to open our chat. We can talk through a dream trip, a group adventure, a little detour, or a change of plans.</p>
      <Button onClick={() => openBuddy()} className="primary-link">Open a conversation <MessageCircle size={17} /></Button>
      <div className="buddy-home-note"><ShieldCheck size={16} /><span>Select a saved trip and ask Way for an itinerary. Review the suggested activities, then approve to save. Local AI runs through Ollama without an API key. Private traveler settings and manual Real Travel assistance are available; live rebooking and long-term preference memory are not connected.</span></div>
    </section>
  </>
}

function SettingsPage() {
  return <><div className="workspace-heading"><p className="eyebrow">SETTINGS</p><h1>Everything in its place.</h1><p>Your account, traveler profile, private details, and application connection. Real Travel assistance keeps existing tickets separate from the demo.</p></div><AccountSettings /><ProfileSettings /><TravelerSettings /><section className="settings-panel"><div className="settings-title"><span className="empty-icon"><Settings size={23} /></span><div><h2>Application connection</h2><p>This check uses the real backend health endpoint.</p></div></div><ConnectionDetails /><div className="settings-note"><ShieldCheck size={20} /><p><strong>Your ideas, your approval.</strong><br />Way can suggest itinerary activities and save them after you approve. Your saved trip supplies the dates and budget. Real AI is configured privately in the backend; demo proposals are curated examples. Long-term preferences, location access, and booking actions are coming later.</p></div></section></>
}

function NotFoundPage() {
  return <main id="main-content" className="not-found page-width"><Compass size={42} strokeWidth={1.2} /><p className="eyebrow">A SMALL DETOUR</p><h1>This path is still unexplored.</h1><p>We couldn’t find that page. Your workspace is just a step away.</p><Button asChild><Link to="/dashboard">Back to your workspace<ArrowRight size={16} /></Link></Button></main>
}

export default function App() {
  return <ConnectionProvider><TripsProvider><BuddyProvider><a className="skip-link" href="#main-content">Skip to content</a><ScrollToPage /><SiteHeader /><Routes><Route path="/" element={<LandingPage />} /><Route element={<WorkspaceLayout />}><Route path="/dashboard" element={<DashboardPage />} /><Route path="/trips" element={<MyTripsPage />} /><Route path="/trips/:tripId" element={<TripDetailPage />} /><Route path="/rescue" element={<RescuePage />} /><Route path="/rescue/real" element={<RealTravelPage />} /><Route path="/trips/:tripId/rescue" element={<RescuePage />} /><Route path="/buddy" element={<BuddyPage />} /><Route path="/explore" element={<ComingPage page="explore" />} /><Route path="/groups" element={<ComingPage page="groups" />} /><Route path="/account" element={<AccountPage />} /><Route path="/settings" element={<SettingsPage />} /></Route><Route path="*" element={<NotFoundPage />} /></Routes><FloatingBuddy /></BuddyProvider></TripsProvider></ConnectionProvider>
}

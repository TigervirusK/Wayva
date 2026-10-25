import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { tripsApi, TripsApiError, type Profile, type TripSummary, type TripDetail, type TripInput, type ItemInput } from './trips-api'
import { accountApi, accountProof, AccountApiError, type AccountSession } from '@/features/accounts/account-api'

const TOKEN_KEY = 'triprescue.local-profile-token'
const TRIP_KEY = 'triprescue.selected-trip-id'
const LEGACY_BACKUP_KEY = 'triprescue.unlinked-profile-token'

function readSaved(key: string): string | null {
  try { return localStorage.getItem(key) } catch { return null }
}

function writeSaved(key: string, value: string | null): boolean {
  try { if (value === null) localStorage.removeItem(key); else localStorage.setItem(key, value); return true } catch { return false }
}

type TripsContextValue = {
  profile: Profile | null
  token: string | null
  activeTrip: TripDetail | null
  viewedTrip: TripDetail | null
  viewTrip: (id: string | null) => void
  selectedTripId: string | null
  selectTrip: (id: string | null) => void
  trips: TripSummary[]
  loading: boolean
  error: string | null
  tripLoading: boolean
  tripError: string | null
  profileLoading: boolean
  profileError: string | null
  recoveryRequired: boolean
  storageAvailable: boolean
  mutationLoading: boolean
  retryProfile: () => void
  refreshTrips: () => Promise<void>
  createProfile: (name: string) => Promise<void>
  accountUsername: string | null
  previousLocalProfile: boolean
  signIn: (username: string, password: string) => Promise<void>
  registerAccount: (username: string, password: string, name: string, link: boolean) => Promise<void>
  signOut: () => Promise<void>
  changeAccountPassword: (current: string, next: string) => Promise<void>
  resumeLocalProfile: () => Promise<void>
  renameProfile: (name: string) => Promise<void>
  loadTrip: (id: string) => Promise<TripDetail>
  saveTrip: (id: string | null, input: TripInput) => Promise<TripDetail>
  saveItem: (tripId: string, itemId: string | null, input: ItemInput) => Promise<TripDetail>
  removeItem: (tripId: string, itemId: string) => Promise<TripDetail>
}

const TripsContext = createContext<TripsContextValue | null>(null)

export function TripsProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => readSaved(TOKEN_KEY))
  const [profile, setProfile] = useState<Profile | null>(null)
  const [profileLoading, setProfileLoading] = useState(true)
  const [accountUsername, setAccountUsername] = useState<string | null>(null)
  const [previousLocalProfile, setPreviousLocalProfile] = useState(!!readSaved(LEGACY_BACKUP_KEY))
  const [profileError, setProfileError] = useState<string | null>(null)
  const [profileAttempt, setProfileAttempt] = useState(0)
  const [recoveryRequired, setRecoveryRequired] = useState(false)
  const [storageAvailable, setStorageAvailable] = useState(true)
  const [trips, setTrips] = useState<TripSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedTripId, setSelectedTripId] = useState<string | null>(() => readSaved(TRIP_KEY))
  const [tripCache, setTripCache] = useState<Record<string, TripDetail>>({})
  const [viewedTripId, setViewedTripId] = useState<string | null>(null)
  const [loadingDetails, setLoadingDetails] = useState<Record<string, boolean>>({})
  const [detailErrors, setDetailErrors] = useState<Record<string, string | null>>({})
  const [mutationLoading, setMutationLoading] = useState(false)
  const mutationLock = useRef(false)
  const tokenRef = useRef(token)
  const selectedRef = useRef(selectedTripId)
  const cacheRef = useRef(tripCache)
  const listRequest = useRef<AbortController | null>(null)
  const detailRequests = useRef(new Map<string, AbortController>())
  const profileRef = useRef(profile)
  const authGeneration = useRef(0)
  const accountChannel = useRef<BroadcastChannel | null>(null)
  profileRef.current = profile
  tokenRef.current = token
  selectedRef.current = selectedTripId
  cacheRef.current = tripCache
  const activeTrip = selectedTripId ? tripCache[selectedTripId] ?? null : null
  const viewedTrip = viewedTripId ? tripCache[viewedTripId] ?? null : null
  const tripLoading = viewedTripId ? loadingDetails[viewedTripId] ?? false : false
  const tripError = viewedTripId ? detailErrors[viewedTripId] ?? null : null

  const abortDetailReads = useCallback(() => {
    for (const controller of detailRequests.current.values()) controller.abort()
    detailRequests.current.clear()
  }, [])

  const cacheTrip = useCallback((trip: TripDetail) => {
    cacheRef.current = { ...cacheRef.current, [trip.id]: trip }
    setTripCache((previous) => ({ ...previous, [trip.id]: trip }))
  }, [])

  const invalidateProfile = useCallback(() => {
    listRequest.current?.abort()
    abortDetailReads()
    tokenRef.current = null
    profileRef.current = null
    selectedRef.current = null
    cacheRef.current = {}
    setToken(null); setProfile(null); setTrips([]); setTripCache({}); setSelectedTripId(null)
    setAccountUsername(null)
    setProfileLoading(false); setLoading(false); setLoadingDetails({}); setDetailErrors({})
    setRecoveryRequired(true)
    writeSaved(TOKEN_KEY, null); writeSaved(TRIP_KEY, null)
    try { sessionStorage.removeItem('triprescue.pip-threads.v1') } catch { /* No persistent chat cache is required. */ }
  }, [abortDetailReads])

  const installAccount = useCallback((result: AccountSession, linked = false) => {
    const previous = tokenRef.current
    if (previous && !previous.startsWith('account-session:') && !linked) {
      setStorageAvailable(writeSaved(LEGACY_BACKUP_KEY, previous))
      setPreviousLocalProfile(true)
    }
    if (linked && readSaved(LEGACY_BACKUP_KEY) === previous) { writeSaved(LEGACY_BACKUP_KEY, null); setPreviousLocalProfile(false) }
    listRequest.current?.abort(); abortDetailReads()
    const sameOwner = !profileRef.current || profileRef.current.id === result.profile.id
    const selected = sameOwner ? selectedRef.current : null
    tokenRef.current = accountProof(result)
    profileRef.current = result.profile
    cacheRef.current = {}; selectedRef.current = selected
    setToken(tokenRef.current); setProfile(result.profile); setAccountUsername(result.account.username)
    setTrips([]); setTripCache({}); setSelectedTripId(selected); setViewedTripId(null)
    setProfileLoading(false); setProfileError(null); setRecoveryRequired(false); setError(null)
    setLoading(false); setLoadingDetails({}); setDetailErrors({})
    writeSaved(TOKEN_KEY, null); writeSaved(TRIP_KEY, selected)
    // Restoring this account after refresh must preserve its tab-scoped chat.
    // Identity changes and sign-out clear the cache before another owner uses it.
    if (!sameOwner) {
      try { sessionStorage.removeItem('triprescue.pip-threads.v1') } catch { /* Account data stays in the backend. */ }
    }
  }, [abortDetailReads])

  const handleMutationError = useCallback((failure: unknown, requestToken: string) => {
    if (requestToken === tokenRef.current && failure instanceof TripsApiError && failure.status === 401) invalidateProfile()
    throw failure
  }, [invalidateProfile])

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const generation = ++authGeneration.current
    setProfileLoading(true); setProfileError(null)
    async function restore() {
      try {
        const result = await accountApi.session(controller.signal)
        if (active && authGeneration.current === generation) installAccount(result)
      } catch (failure) {
        if (!active || controller.signal.aborted || authGeneration.current !== generation) return
        if (!(failure instanceof AccountApiError) || failure.status !== 401) {
          setProfileError(failure instanceof Error ? failure.message : 'Your account could not be opened. Retry the connection.')
          return
        }
        const legacy = tokenRef.current
        if (legacy && !legacy.startsWith('account-session:')) {
          try {
            const result = await tripsApi.getProfile(legacy, controller.signal)
            if (active && authGeneration.current === generation) { setProfile(result); profileRef.current = result; setAccountUsername(null); setRecoveryRequired(false) }
          } catch (error) {
            if (!active || controller.signal.aborted || authGeneration.current !== generation) return
            if (error instanceof TripsApiError && error.status === 401) invalidateProfile()
            else setProfileError(error instanceof Error ? error.message : 'Your existing profile could not be opened.')
          }
        } else if (active && authGeneration.current === generation) invalidateProfile()
      } finally { if (active && authGeneration.current === generation) setProfileLoading(false) }
    }
    void restore()
    return () => { active = false; controller.abort() }
  }, [profileAttempt, invalidateProfile, installAccount])

  useEffect(() => {
    if (!accountUsername) return
    let active = true
    const controller = new AbortController()
    let checking = false
    const check = async () => {
      if (checking || document.visibilityState === 'hidden') return
      checking = true
      const generation = authGeneration.current
      try {
        const result = await accountApi.session(controller.signal)
        if (active && generation === authGeneration.current && accountProof(result) !== tokenRef.current) installAccount(result)
      } catch (failure) {
        if (active && generation === authGeneration.current && failure instanceof AccountApiError && failure.status === 401) invalidateProfile()
      } finally { checking = false }
    }
    const timer = window.setInterval(() => void check(), 60000)
    const visible = () => { if (document.visibilityState === 'visible') void check() }
    document.addEventListener('visibilitychange', visible)
    return () => { active = false; controller.abort(); window.clearInterval(timer); document.removeEventListener('visibilitychange', visible) }
  }, [accountUsername, installAccount, invalidateProfile])

  useEffect(() => {
    try {
      const channel = new BroadcastChannel('triprescue-account-state')
      accountChannel.current = channel
      channel.onmessage = () => { authGeneration.current += 1; invalidateProfile(); setProfileAttempt(value => value + 1) }
      return () => { channel.close(); accountChannel.current = null }
    } catch { return undefined }
  }, [invalidateProfile])

  const refreshTrips = useCallback(async () => {
    if (!token || !profile) return
    listRequest.current?.abort()
    const controller = new AbortController()
    listRequest.current = controller
    setLoading(true); setError(null)
    try {
      const result = await tripsApi.list(token, controller.signal)
      if (!controller.signal.aborted && tokenRef.current === token) {
        setTrips(result)
        if (selectedRef.current && !result.some(trip => trip.id === selectedRef.current)) {
          selectedRef.current = null; setSelectedTripId(null); writeSaved(TRIP_KEY, null)
        }
      }
    } catch (failure: unknown) {
      if (controller.signal.aborted || tokenRef.current !== token) return
      if (failure instanceof TripsApiError && failure.status === 401) invalidateProfile()
      else setError(failure instanceof Error ? failure.message : 'Trips could not be loaded. Please retry.')
    } finally {
      if (listRequest.current === controller && tokenRef.current === token) setLoading(false)
    }
  }, [token, profile, invalidateProfile])

  useEffect(() => {
    if (profile && token) void refreshTrips()
    return () => listRequest.current?.abort()
  }, [profile, token, refreshTrips])

  const loadTrip = useCallback(async (id: string) => {
    if (!token || !profile) throw new TripsApiError('Sign in to open your saved trips.', 401)
    detailRequests.current.get(id)?.abort()
    const controller = new AbortController()
    detailRequests.current.set(id, controller)
    setLoadingDetails((previous) => ({ ...previous, [id]: true }))
    setDetailErrors((previous) => ({ ...previous, [id]: null }))
    try {
      const result = await tripsApi.get(token, id, controller.signal)
      if (!controller.signal.aborted && tokenRef.current === token) cacheTrip(result)
      return result
    } catch (failure: unknown) {
      if (!controller.signal.aborted && tokenRef.current === token) {
        if (failure instanceof TripsApiError && failure.status === 401) invalidateProfile()
        else setDetailErrors((previous) => ({ ...previous, [id]: failure instanceof Error ? failure.message : 'This trip could not be loaded.' }))
      }
      throw failure
    } finally {
      if (detailRequests.current.get(id) === controller) {
        detailRequests.current.delete(id)
        if (tokenRef.current === token) setLoadingDetails((previous) => ({ ...previous, [id]: false }))
      }
    }
  }, [token, profile, invalidateProfile, cacheTrip])

  const selectTrip = useCallback((id: string | null) => {
    if (selectedRef.current === id) return
    selectedRef.current = id
    setSelectedTripId(id)
    setStorageAvailable((previous) => writeSaved(TRIP_KEY, id) && previous)
  }, [])

  const viewTrip = useCallback((id: string | null) => setViewedTripId(id), [])

  useEffect(() => {
    if (!profile || !token) return
    // Browsing and Way selection are independent consumers of the same saved data.
    // Clearing chat context must not cancel a page's pending detail request.
    for (const id of new Set([selectedTripId, viewedTripId])) {
      if (id && !cacheRef.current[id] && !detailRequests.current.has(id)) void loadTrip(id).catch(() => undefined)
    }
  }, [profile, token, selectedTripId, viewedTripId, loadTrip])

  useEffect(() => () => { listRequest.current?.abort(); abortDetailReads() }, [abortDetailReads])

  const applyTrip = (result: TripDetail, activate = false) => {
    listRequest.current?.abort()
    setLoading(false)
    setTrips((previous) => [result, ...previous.filter((trip) => trip.id !== result.id)].sort((a, b) => a.start_date.localeCompare(b.start_date)))
    detailRequests.current.get(result.id)?.abort()
    detailRequests.current.delete(result.id)
    cacheTrip(result)
    setDetailErrors((previous) => ({ ...previous, [result.id]: null }))
    setLoadingDetails((previous) => ({ ...previous, [result.id]: false }))
    if (activate) {
      selectedRef.current = result.id
      setSelectedTripId(result.id)
      setStorageAvailable((previous) => writeSaved(TRIP_KEY, result.id) && previous)
    }
    // Refresh the complete collection even if the first list request was still pending.
    void refreshTrips()
  }

  const createProfile = async (name: string) => {
    const result = await tripsApi.createProfile(name.trim())
    listRequest.current?.abort(); abortDetailReads()
    tokenRef.current = result.token
    selectedRef.current = null
    cacheRef.current = {}
    setStorageAvailable(writeSaved(TOKEN_KEY, result.token) && writeSaved(TRIP_KEY, null))
    setToken(result.token); setProfile(result.profile); setSelectedTripId(null); setTripCache({}); setTrips([])
    setAccountUsername(null)
    setRecoveryRequired(false); setProfileError(null); setError(null); setDetailErrors({}); setLoadingDetails({})
  }

  const broadcastAccount = () => { try { accountChannel.current?.postMessage({ changed: true }) } catch { /* Server auth still checks every request. */ } }
  const signIn = async (username: string, password: string) => {
    const generation = ++authGeneration.current
    const result = await accountApi.login(username, password)
    if (generation !== authGeneration.current) return
    installAccount(result); broadcastAccount()
  }
  const registerAccount = async (username: string, password: string, name: string, link: boolean) => {
    const generation = ++authGeneration.current
    const result = await accountApi.register(username, password, name, link, link ? tokenRef.current : null)
    if (generation !== authGeneration.current) return
    installAccount(result, link); broadcastAccount()
  }
  const signOut = async () => {
    await accountApi.logout(tokenRef.current)
    authGeneration.current += 1
    invalidateProfile(); setRecoveryRequired(false); broadcastAccount()
  }
  const changeAccountPassword = async (current: string, next: string) => {
    if (!tokenRef.current) throw new AccountApiError('Sign in before changing your password.', 401)
    const generation = ++authGeneration.current
    const result = await accountApi.changePassword(tokenRef.current, current, next)
    if (generation !== authGeneration.current) return
    installAccount(result); broadcastAccount()
  }
  const resumeLocalProfile = async () => {
    const legacy = readSaved(LEGACY_BACKUP_KEY)
    if (!legacy) throw new AccountApiError('No previous local profile is available in this browser.', 401)
    const result = await tripsApi.getProfile(legacy)
    authGeneration.current += 1; invalidateProfile()
    writeSaved(TOKEN_KEY, legacy)
    tokenRef.current = legacy; profileRef.current = result
    setToken(legacy); setProfile(result); setAccountUsername(null); setRecoveryRequired(false)
  }

  const renameProfile = async (name: string) => {
    if (!token) throw new TripsApiError('Sign in to manage your saved trips.', 401)
    try { const result = await tripsApi.renameProfile(token, name.trim()); if (tokenRef.current === token) setProfile(result) }
    catch (failure) { handleMutationError(failure, token) }
  }

  const performTripMutation = async (operation: (requestToken: string) => Promise<TripDetail>, activate = false) => {
    if (!token) throw new TripsApiError('Sign in to manage your saved trips.', 401)
    if (mutationLock.current) throw new TripsApiError('Another change is being saved. Please wait a moment and try again.', 409)
    mutationLock.current = true; setMutationLoading(true)
    try {
      const result = await operation(token)
      if (tokenRef.current !== token) throw new TripsApiError('Your account or profile changed. Reload before continuing.', 401)
      applyTrip(result, activate)
      return result
    } catch (failure) { return handleMutationError(failure, token) }
    finally { mutationLock.current = false; setMutationLoading(false) }
  }

  const saveTrip = (id: string | null, input: TripInput) => performTripMutation((requestToken) => id ? tripsApi.update(requestToken, id, input) : tripsApi.create(requestToken, input), id === null)

  const saveItem = (tripId: string, itemId: string | null, input: ItemInput) => performTripMutation((requestToken) => tripsApi.saveItem(requestToken, tripId, itemId, input))

  const removeItem = (tripId: string, itemId: string) => performTripMutation((requestToken) => tripsApi.removeItem(requestToken, tripId, itemId))

  return <TripsContext.Provider value={{ profile, token, accountUsername, previousLocalProfile, signIn, registerAccount, signOut, changeAccountPassword, resumeLocalProfile, activeTrip, viewedTrip, viewTrip, selectedTripId, selectTrip, trips, loading, error, tripLoading, tripError, profileLoading, profileError, recoveryRequired, storageAvailable, mutationLoading, retryProfile: () => setProfileAttempt((value) => value + 1), refreshTrips, createProfile, renameProfile, loadTrip, saveTrip, saveItem, removeItem }}>{children}</TripsContext.Provider>
}

export function useTrips() {
  const value = useContext(TripsContext)
  if (!value) throw new Error('useTrips must be used inside TripsProvider.')
  return value
}

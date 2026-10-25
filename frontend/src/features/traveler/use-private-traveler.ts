import { useCallback, useEffect, useRef, useState } from 'react'
import { useTrips } from '@/features/trips'
import { PrivateApiError, travelerApi, type VaultData, type VaultEnvelope, type VaultStatus } from './traveler-api'

// Deliberately no localStorage/sessionStorage, chat context, or analytics access.
export function usePrivateTraveler() {
  const { profile, token } = useTrips()
  const identity = `${profile?.id}:${token}`
  const current = useRef(identity)
  current.current = identity
  const generation = useRef(0)
  const loaded = useRef<string | null>(null)
  const busyRef = useRef(false)
  const [status, setStatus] = useState<VaultStatus | null>(null)
  const [envelope, setEnvelope] = useState<VaultEnvelope | null>(null)
  const [deadline, setDeadline] = useState(0)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const channel = useRef<BroadcastChannel | null>(null)
  const clear = useCallback(() => { setEnvelope(null); setDeadline(0); setNotice(null); setStatus(previous => previous ? { ...previous, unlocked: false, expires_in_seconds: 0 } : null) }, [])
  const receive = (value: VaultEnvelope) => {
    loaded.current = identity
    setEnvelope(value); setDeadline(Date.now() + value.expires_in_seconds * 1000)
    setStatus({ exists: true, unlocked: true, expires_in_seconds: value.expires_in_seconds, production_account_ready: false })
  }
  useEffect(() => {
    const controller = new AbortController()
    const requestGeneration = ++generation.current
    setEnvelope(null); setStatus(null); setError(null); setNotice(null); setDeadline(0); setLoading(!!token && !!profile)
    busyRef.current = false; setBusy(false)
    if (token && profile) {
      travelerApi.status(token, controller.signal).then(async result => {
        if (controller.signal.aborted || current.current !== identity) return
        loaded.current = identity; setStatus(result)
        if (result.unlocked) {
          const data = await travelerApi.read(token, controller.signal)
          if (!controller.signal.aborted && generation.current === requestGeneration && current.current === identity) receive(data)
        }
      }).catch(failure => { if (!controller.signal.aborted && current.current === identity) { clear(); setError(failure instanceof Error ? failure.message : 'Private details could not be opened.') } })
        .finally(() => { if (!controller.signal.aborted && current.current === identity) setLoading(false) })
    }
    return () => { controller.abort(); generation.current += 1 }
    // receive captures only the identity used by this request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identity, token, profile?.id, attempt, clear])
  useEffect(() => {
    if (!deadline) return
    const expire = () => { if (Date.now() >= deadline) clear() }
    const timer = window.setTimeout(expire, Math.max(0, deadline - Date.now()))
    document.addEventListener('visibilitychange', expire)
    return () => { window.clearTimeout(timer); document.removeEventListener('visibilitychange', expire) }
  }, [deadline, clear])
  useEffect(() => {
    try {
      const messages = new BroadcastChannel('triprescue-private-lock')
      channel.current = messages
      messages.onmessage = event => { if (event.data?.profile === profile?.id) clear() }
      return () => { messages.close(); channel.current = null }
    } catch { return undefined }
  }, [profile?.id, clear])
  const broadcast = () => { try { channel.current?.postMessage({ profile: profile?.id, action: 'invalidate' }) } catch { /* Server checks remain authoritative. */ } }
  async function perform(operation: (access: string) => Promise<VaultEnvelope>, notify = false) {
    if (!token || !profile || busyRef.current) return false
    const requestGeneration = generation.current
    busyRef.current = true; setBusy(true); setError(null)
    try {
      const result = await operation(token)
      if (current.current !== identity || generation.current !== requestGeneration) return false
      receive(result)
      if (notify) { setNotice('Last save completed: private changes were stored encrypted. Booking details remain unverified.'); broadcast() }
      return true
    } catch (failure) {
      if (current.current === identity && generation.current === requestGeneration) {
        if (failure instanceof PrivateApiError && [401, 423].includes(failure.status)) clear()
        setError(failure instanceof Error ? failure.message : 'Private details could not be saved.')
      }
      return false
    } finally { if (current.current === identity && generation.current === requestGeneration) { busyRef.current = false; setBusy(false) } }
  }
  async function lock() {
    clear()
    if (!token) return
    try { await travelerApi.lock(token) } catch (failure) { setError(failure instanceof Error ? failure.message : 'Details are hidden here; the server session could not be closed. It will expire automatically.') }
    finally { broadcast() }
  }
  const visible = loaded.current === identity
  return { profile, token, status: visible ? status : null, envelope: visible ? envelope : null, loading, busy, error, notice,
    reload: () => { clear(); setAttempt(value => value + 1) }, lock,
    authenticate: (password: string) => perform(access => status?.exists ? travelerApi.unlock(access, password) : travelerApi.create(access, password)),
    save: (data: VaultData) => envelope ? perform(access => travelerApi.save(access, envelope.revision, data), true) : Promise.resolve(false),
    changePassword: (old: string, next: string) => perform(access => travelerApi.changePassword(access, old, next), true),
  }
}

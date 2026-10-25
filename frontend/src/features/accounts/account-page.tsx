import { useId, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Check, KeyRound, LockKeyhole, LogOut, ShieldCheck, UserRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTrips } from '@/features/trips/trips-provider'
import './accounts.css'

const failureMessage = (failure: unknown) => failure instanceof Error ? failure.message : 'Your account request could not be completed.'

export function AccountAccess() {
  const { profile, signIn, registerAccount, previousLocalProfile, resumeLocalProfile } = useTrips()
  const [mode, setMode] = useState<'login' | 'register'>(profile ? 'register' : 'login')
  const [username, setUsername] = useState('')
  const [name, setName] = useState(profile?.display_name ?? '')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [link, setLink] = useState(!!profile)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const lock = useId()
  const navigate = useNavigate()
  return <section className="account-access" aria-labelledby={`${lock}-title`}><span className="account-icon"><LockKeyhole size={27} strokeWidth={1.4} /></span><p className="eyebrow">A HOME FOR YOUR JOURNEYS</p><h2 id={`${lock}-title`}>{mode === 'login' ? 'Your trips. Your account.' : 'Make these journeys yours.'}</h2><p>Sign in with a username and password to reopen the saved trips and details linked to your account.</p>
    <div className="account-tabs" role="group" aria-label="Account access"><button type="button" aria-pressed={mode === 'login'} disabled={busy} onClick={() => { setMode('login'); setError(null); setPassword(''); setConfirm('') }}>Sign in</button><button type="button" aria-pressed={mode === 'register'} disabled={busy} onClick={() => { setMode('register'); setError(null); setPassword(''); setConfirm('') }}>Create account</button></div>
    {profile && <div className="account-preserve"><ShieldCheck size={18} /><p>You’re using the local profile <strong>{profile.display_name}</strong>. Create an account with “Keep my current profile and saved data” selected to connect its trips and private vault. Signing into another account keeps this unlinked profile available on this browser.</p></div>}
    <form className="trips-form account-form" onSubmit={async event => {
      event.preventDefault(); if (busy) return
      if (mode === 'register' && password !== confirm) { setError('The passwords do not match.'); return }
      setBusy(true); setError(null)
      try {
        if (mode === 'register') await registerAccount(username.trim(), password, name.trim(), !!profile && link)
        else await signIn(username.trim(), password)
        navigate('/trips', { replace: true })
      } catch (failure) { setError(failureMessage(failure)) }
      finally { setBusy(false); setPassword(''); setConfirm('') }
    }} aria-busy={busy}>
      <fieldset disabled={busy}><legend className="trips-sr-only">{mode === 'login' ? 'Sign in' : 'Create account'}</legend>
        {mode === 'register' && (!profile || !link) && <label htmlFor={`${lock}-name`}>Display name<input id={`${lock}-name`} value={name} onChange={event => setName(event.target.value)} maxLength={80} autoComplete="nickname" placeholder="What should Way call you?" /></label>}
        <label htmlFor={`${lock}-username`}>Username<input id={`${lock}-username`} value={username} onChange={event => setUsername(event.target.value)} minLength={3} maxLength={30} required pattern="[A-Za-z0-9][A-Za-z0-9_.\-]{2,29}" autoCapitalize="none" autoCorrect="off" spellCheck={false} autoComplete="username" aria-describedby={`${lock}-username-help`} /></label>
        <p className="account-help" id={`${lock}-username-help`}>3–30 characters: letters, numbers, dots, underscores, or hyphens. Usernames are not case-sensitive.</p>
        <label htmlFor={`${lock}-password`}>Account password<input id={`${lock}-password`} type="password" value={password} onChange={event => setPassword(event.target.value)} minLength={mode === 'register' ? 15 : 1} maxLength={128} required autoComplete={mode === 'register' ? 'new-password' : 'current-password'} /></label>
        {mode === 'register' && <><p className="account-help">Use a unique passphrase of at least 15 characters. Passwords are stored as salted hashes.</p><label htmlFor={`${lock}-confirm`}>Confirm account password<input id={`${lock}-confirm`} type="password" value={confirm} onChange={event => setConfirm(event.target.value)} minLength={15} maxLength={128} required autoComplete="new-password" /></label>{profile && <label className="account-checkbox"><input type="checkbox" checked={link} onChange={event => setLink(event.target.checked)} /><span>Keep my current profile and saved data</span></label>}</>}
      </fieldset>
      {error && <div className="trips-error" role="alert">{error}</div>}
      <Button type="submit" disabled={busy}>{busy ? 'Opening your account…' : mode === 'login' ? 'Sign in to Wayva' : profile && link ? 'Create account & keep my data' : 'Create my account'}<ArrowRight size={16} /></Button>
    </form>
    {previousLocalProfile && !profile && <button className="account-restore" type="button" disabled={busy} onClick={async () => { setBusy(true); setError(null); try { await resumeLocalProfile(); navigate('/account', { replace: true }) } catch (failure) { setError(failureMessage(failure)) } finally { setBusy(false) } }}>Reopen my previous local profile</button>}
    <p className="account-help account-limit">There is no email password-reset service yet. Keep your username and password safe. Your encrypted traveler vault keeps its separate vault password.</p>
  </section>
}

export function AccountSettings() {
  const { profile, accountUsername } = useTrips()
  if (!profile) return null
  return <section className="account-summary"><span className="account-icon"><UserRound size={23} /></span><div><p className="eyebrow">YOUR ACCOUNT</p><h2>{accountUsername ? `Signed in as ${accountUsername}` : 'Connect this profile to a login.'}</h2><p>{accountUsername ? 'Your saved trips and private details belong to this account.' : 'Keep your existing trips and private vault while adding username-and-password sign-in.'}</p></div><Button asChild variant="outline" size="sm"><Link to="/account">{accountUsername ? 'Manage account' : 'Create my account'}<ArrowRight size={14} /></Link></Button></section>
}

export function AccountPage() {
  const { profile, accountUsername, profileLoading, profileError, retryProfile, signOut, changeAccountPassword } = useTrips()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const id = useId()
  if (profileLoading) return <p className="trips-loading" role="status">Opening your account…</p>
  if (profileError) return <div className="trips-error" role="alert"><p>{profileError}</p><button onClick={retryProfile}>Retry account connection</button></div>
  if (!accountUsername) return <AccountAccess key={profile?.id ?? 'guest'} />
  return <div className="account-page"><div className="workspace-heading"><p className="eyebrow">YOUR ACCOUNT</p><h1>Welcome back, {profile?.display_name}.</h1><p>Signed in as <strong>{accountUsername}</strong>. Your trips, proposals, demo recovery records, and encrypted private details stay linked to this account.</p></div>
    <section className="account-security"><div className="private-heading"><div><p className="eyebrow">PASSWORD & ACCESS</p><h2>Keep your journeys private.</h2></div><KeyRound size={26} strokeWidth={1.4} /></div>
      <form className="trips-form" onSubmit={async event => {
        event.preventDefault(); if (busy) return
        if (next !== confirm) { setError('The new passwords do not match.'); return }
        setBusy(true); setError(null); setSaved(false)
        try { await changeAccountPassword(current, next); setSaved(true) } catch (failure) { setError(failureMessage(failure)) }
        finally { setCurrent(''); setNext(''); setConfirm(''); setBusy(false) }
      }}>
        <label htmlFor={`${id}-current`}>Current account password<input id={`${id}-current`} type="password" value={current} onChange={event => setCurrent(event.target.value)} required maxLength={128} autoComplete="current-password" disabled={busy} /></label>
        <label htmlFor={`${id}-new`}>New account password<input id={`${id}-new`} type="password" value={next} onChange={event => setNext(event.target.value)} required minLength={15} maxLength={128} autoComplete="new-password" disabled={busy} /></label>
        <label htmlFor={`${id}-confirm`}>Confirm new account password<input id={`${id}-confirm`} type="password" value={confirm} onChange={event => setConfirm(event.target.value)} required minLength={15} maxLength={128} autoComplete="new-password" disabled={busy} /></label>
        {saved && <p className="trips-success" role="status"><Check size={15} /> Account password changed. Other sign-in sessions were ended; your vault password is unchanged.</p>}
        <Button type="submit" disabled={busy}>{busy ? 'Updating account…' : 'Change account password'}<KeyRound size={15} /></Button>
      </form>
      {error && <div className="trips-error" role="alert">{error}</div>}
      <div className="account-signout"><p>Sign out to close this browser’s account session and clear its displayed trip and chat state. Saved data stays in the database.</p><Button variant="outline" disabled={busy} onClick={async () => { setBusy(true); setError(null); try { await signOut() } catch (failure) { setError(failureMessage(failure)) } finally { setBusy(false) } }}><LogOut size={16} /> Sign out</Button></div>
      <p className="account-help">Account sessions expire after 30 minutes without API activity, or eight hours in total. Private traveler details still require their vault password. Password recovery, MFA, and public hosting are not configured.</p>
    </section>
  </div>
}

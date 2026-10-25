import { Link } from 'react-router-dom'
import { Plane, ShieldCheck } from 'lucide-react'

export function RescueModeSwitch({ mode }: { mode: 'demo' | 'real' }) {
  return <nav className="rescue-mode-switch" aria-label="Rescue mode"><Link to="/rescue" aria-current={mode === 'demo' ? 'page' : undefined}><ShieldCheck size={15} /> Demo Mode<span>Simulated bookings</span></Link><Link to="/rescue/real" aria-current={mode === 'real' ? 'page' : undefined}><Plane size={15} /> Real Travel Mode<span>Assisted · not connected</span></Link></nav>
}

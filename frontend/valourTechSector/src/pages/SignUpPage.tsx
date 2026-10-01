import { AtSign, Lock, Phone } from 'lucide-react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { safeNextPath } from '../auth/nextPath'
import { useAuth } from '../auth/useAuth'
import { LearnerAuthForm } from '../components/LearnerAuthForm'
import { LoadingState } from '../components/States'

export function SignUpPage() {
  const { status, isAuthenticated } = useAuth()
  const [searchParams] = useSearchParams()
  const next = safeNextPath(searchParams.get('next'))

  if (status === 'loading') {
    return <section className="section-shell auth-shell"><LoadingState label="Checking your session…" /></section>
  }
  if (isAuthenticated) return <Navigate to={next} replace />

  return (
    <>
      <section className="page-hero auth-hero section-shell">
        <div className="breadcrumb"><span>LEARNER ACCESS</span><span className="breadcrumb-slash">/</span><span>CREATE ACCOUNT</span></div>
        <div className="page-hero-content">
          <div><p className="eyebrow">FREE LEARNER ACCOUNT</p><h1>Two details,<br /><em>then the bench.</em></h1></div>
          <p className="page-hero-note">Create an account with your email address and phone number. You will be signed in straight away.</p>
        </div>
      </section>

      <section className="auth-content section-shell">
        <div className="auth-panel">
          <span className="auth-panel-kicker">CREATE YOUR ACCOUNT</span>
          <LearnerAuthForm mode="signup" next={next} />
        </div>
        <aside className="auth-aside">
          <span className="sidebar-kicker">WHAT WE ASK FOR</span>
          <ul className="auth-benefit-list">
            <li><AtSign size={16} aria-hidden="true" /> Your email address — this is what you sign in with</li>
            <li><Phone size={16} aria-hidden="true" /> Your phone number — so the team can reach you about lessons</li>
            <li><Lock size={16} aria-hidden="true" /> A password you choose, stored scrambled and never shown</li>
          </ul>
          <p className="auth-aside-note">No payment details, and nothing is published on the site. Signing out on a shared device ends the session.</p>
        </aside>
      </section>
    </>
  )
}

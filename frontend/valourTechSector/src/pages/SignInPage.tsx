import { ArrowUpRight, BookOpen, Download, ShieldCheck } from 'lucide-react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { safeNextPath } from '../auth/nextPath'
import { useAuth } from '../auth/useAuth'
import { LearnerAuthForm } from '../components/LearnerAuthForm'
import { LoadingState } from '../components/States'

export function SignInPage() {
  const { status, isAuthenticated, registration } = useAuth()
  const [searchParams] = useSearchParams()
  const next = safeNextPath(searchParams.get('next'))

  // A signed-in learner has nothing to sign in to; send them where they were going.
  if (status === 'loading') {
    return <section className="section-shell auth-shell"><LoadingState label="Checking your session…" /></section>
  }
  if (isAuthenticated) return <Navigate to={next} replace />

  return (
    <>
      <section className="page-hero auth-hero section-shell">
        <div className="breadcrumb"><span>LEARNER ACCESS</span><span className="breadcrumb-slash">/</span><span>SIGN IN</span></div>
        <div className="page-hero-content">
          <div><p className="eyebrow">WELCOME BACK</p><h1>Sign in to<br /><em>your bench.</em></h1></div>
          <p className="page-hero-note">Your lessons are where you left them. Sign in with the email address you registered with.</p>
        </div>
      </section>

      <section className="auth-content section-shell">
        <div className="auth-panel">
          <span className="auth-panel-kicker">LEARNER SIGN IN</span>
          <LearnerAuthForm mode="signin" next={next} />
        </div>
        <aside className="auth-aside">
          <span className="sidebar-kicker">WHAT SIGNING IN OPENS</span>
          <ul className="auth-benefit-list">
            <li><BookOpen size={16} aria-hidden="true" /> Written notes for every published lesson</li>
            <li><ShieldCheck size={16} aria-hidden="true" /> Video demonstrations from the creators</li>
            <li><Download size={16} aria-hidden="true" /> PDF and Word references you can keep</li>
          </ul>
          <p className="auth-aside-note">
            Forgotten your password? <Link to="/contact">Contact the team <ArrowUpRight size={13} aria-hidden="true" /></Link> and we will help you back in.
          </p>
          {registration !== 'open' && (
            <p className="auth-aside-note">
              No account yet? Places are opened with a personal invitation link.{' '}
              <Link to="/contact">Ask the team for yours <ArrowUpRight size={13} aria-hidden="true" /></Link>
            </p>
          )}
        </aside>
      </section>
    </>
  )
}

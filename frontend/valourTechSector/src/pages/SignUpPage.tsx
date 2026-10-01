import { useEffect, useState, type ReactNode } from 'react'
import {
  ArrowRight,
  ArrowUpRight,
  AtSign,
  KeyRound,
  Lock,
  Mail,
  Phone,
  RefreshCw,
  TicketX,
} from 'lucide-react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { getInviteStatus } from '../api'
import { safeNextPath } from '../auth/nextPath'
import { useAuth } from '../auth/useAuth'
import { LearnerAuthForm } from '../components/LearnerAuthForm'
import { LoadingState } from '../components/States'

/**
 * What the invitation link in the address bar turned out to be.
 *
 * Registration is by invitation: the owner generates a single-use link in the
 * admin and sends it privately. This page is not linked from anywhere on the
 * site, so it explains itself to anyone who lands on it without a usable link.
 */
type InviteCheck =
  | { kind: 'checking' }
  | { kind: 'ready'; expiresAt: string | null }
  | { kind: 'refused'; message: string; reason: string }
  | { kind: 'unreachable' }

const REASON_HEADINGS: Record<string, string> = {
  used: 'That link has already been used',
  expired: 'That link has expired',
  revoked: 'That link was withdrawn',
  unknown: 'That link is not one of ours',
}

function Hero({ eyebrow, title, note, crumb }: { eyebrow: string; title: ReactNode; note: string; crumb: string }) {
  return (
    <section className="page-hero auth-hero section-shell">
      <div className="breadcrumb">
        <span>LEARNER ACCESS</span><span className="breadcrumb-slash">/</span><span>{crumb}</span>
      </div>
      <div className="page-hero-content">
        <div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1></div>
        <p className="page-hero-note">{note}</p>
      </div>
    </section>
  )
}

function InvitationAside() {
  return (
    <aside className="auth-aside">
      <span className="sidebar-kicker">WHAT WE ASK FOR</span>
      <ul className="auth-benefit-list">
        <li><AtSign size={16} aria-hidden="true" /> Your email address — this is what you sign in with</li>
        <li><Phone size={16} aria-hidden="true" /> Your phone number — so the team can reach you about lessons</li>
        <li><Lock size={16} aria-hidden="true" /> A password you choose, stored scrambled and never shown</li>
      </ul>
      <p className="auth-aside-note">
        Already registered? <Link to="/signin">Sign in <ArrowUpRight size={13} aria-hidden="true" /></Link> instead — a link
        is only needed the first time.
      </p>
    </aside>
  )
}

function ContactAside() {
  return (
    <aside className="auth-aside">
      <span className="sidebar-kicker">HOW ACCESS WORKS</span>
      <ul className="auth-benefit-list">
        <li><Mail size={16} aria-hidden="true" /> The team sends you a personal invitation link</li>
        <li><KeyRound size={16} aria-hidden="true" /> You open it and choose your own password</li>
        <li><ArrowRight size={16} aria-hidden="true" /> You sign in whenever you want to study</li>
      </ul>
      <p className="auth-aside-note">
        Each link registers one person, then stops working. Lost yours?{' '}
        <Link to="/contact">Ask the team for a new one <ArrowUpRight size={13} aria-hidden="true" /></Link>
      </p>
    </aside>
  )
}

export function SignUpPage() {
  const { status, isAuthenticated, registration } = useAuth()
  const [searchParams] = useSearchParams()
  const next = safeNextPath(searchParams.get('next'))
  const invite = (searchParams.get('invite') ?? '').trim()
  const needsInvite = registration !== 'open'
  const [check, setCheck] = useState<InviteCheck>({ kind: 'checking' })
  const [attempt, setAttempt] = useState(0)

  // Check the link before showing a form, so a spent or expired link is
  // explained instead of being refused after someone has typed their details.
  useEffect(() => {
    if (!needsInvite || !invite) return
    let active = true
    const controller = new AbortController()
    getInviteStatus(invite, { signal: controller.signal })
      .then((result) => {
        if (!active) return
        setCheck(result.valid
          ? { kind: 'ready', expiresAt: result.expires_at ?? null }
          : { kind: 'refused', message: result.message, reason: result.reason ?? 'unknown' })
      })
      .catch(() => {
        if (active) setCheck({ kind: 'unreachable' })
      })
    return () => {
      active = false
      controller.abort()
    }
  }, [attempt, invite, needsInvite])

  if (status === 'loading') {
    return <section className="section-shell auth-shell"><LoadingState label="Checking your session…" /></section>
  }
  // A signed-in learner has an account already; send them to their lessons.
  if (isAuthenticated) return <Navigate to={next} replace />

  if (needsInvite && !invite) {
    return (
      <>
        <Hero
          crumb="BY INVITATION"
          eyebrow="REGISTRATION"
          title={<>Places are opened<br /><em>one link at a time.</em></>}
          note="We do not run open sign-up. The team sends a personal invitation link to the learners they are admitting, and that link creates one account."
        />
        <section className="auth-content section-shell">
          <div className="auth-panel">
            <span className="auth-panel-kicker">NEED AN ACCOUNT?</span>
            <div className="invite-state" role="status">
              <span className="invite-state-icon" aria-hidden="true"><Mail size={20} /></span>
              <div>
                <strong>Ask the team for your invitation link</strong>
                <p>
                  Send a message with your name and the course you want to study. You will get a link that opens this
                  page with your details ready to fill in — it takes about a minute.
                </p>
                <div className="signin-actions">
                  <Link className="button button-primary" to="/contact">
                    Request access <ArrowRight size={15} aria-hidden="true" />
                  </Link>
                  <Link className="button button-outline" to="/signin">I already have an account</Link>
                </div>
              </div>
            </div>
          </div>
          <ContactAside />
        </section>
      </>
    )
  }

  if (needsInvite && check.kind === 'checking') {
    return <section className="section-shell auth-shell"><LoadingState label="Checking your invitation link…" /></section>
  }

  if (needsInvite && check.kind === 'refused') {
    return (
      <>
        <Hero
          crumb="LINK UNAVAILABLE"
          eyebrow="INVITATION"
          title={<>That link cannot<br /><em>register you.</em></>}
          note={check.message}
        />
        <section className="auth-content section-shell">
          <div className="auth-panel">
            <span className="auth-panel-kicker">WHAT HAPPENED</span>
            <div className="invite-state is-refused" role="status">
              <span className="invite-state-icon" aria-hidden="true"><TicketX size={20} /></span>
              <div>
                <strong>{REASON_HEADINGS[check.reason] ?? 'That link is not usable'}</strong>
                <p>
                  {check.reason === 'used'
                    ? 'An invitation link registers one person. If this one was forwarded to you, the team can issue another.'
                    : 'The team can issue you a fresh link — it takes a moment, and nothing you have typed is lost.'}
                </p>
                <div className="signin-actions">
                  <Link className="button button-primary" to="/contact">
                    Request a new link <ArrowRight size={15} aria-hidden="true" />
                  </Link>
                  <Link className="button button-outline" to="/signin">Sign in instead</Link>
                </div>
              </div>
            </div>
          </div>
          <ContactAside />
        </section>
      </>
    )
  }

  if (needsInvite && check.kind === 'unreachable') {
    return (
      <>
        <Hero
          crumb="LINK UNCHECKED"
          eyebrow="INVITATION"
          title={<>We could not<br /><em>check your link.</em></>}
          note="The site is still here, but the invitation check did not come back. Try again before you fill in your details."
        />
        <section className="auth-content section-shell">
          <div className="auth-panel">
            <span className="auth-panel-kicker">TRY AGAIN</span>
            <div className="invite-state" role="status">
              <span className="invite-state-icon" aria-hidden="true"><RefreshCw size={20} /></span>
              <div>
                <strong>The invitation check did not answer</strong>
                <p>Nothing has been registered and your link has not been used. Check your connection and try again.</p>
                <div className="signin-actions">
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={() => { setCheck({ kind: 'checking' }); setAttempt((current) => current + 1) }}
                  >
                    Check my link again <RefreshCw size={15} aria-hidden="true" />
                  </button>
                  <Link className="button button-outline" to="/contact">Contact the team</Link>
                </div>
              </div>
            </div>
          </div>
          <ContactAside />
        </section>
      </>
    )
  }

  const expiresAt = needsInvite && check.kind === 'ready' ? check.expiresAt : null

  return (
    <>
      <Hero
        crumb="CREATE ACCOUNT"
        eyebrow="YOUR INVITATION"
        title={<>Two details,<br /><em>then the bench.</em></>}
        note="Your invitation link is ready. Add your email address and phone number, choose a password, and you will be signed in straight away."
      />

      <section className="auth-content section-shell">
        <div className="auth-panel">
          <span className="auth-panel-kicker">CREATE YOUR ACCOUNT</span>
          {expiresAt && (
            <p className="invite-expiry">
              This link is valid until {new Date(expiresAt).toLocaleString()} and registers one person.
            </p>
          )}
          <LearnerAuthForm mode="signup" next={next} invite={needsInvite ? invite : undefined} />
        </div>
        <InvitationAside />
      </section>
    </>
  )
}

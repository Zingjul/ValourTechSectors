import { Suspense, useEffect, useState, type PropsWithChildren } from 'react'
import { ArrowUpRight, CircleUserRound, LogOut, Menu, X } from 'lucide-react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { getSiteProfile, type SiteProfile } from '../api'
import { useAuth } from '../auth/useAuth'
import { LoadingState } from './States'

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [pathname])
  return null
}

function PageFrame({ children }: PropsWithChildren) {
  return <div className="page-frame">{children}</div>
}

/**
 * The account end of the navigation. Visitors get a way in; signed-in learners
 * see who they are and how to sign out on a shared device.
 */
function AccountNavigation({ onNavigate }: { onNavigate: () => void }) {
  const { status, learner, isAuthenticated, signOut } = useAuth()

  if (status === 'loading') return <span className="nav-account-skeleton" aria-hidden="true" />

  if (!isAuthenticated) return (
    <>
      <NavLink to="/signin" onClick={onNavigate} className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Sign in</NavLink>
      <NavLink className="nav-cta" to="/signup" onClick={onNavigate}>Create free account <ArrowUpRight size={16} aria-hidden="true" /></NavLink>
    </>
  )

  return (
    <>
      <span className="account-chip" title={learner?.email}>
        <CircleUserRound size={15} aria-hidden="true" />
        <span className="account-email">{learner?.email}</span>
      </span>
      <button
        type="button"
        className="nav-link sign-out-button"
        onClick={() => { onNavigate(); signOut().catch(() => undefined) }}
      >
        Sign out <LogOut size={14} aria-hidden="true" />
      </button>
    </>
  )
}

function HeaderNavigation() {
  const [menuOpen, setMenuOpen] = useState(false)
  const closeMenu = () => setMenuOpen(false)
  return (
    <>
      <button
        className="menu-toggle"
        type="button"
        aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
        aria-expanded={menuOpen}
        aria-controls="primary-navigation"
        onClick={() => setMenuOpen((open) => !open)}
      >
        {menuOpen ? <X size={21} aria-hidden="true" /> : <Menu size={21} aria-hidden="true" />}
      </button>
      <nav id="primary-navigation" className={`primary-navigation${menuOpen ? ' is-open' : ''}`} aria-label="Main navigation">
        <NavLink to="/courses" onClick={closeMenu} className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Courses</NavLink>
        <a className="nav-link" href="/#approach" onClick={closeMenu}>How we teach</a>
        <NavLink to="/contact" onClick={closeMenu} className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Contact</NavLink>
        <AccountNavigation onNavigate={closeMenu} />
      </nav>
    </>
  )
}

function FooterAccountLinks() {
  const { isAuthenticated } = useAuth()
  if (isAuthenticated) return <Link to="/courses">My lessons</Link>
  return (
    <>
      <Link to="/signin">Sign in</Link>
      <Link to="/signup">Create account</Link>
    </>
  )
}

export function SiteLayout() {
  const [profile, setProfile] = useState<SiteProfile | null>(null)
  const location = useLocation()

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    getSiteProfile({ signal: controller.signal }).then((data) => {
      if (active) setProfile(data)
    }).catch(() => undefined)
    return () => { active = false; controller.abort() }
  }, [])

  return (
    <PageFrame>
      <ScrollToTop />
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="site-header">
        <Link className="wordmark" to="/" aria-label="ValourTech Sectors home">
          <span className="wordmark-name">ValourTech</span>
          <span className="wordmark-sub">Sectors <i aria-hidden="true">/</i> Learning</span>
        </Link>
        <HeaderNavigation key={location.pathname} />
      </header>

      <main id="main-content" tabIndex={-1}>
        <Suspense fallback={<section className="section-shell detail-shell"><LoadingState label="Opening page…" /></section>}>
          <Outlet />
        </Suspense>
      </main>

      <footer className="site-footer">
        <div className="footer-top">
          <div className="footer-brand">
            <Link className="wordmark footer-wordmark" to="/">
              <span className="wordmark-name">ValourTech</span>
              <span className="wordmark-sub">Sectors <i aria-hidden="true">/</i> Learning</span>
            </Link>
            <p>Practical lessons for understanding the parts inside a circuit.</p>
          </div>
          <div className="footer-links">
            <div>
              <span className="footer-label">Explore</span>
              <Link to="/courses">All courses</Link>
              <Link to="/contact">Contact</Link>
              <FooterAccountLinks />
            </div>
            <div>
              <span className="footer-label">Follow</span>
              {profile?.social_links.length ? profile.social_links.map((link) => (
                <a key={link.id} href={link.url} target="_blank" rel="noreferrer">
                  {link.label} <ArrowUpRight size={13} aria-hidden="true" />
                </a>
              )) : <span className="muted-note">Social links coming soon</span>}
            </div>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} {profile?.brand_name || 'ValourTech Sectors'}</span>
          <a href="/admin/" className="staff-link">Staff access <ArrowUpRight size={13} aria-hidden="true" /></a>
        </div>
      </footer>
    </PageFrame>
  )
}

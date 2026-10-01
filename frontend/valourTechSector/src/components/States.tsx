import { AlertCircle, ArrowRight, BookOpen, KeyRound, LockKeyhole } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { withNext } from '../auth/nextPath'

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return <div className="state-panel" role="status"><span className="loading-dot" aria-hidden="true" />{label}</div>
}

export function ErrorState({ message }: { message: string }) {
  return <div className="state-panel state-error" role="alert"><AlertCircle size={19} aria-hidden="true" />{message}</div>
}

export function EmptyCourses({ filtered = false }: { filtered?: boolean }) {
  return (
    <div className="empty-state">
      <span className="empty-icon"><BookOpen size={23} aria-hidden="true" /></span>
      <h2>{filtered ? 'No courses match those filters.' : 'New lessons are being prepared.'}</h2>
      <p>{filtered ? 'Try a different component name or level to widen your search.' : 'There aren’t any published courses to show yet. Check back soon for notes, demonstrations, and component guides.'}</p>
      <Link className="text-link" to={filtered ? '/courses' : '/contact'}>{filtered ? 'Clear filters' : 'Get in touch'} <span aria-hidden="true">↗</span></Link>
    </div>
  )
}

export function LockedNotice({ message }: { message?: string }) {
  return (
    <aside className="locked-notice" role="status">
      <span className="locked-icon"><LockKeyhole size={17} aria-hidden="true" /></span>
      <div><strong>Access paused</strong><p>{message || 'This learning material is currently locked.'}</p></div>
    </aside>
  )
}

/**
 * What a visitor sees instead of lesson content. Registration is by invitation,
 * so the second button asks for access rather than pointing at a sign-up page
 * that would refuse them.
 */
export function SignInNotice({ message, next, lessonTitle }: { message?: string; next: string; lessonTitle?: string }) {
  const { registration } = useAuth()
  return (
    <aside className="signin-notice" role="status">
      <span className="signin-icon"><KeyRound size={18} aria-hidden="true" /></span>
      <div>
        <strong>{lessonTitle ? `Sign in to open ${lessonTitle}` : 'Sign in to continue'}</strong>
        <p>{message || 'Lesson notes, videos, and downloads are for signed-in learners.'}</p>
        <div className="signin-actions">
          <Link className="button button-primary" to={withNext('/signin', next)}>Sign in <ArrowRight size={15} aria-hidden="true" /></Link>
          {registration === 'open' ? (
            <Link className="button button-outline" to={withNext('/signup', next)}>Create a free account</Link>
          ) : (
            <Link className="button button-outline" to="/contact">Request access</Link>
          )}
        </div>
      </div>
    </aside>
  )
}

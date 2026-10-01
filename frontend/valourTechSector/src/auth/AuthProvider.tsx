import { useCallback, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react'
import {
  getSession,
  signInAccount,
  signOutAccount,
  signUpAccount,
  type ContentAccess,
  type Learner,
  type SessionResponse,
  type SignInCredentials,
  type SignUpDetails,
} from '../api'
import { AuthContext, type AuthContextValue } from './context'

/**
 * Owns the learner session for the whole site.
 *
 * The session is asked for once on load and kept in memory only (never in
 * localStorage), so nothing sensitive is written to disk and a sign-out really
 * ends it. If the session call fails the site still renders: the visitor sees
 * the public pages and sign-in prompts instead of a broken screen.
 */
export function AuthProvider({ children }: PropsWithChildren) {
  const [status, setStatus] = useState<AuthContextValue['status']>('loading')
  const [learner, setLearner] = useState<Learner | null>(null)
  const [contentAccess, setContentAccess] = useState<ContentAccess>('lessons')
  const [signInPath, setSignInPath] = useState('/signin')
  const [csrfToken, setCsrfToken] = useState('')
  const mounted = useRef(true)

  const applySession = useCallback((session: SessionResponse) => {
    setLearner(session.learner)
    setContentAccess(session.content_access)
    setSignInPath(session.sign_in_path || '/signin')
    // Sign-up, sign-in, and sign-out each rotate the CSRF secret, so the browser
    // has to take the new token instead of keeping the one it started with.
    if (session.csrf_token) setCsrfToken(session.csrf_token)
  }, [])

  useEffect(() => {
    mounted.current = true
    const controller = new AbortController()
    getSession({ signal: controller.signal })
      .then((session) => {
        if (!mounted.current) return
        applySession(session)
        setStatus('ready')
      })
      .catch(() => {
        if (!mounted.current) return
        setLearner(null)
        setStatus('ready')
      })
    return () => {
      mounted.current = false
      controller.abort()
    }
  }, [applySession])

  const signIn = useCallback(async (credentials: SignInCredentials) => {
    const session = await signInAccount(credentials, csrfToken)
    applySession(session)
    return session.learner
  }, [applySession, csrfToken])

  const signUp = useCallback(async (details: SignUpDetails) => {
    const session = await signUpAccount(details, csrfToken)
    applySession(session)
    return session.learner
  }, [applySession, csrfToken])

  const signOut = useCallback(async () => {
    const session = await signOutAccount(csrfToken)
    applySession(session)
    setLearner(null)
  }, [applySession, csrfToken])

  const value = useMemo<AuthContextValue>(() => ({
    status,
    learner,
    isAuthenticated: learner !== null,
    contentAccess,
    signInPath,
    csrfToken,
    signIn,
    signUp,
    signOut,
  }), [status, learner, contentAccess, signInPath, csrfToken, signIn, signUp, signOut])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

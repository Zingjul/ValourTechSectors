import { createContext } from 'react'
import type { ContentAccess, Learner, SignInCredentials, SignUpDetails } from '../api'

export type AuthStatus = 'loading' | 'ready'

export type AuthContextValue = {
  /** 'loading' until the first session answer arrives, so pages can wait. */
  status: AuthStatus
  learner: Learner | null
  isAuthenticated: boolean
  contentAccess: ContentAccess
  signInPath: string
  /** Posted back as X-CSRFToken; the cookie itself stays HttpOnly. */
  csrfToken: string
  signIn: (credentials: SignInCredentials) => Promise<Learner | null>
  signUp: (details: SignUpDetails) => Promise<Learner | null>
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

import { useState, type ChangeEvent, type FormEvent } from 'react'
import { ArrowRight, AtSign, Eye, EyeOff, KeyRound, LockKeyhole, Phone } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { fieldErrors, isAccountTaken, type SignInCredentials, type SignUpDetails } from '../api'
import { useAuth } from '../auth/useAuth'
import { withNext } from '../auth/nextPath'

type Mode = 'signin' | 'signup'
type Values = { email: string; phone_number: string; password: string; confirm_password: string }
type Errors = Record<string, string[]>

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/
const PHONE_PATTERN = /^\+?\d{7,15}$/
const EMPTY: Values = { email: '', phone_number: '', password: '', confirm_password: '' }

function normalizedPhone(value: string) {
  return value.replace(/[\s().-]/g, '')
}

/**
 * The same rules the API applies, checked before the round trip so a typo is
 * caught instantly. The server still validates everything; these messages only
 * save the learner a wait.
 */
function localErrors(mode: Mode, values: Values): Errors {
  const errors: Errors = {}
  const email = values.email.trim()
  if (!email) errors.email = ['Enter your email address.']
  else if (!EMAIL_PATTERN.test(email)) errors.email = ['Enter a valid email address, for example ada@example.com.']

  if (mode === 'signup') {
    const phone = normalizedPhone(values.phone_number)
    if (!phone) errors.phone_number = ['Enter a phone number we can reach you on.']
    else if (!PHONE_PATTERN.test(phone)) errors.phone_number = ['Enter 7 to 15 digits, for example +234 803 123 4567.']
    if (!values.password) errors.password = ['Choose a password.']
    else if (values.password.length < 8) errors.password = ['Use at least 8 characters.']
    else if (/^\d+$/.test(values.password)) errors.password = ['Numbers alone are too easy to guess. Add letters or symbols.']
    if (values.confirm_password !== values.password) errors.confirm_password = ['The two passwords do not match.']
  } else if (!values.password) {
    errors.password = ['Enter your password.']
  }
  return errors
}

function FieldError({ id, messages }: { id: string; messages?: string[] }) {
  if (!messages?.length) return null
  return <p className="auth-error" id={id} role="alert">{messages[0]}</p>
}

export function LearnerAuthForm({ mode, next }: { mode: Mode; next: string }) {
  const { signIn, signUp } = useAuth()
  const navigate = useNavigate()
  const [values, setValues] = useState<Values>(EMPTY)
  const [remember, setRemember] = useState(false)
  const [revealed, setRevealed] = useState(false)
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState('')
  const [accountTaken, setAccountTaken] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const isSignUp = mode === 'signup'

  function update(field: keyof Values) {
    return (event: ChangeEvent<HTMLInputElement>) => {
      const value = event.currentTarget.value
      setValues((current) => ({ ...current, [field]: value }))
      // Clear a field's complaint as soon as the learner starts fixing it.
      setErrors((current) => {
        if (!current[field]) return current
        const next = { ...current }
        delete next[field]
        return next
      })
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return
    const found = localErrors(mode, values)
    setErrors(found)
    setAccountTaken(false)
    if (Object.keys(found).length > 0) {
      setFormError('Please correct the highlighted fields.')
      return
    }
    setFormError('')
    setSubmitting(true)
    try {
      if (isSignUp) {
        const details: SignUpDetails = {
          email: values.email.trim(),
          phone_number: values.phone_number.trim(),
          password: values.password,
          confirm_password: values.confirm_password,
          remember,
        }
        await signUp(details)
      } else {
        const credentials: SignInCredentials = { email: values.email.trim(), password: values.password, remember }
        await signIn(credentials)
      }
      navigate(next, { replace: true })
    } catch (error) {
      setSubmitting(false)
      const serverErrors = fieldErrors(error)
      const taken = isAccountTaken(error)
      const message = error instanceof Error ? error.message : 'Something went wrong. Please try again.'
      setErrors(serverErrors)
      setAccountTaken(taken)
      // The note explains a duplicate email, and a field already shows its own
      // message, so the form-level line only appears when it adds something.
      const alreadyShown = taken || Object.values(serverErrors).flat().includes(message)
      setFormError(alreadyShown ? '' : message)
    }
  }

  const describedBy = (field: keyof Values) => (errors[field]?.length ? `${field}-error` : undefined)

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <div className="auth-field">
        <label htmlFor="email">Email address</label>
        <span className="auth-input">
          <AtSign size={17} aria-hidden="true" />
          <input
            id="email"
            name="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="ada@example.com"
            value={values.email}
            onChange={update('email')}
            aria-invalid={errors.email ? true : undefined}
            aria-describedby={describedBy('email')}
            required
          />
        </span>
        <FieldError id="email-error" messages={errors.email} />
      </div>

      {isSignUp && (
        <div className="auth-field">
          <label htmlFor="phone_number">Phone number</label>
          <span className="auth-input">
            <Phone size={17} aria-hidden="true" />
            <input
              id="phone_number"
              name="phone_number"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="+234 803 123 4567"
              value={values.phone_number}
              onChange={update('phone_number')}
              aria-invalid={errors.phone_number ? true : undefined}
              aria-describedby={describedBy('phone_number')}
              required
            />
          </span>
          <p className="auth-hint" id="phone_number-hint">Used to reach you about your lessons. It is never shown on the site.</p>
          <FieldError id="phone_number-error" messages={errors.phone_number} />
        </div>
      )}

      <div className="auth-field">
        <label htmlFor="password">Password</label>
        <span className="auth-input">
          <KeyRound size={17} aria-hidden="true" />
          <input
            id="password"
            name="password"
            type={revealed ? 'text' : 'password'}
            autoComplete={isSignUp ? 'new-password' : 'current-password'}
            placeholder={isSignUp ? 'At least 8 characters' : 'Your password'}
            value={values.password}
            onChange={update('password')}
            aria-invalid={errors.password ? true : undefined}
            aria-describedby={describedBy('password')}
            required
          />
          <button
            type="button"
            className="reveal-toggle"
            onClick={() => setRevealed((shown) => !shown)}
            aria-label={revealed ? 'Hide password' : 'Show password'}
          >
            {revealed ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
          </button>
        </span>
        {isSignUp && <p className="auth-hint">At least 8 characters, and not only numbers.</p>}
        <FieldError id="password-error" messages={errors.password} />
      </div>

      {isSignUp && (
        <div className="auth-field">
          <label htmlFor="confirm_password">Confirm password</label>
          <span className="auth-input">
            <LockKeyhole size={17} aria-hidden="true" />
            <input
              id="confirm_password"
              name="confirm_password"
              type={revealed ? 'text' : 'password'}
              autoComplete="new-password"
              placeholder="Type it once more"
              value={values.confirm_password}
              onChange={update('confirm_password')}
              aria-invalid={errors.confirm_password ? true : undefined}
              aria-describedby={describedBy('confirm_password')}
              required
            />
          </span>
          <FieldError id="confirm_password-error" messages={errors.confirm_password} />
        </div>
      )}

      <label className="auth-checkbox">
        <input type="checkbox" name="remember" checked={remember} onChange={(event) => setRemember(event.currentTarget.checked)} />
        <span>Keep me signed in on this device</span>
      </label>

      {formError && <p className="auth-form-error" role="alert">{formError}</p>}
      {accountTaken && (
        <p className="auth-form-note">
          Already registered? <Link to={withNext('/signin', next)}>Sign in instead</Link>.
        </p>
      )}

      <button className="button button-primary auth-submit" type="submit" disabled={submitting}>
        {submitting ? (isSignUp ? 'Creating your account…' : 'Signing you in…') : (isSignUp ? 'Create my account' : 'Sign in')}
        {!submitting && <ArrowRight size={16} aria-hidden="true" />}
      </button>

      <p className="auth-switch">
        {isSignUp ? (
          <>Already have an account? <Link to={withNext('/signin', next)}>Sign in</Link></>
        ) : (
          <>New here? <Link to={withNext('/signup', next)}>Create a free account</Link></>
        )}
      </p>
    </form>
  )
}

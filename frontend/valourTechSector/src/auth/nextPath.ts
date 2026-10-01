/**
 * Where to send a learner after they sign in.
 *
 * The value comes from a URL query string, so it is untrusted: only a relative
 * path on this same origin is accepted. Anything protocol-relative (`//host`),
 * absolute (`https://host`), backslash-tricked (`/\\host`), or pointing back at
 * the auth pages falls back to the course library.
 */
const FALLBACK = '/courses'

export function safeNextPath(raw: string | null | undefined, fallback: string = FALLBACK): string {
  if (typeof raw !== 'string' || raw.length === 0 || raw.length > 400) return fallback
  if (!raw.startsWith('/') || raw.startsWith('//') || raw.startsWith('/\\')) return fallback
  if (/[\s\\]/.test(raw)) return fallback
  const path = raw.split('?')[0].split('#')[0].replace(/\/+$/, '')
  if (path === '/signin' || path === '/signup' || path === '' || path === '/admin') return fallback
  return raw
}

export function withNext(path: string, next: string): string {
  return next && next !== FALLBACK ? `${path}?next=${encodeURIComponent(next)}` : path
}

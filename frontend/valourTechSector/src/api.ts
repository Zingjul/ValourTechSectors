export class ApiError extends Error {
  status: number
  payload: unknown

  constructor(message: string, status: number, payload: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

export type RequestOptions = {
  signal?: AbortSignal
  method?: 'GET' | 'POST'
  body?: Record<string, unknown>
  /** Sent as X-CSRFToken; the API returns it because the CSRF cookie is HttpOnly. */
  csrfToken?: string
}
const REQUEST_TIMEOUT_MS = 15_000

async function request<T>(path: string, { signal, method, body, csrfToken }: RequestOptions = {}): Promise<T> {
  const controller = new AbortController()
  const cancel = () => controller.abort()
  if (signal?.aborted) cancel()
  signal?.addEventListener('abort', cancel, { once: true })
  const timeout = setTimeout(cancel, REQUEST_TIMEOUT_MS)

  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (csrfToken) headers['X-CSRFToken'] = csrfToken

  try {
    const response = await fetch(path, {
      method: method ?? 'GET',
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: 'same-origin',
      cache: 'no-store',
      signal: controller.signal,
    })
    const contentType = response.headers.get('Content-Type') || ''
    const payload: unknown = contentType.includes('application/json')
      ? await response.json().catch(() => null)
      : null
    if (!response.ok) {
      let message = response.status >= 500
        ? 'The learning service is temporarily unavailable. Please try again.'
        : response.status === 429
          ? 'Too many requests. Please wait a moment and try again.'
          : response.status === 401
            ? 'Sign in to continue.'
            : `Request failed (${response.status}).`
      if (typeof payload === 'object' && payload !== null) {
        if ('message' in payload && typeof payload.message === 'string') message = payload.message
        else if ('error' in payload && typeof payload.error === 'string') message = payload.error
      }
      throw new ApiError(message, response.status, payload)
    }
    // A missing proxy route must not be mistaken for successful JSON data.
    if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
      throw new ApiError('The learning service returned an unexpected response. Please try again.', response.status, null)
    }
    return payload as T
  } catch (error) {
    if (signal?.aborted) throw new DOMException('Request cancelled.', 'AbortError')
    if (controller.signal.aborted) {
      throw new ApiError('The request timed out. Please check your connection and try again.', 0, null)
    }
    if (error instanceof ApiError) throw error
    throw new ApiError('The learning service is not reachable right now. Please try again.', 0, null)
  } finally {
    clearTimeout(timeout)
    signal?.removeEventListener('abort', cancel)
  }
}

export type Course = {
  id: number
  title: string
  slug: string
  summary: string
  description: string
  level: 'beginner' | 'intermediate' | 'advanced'
  level_label: string
  estimated_minutes: number
  is_locked: boolean
  lock_notice: string
  /** True when the outline below is listed but its lessons need a sign-in. */
  sign_in_required: boolean
  sign_in_message: string
  url: string
}

export type Material = {
  id: number
  title: string
  description: string
  kind: 'pdf' | 'word'
  kind_label: string
  file_name: string
  extension: string
  is_locked: boolean
  lock_notice: string
  /** True while the file stays closed because nobody is signed in. */
  sign_in_required: boolean
  download_url: string | null
}

export type Video = {
  id: number
  title: string
  platform: 'youtube' | 'tiktok' | 'instagram' | 'facebook'
  platform_label: string
  source_url: string
  embed_url: string | null
}

export type LessonOutline = {
  id: number
  title: string
  slug: string
  summary: string
  estimated_minutes: number
  is_locked: boolean
  lock_notice: string
  sign_in_required: boolean
  url: string
  notes: string
  safety_notice: string
  videos: Video[]
  materials: Material[]
}

export type Section = {
  id: number
  title: string
  description: string
  is_locked: boolean
  lock_notice: string
  lessons: LessonOutline[]
}

export type CourseDetail = Course & { sections: Section[] }

export type CatalogResponse = {
  count: number
  page: number
  pages: number
  has_next: boolean
  has_previous: boolean
  results: Course[]
}

export type LessonDetail = Omit<LessonOutline, 'is_locked' | 'lock_notice' | 'url' | 'sign_in_required'> & {
  course: { title: string; slug: string }
  section: { title: string; id: number }
}

export type SocialLink = {
  id: number
  platform: string
  platform_label: string
  label: string
  url: string
}

export type SiteProfile = {
  brand_name: string
  tagline: string
  contact_email: string
  phone_number: string
  whatsapp_url: string
  contact_note: string
  social_links: SocialLink[]
}

export type Learner = {
  email: string
  phone_number: string
  member_since: string
  last_sign_in: string
}

/** How much of the site an account opens, decided by LEARNER_CONTENT_ACCESS. */
export type ContentAccess = 'open' | 'lessons' | 'everything'

/**
 * Whether an account needs a link from the owner first, decided by
 * LEARNER_REGISTRATION. 'invite' hides sign-up from the public site.
 */
export type RegistrationMode = 'invite' | 'open'

export type SessionResponse = {
  authenticated: boolean
  learner: Learner | null
  content_access: ContentAccess
  registration: RegistrationMode
  sign_in_path: string
  csrf_token: string
}

export type SignUpDetails = {
  email: string
  phone_number: string
  password: string
  confirm_password: string
  remember: boolean
  /** The single-use link staff issued. Required unless registration is open. */
  invite?: string
}

export type SignInCredentials = { email: string; password: string; remember: boolean }

export type FieldErrors = Record<string, string[]>

/** The 401 body the API sends instead of lesson content. */
export type SignInRequiredPayload = {
  sign_in_required: true
  message: string
  sign_in_path: string
  next?: string
  lesson?: Omit<LessonDetail, 'notes' | 'safety_notice' | 'videos' | 'materials'>
}

function payloadOf(error: unknown): Record<string, unknown> | null {
  if (!(error instanceof ApiError) || typeof error.payload !== 'object' || error.payload === null) return null
  return error.payload as Record<string, unknown>
}

/** True when the API withheld content because no learner is signed in. */
export function isSignInRequired(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401 && payloadOf(error)?.sign_in_required === true
}

export function signInRequiredPayload(error: unknown): SignInRequiredPayload | null {
  if (!isSignInRequired(error)) return null
  return payloadOf(error) as unknown as SignInRequiredPayload
}

/** What the API says about an invitation link before a form is shown. */
export type InviteStatus = {
  registration: RegistrationMode
  valid: boolean
  reason?: 'missing' | 'unknown' | 'used' | 'expired' | 'revoked'
  message: string
  expires_at?: string | null
  sign_in_path?: string
}

/** True when sign-up was refused for want of a usable invitation link. */
export function isInviteProblem(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status !== 403) return false
  const payload = payloadOf(error)
  return payload?.invite_required === true || payload?.invite_invalid === true
}

/** True when the email address already has an account, so sign-in is the way in. */
export function isAccountTaken(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409 && payloadOf(error)?.account_exists === true
}

/** Per-field messages from a rejected sign-up or sign-in, safe to render. */
export function fieldErrors(error: unknown): FieldErrors {
  const errors = payloadOf(error)?.errors
  if (typeof errors !== 'object' || errors === null) return {}
  const normalized: FieldErrors = {}
  for (const [field, messages] of Object.entries(errors as Record<string, unknown>)) {
    if (typeof messages === 'string') normalized[field] = [messages]
    else if (Array.isArray(messages)) normalized[field] = messages.filter((line): line is string => typeof line === 'string')
  }
  return normalized
}

export function getSession(options?: RequestOptions) {
  return request<SessionResponse>('/api/v1/auth/session/', options)
}

export function signUpAccount(details: SignUpDetails, csrfToken: string, options?: RequestOptions) {
  return request<SessionResponse>('/api/v1/auth/signup/', { ...options, method: 'POST', body: details, csrfToken })
}

/** Ask whether a link can still register someone, without spending it. */
export function getInviteStatus(token: string, options?: RequestOptions) {
  return request<InviteStatus>(`/api/v1/auth/invite/${encodeURIComponent(token)}/`, options)
}

export function signInAccount(credentials: SignInCredentials, csrfToken: string, options?: RequestOptions) {
  return request<SessionResponse>('/api/v1/auth/signin/', { ...options, method: 'POST', body: credentials, csrfToken })
}

export function signOutAccount(csrfToken: string, options?: RequestOptions) {
  return request<SessionResponse>('/api/v1/auth/signout/', { ...options, method: 'POST', body: {}, csrfToken })
}

export function getCourses(params = new URLSearchParams(), options?: RequestOptions) {
  const query = params.toString()
  return request<CatalogResponse>(`/api/v1/courses/${query ? `?${query}` : ''}`, options)
}

export function getCourse(slug: string, options?: RequestOptions) {
  return request<CourseDetail>(`/api/v1/courses/${encodeURIComponent(slug)}/`, options)
}

export function getLesson(slug: string, options?: RequestOptions) {
  return request<LessonDetail>(`/api/v1/lessons/${encodeURIComponent(slug)}/`, options)
}

export function getSiteProfile(options?: RequestOptions) {
  return request<SiteProfile>('/api/v1/site-profile/', options)
}

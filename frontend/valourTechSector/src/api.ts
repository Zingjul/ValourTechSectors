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

export type RequestOptions = { signal?: AbortSignal }
const REQUEST_TIMEOUT_MS = 15_000

async function request<T>(path: string, { signal }: RequestOptions = {}): Promise<T> {
  const controller = new AbortController()
  const cancel = () => controller.abort()
  if (signal?.aborted) cancel()
  signal?.addEventListener('abort', cancel, { once: true })
  const timeout = setTimeout(cancel, REQUEST_TIMEOUT_MS)

  try {
    const response = await fetch(path, {
      headers: { Accept: 'application/json' },
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

export type LessonDetail = Omit<LessonOutline, 'is_locked' | 'lock_notice' | 'url'> & {
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

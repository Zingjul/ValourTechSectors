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

async function request<T>(path: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: 'application/json' } })
  } catch {
    throw new ApiError('The learning service is not reachable right now. Please try again.', 0, null)
  }

  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const message =
      typeof payload === 'object' && payload !== null && 'message' in payload
        ? String(payload.message)
        : `Request failed (${response.status}).`
    throw new ApiError(message, response.status, payload)
  }
  return payload as T
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

export function getCourses(params = new URLSearchParams()) {
  const query = params.toString()
  return request<CatalogResponse>(`/api/v1/courses/${query ? `?${query}` : ''}`)
}

export function getCourse(slug: string) {
  return request<CourseDetail>(`/api/v1/courses/${encodeURIComponent(slug)}/`)
}

export function getLesson(slug: string) {
  return request<LessonDetail>(`/api/v1/lessons/${encodeURIComponent(slug)}/`)
}

export function getSiteProfile() {
  return request<SiteProfile>('/api/v1/site-profile/')
}

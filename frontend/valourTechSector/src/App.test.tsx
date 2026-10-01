import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import App from './App'
import { ApiError, getCourse, getCourses, getLesson, getSession, getSiteProfile, type CatalogResponse, type CourseDetail, type LessonDetail, type SessionResponse, type SiteProfile } from './api'

vi.mock('./api', async (importOriginal) => ({
  ...await importOriginal<typeof import('./api')>(),
  getCourses: vi.fn(), getCourse: vi.fn(), getLesson: vi.fn(), getSession: vi.fn(), getSiteProfile: vi.fn(),
}))

const catalog: CatalogResponse = {
  count: 1, page: 1, pages: 1, has_next: false, has_previous: false,
  results: [{
    id: 1, title: 'Resistors', slug: 'resistors', summary: 'Resistance made clear.', description: '',
    level: 'beginner', level_label: 'Beginner', estimated_minutes: 20, is_locked: false,
    lock_notice: '', sign_in_required: false, sign_in_message: '', url: '/api/v1/courses/resistors/',
  }],
}
const signedOut: SessionResponse = {
  authenticated: false, learner: null, content_access: 'lessons', sign_in_path: '/signin', csrf_token: 'token-1',
}
const profile: SiteProfile = {
  brand_name: 'ValourTech Sectors', tagline: '', contact_email: '', phone_number: '',
  whatsapp_url: '', contact_note: '', social_links: [],
}
const course: CourseDetail = { ...catalog.results[0], sections: [] }
const lesson: LessonDetail = {
  id: 1, title: 'Resistance in ohms', slug: 'ohms', summary: '', estimated_minutes: 10,
  notes: 'Resistance is measured in ohms.', safety_notice: 'Disconnect the power first.',
  videos: [], materials: [], course: { title: 'Resistors', slug: 'resistors' }, section: { id: 1, title: 'Basics' },
}

function renderRoute(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
}

beforeEach(() => {
  vi.mocked(getSession).mockResolvedValue(signedOut)
  vi.mocked(getCourses).mockResolvedValue(catalog)
  vi.mocked(getSiteProfile).mockResolvedValue(profile)
  vi.mocked(getCourse).mockResolvedValue(course)
  vi.mocked(getLesson).mockResolvedValue(lesson)
})

describe('learner routes', () => {
  it('loads the course library and submits real search/level filters', async () => {
    renderRoute('/courses')
    expect(await screen.findByRole('heading', { name: 'Resistors', level: 3 })).toBeInTheDocument()
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search courses' }), { target: { value: 'capacitor' } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by level' }), { target: { value: 'intermediate' } })
    fireEvent.click(screen.getByRole('button', { name: /Find courses/ }))
    await waitFor(() => {
      const params = vi.mocked(getCourses).mock.calls.at(-1)?.[0]
      expect(params?.get('q')).toBe('capacitor')
      expect(params?.get('level')).toBe('intermediate')
    })
  })

  it('uses the server-normalized page for pagination, not untrusted URL input', async () => {
    vi.mocked(getCourses).mockResolvedValue({ ...catalog, count: 30, page: 2, pages: 3, has_next: true, has_previous: true })
    renderRoute('/courses?page=999')
    await screen.findByText('Page 2 of 3')
    fireEvent.click(screen.getByRole('button', { name: /Next/ }))
    await waitFor(() => expect(vi.mocked(getCourses).mock.calls.at(-1)?.[0]?.get('page')).toBe('3'))
  })

  it('shows a lock notice without rendering lesson content or download links', async () => {
    vi.mocked(getLesson).mockRejectedValue(new ApiError('This lesson is not open yet.', 403, { locked: true }))
    renderRoute('/lessons/locked')
    expect(await screen.findByText('This lesson is not open yet.')).toBeInTheDocument()
    expect(screen.queryByText('Resistance is measured in ohms.')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Download/ })).not.toBeInTheDocument()
  })

  it('turns a withheld lesson into a sign-in prompt that remembers where the learner was going', async () => {
    vi.mocked(getLesson).mockRejectedValue(new ApiError('Sign in to open your lesson notes, videos, and downloads.', 401, {
      sign_in_required: true,
      message: 'Sign in to open your lesson notes, videos, and downloads.',
      sign_in_path: '/signin',
      lesson: {
        id: 1, title: 'Resistance in ohms', slug: 'ohms', summary: '', estimated_minutes: 10,
        course: { title: 'Resistors', slug: 'resistors' }, section: { id: 1, title: 'Basics' },
      },
    }))
    renderRoute('/lessons/ohms')

    await screen.findByText('Sign in to open Resistance in ohms')
    const notice = screen.getByRole('status')
    expect(screen.queryByText('Resistance is measured in ohms.')).not.toBeInTheDocument()
    expect(within(notice).getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/signin?next=%2Flessons%2Fohms')
    expect(within(notice).getByRole('link', { name: /Create a free account/ })).toHaveAttribute('href', '/signup?next=%2Flessons%2Fohms')
  })

  it('renders an open lesson and its safety guidance', async () => {
    renderRoute('/lessons/ohms')
    expect(await screen.findByRole('heading', { name: 'Resistance in ohms' })).toBeInTheDocument()
    expect(screen.getByText('Disconnect the power first.')).toBeInTheDocument()
    expect(screen.getByText('Resistance is measured in ohms.')).toBeInTheDocument()
  })

  it('shows an actionable course-not-found message', async () => {
    vi.mocked(getCourse).mockRejectedValue(new ApiError('Not found', 404, null))
    renderRoute('/courses/missing')
    expect(await screen.findByRole('alert')).toHaveTextContent('We couldn’t find that course')
    expect(screen.getByRole('link', { name: /Back to courses/ })).toBeInTheDocument()
  })

  it('keeps an empty production database usable without inventing sample courses', async () => {
    vi.mocked(getCourses).mockResolvedValue({ ...catalog, count: 0, results: [] })
    renderRoute('/')
    expect(await screen.findByRole('heading', { name: 'New lessons are being prepared.' })).toBeInTheDocument()
  })

  it('renders the learner 404 screen for unknown routes', async () => {
    renderRoute('/unknown-page')
    expect(await screen.findByRole('heading', { name: /on the board/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Back to the home page/ })).toHaveAttribute('href', '/')
  })

  it('cancels an in-flight course request when navigation changes', async () => {
    let signal: AbortSignal | undefined
    vi.mocked(getCourse).mockImplementation((_slug, options) => {
      signal = options?.signal
      return new Promise(() => {})
    })
    renderRoute('/courses/resistors')
    await waitFor(() => expect(signal).toBeDefined())
    fireEvent.click(screen.getByRole('link', { name: 'Courses' }))
    await screen.findByRole('heading', { name: 'Resistors', level: 3 })
    expect(signal?.aborted).toBe(true)
  })
})

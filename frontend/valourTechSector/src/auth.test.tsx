import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import App from './App'
import {
  ApiError,
  getCourse,
  getCourses,
  getLesson,
  getSession,
  getSiteProfile,
  signInAccount,
  signOutAccount,
  signUpAccount,
  type CatalogResponse,
  type CourseDetail,
  type LessonDetail,
  type SessionResponse,
  type SiteProfile,
} from './api'
import { safeNextPath } from './auth/nextPath'

vi.mock('./api', async (importOriginal) => ({
  ...await importOriginal<typeof import('./api')>(),
  getCourses: vi.fn(), getCourse: vi.fn(), getLesson: vi.fn(), getSession: vi.fn(), getSiteProfile: vi.fn(),
  signUpAccount: vi.fn(), signInAccount: vi.fn(), signOutAccount: vi.fn(),
}))

const catalog: CatalogResponse = {
  count: 1, page: 1, pages: 1, has_next: false, has_previous: false,
  results: [{
    id: 1, title: 'Resistors', slug: 'resistors', summary: 'Resistance made clear.', description: '',
    level: 'beginner', level_label: 'Beginner', estimated_minutes: 20, is_locked: false,
    lock_notice: '', sign_in_required: false, sign_in_message: '', url: '/api/v1/courses/resistors/',
  }],
}
const course: CourseDetail = { ...catalog.results[0], sections: [] }
const lesson: LessonDetail = {
  id: 1, title: 'Resistance in ohms', slug: 'ohms', summary: '', estimated_minutes: 10,
  notes: 'Resistance is measured in ohms.', safety_notice: '', videos: [], materials: [],
  course: { title: 'Resistors', slug: 'resistors' }, section: { id: 1, title: 'Basics' },
}
const profile: SiteProfile = {
  brand_name: 'ValourTech Sectors', tagline: '', contact_email: '', phone_number: '',
  whatsapp_url: '', contact_note: '', social_links: [],
}
const signedOut: SessionResponse = {
  authenticated: false, learner: null, content_access: 'lessons', sign_in_path: '/signin', csrf_token: 'token-1',
}
const signedIn: SessionResponse = {
  authenticated: true,
  learner: { email: 'ada@example.com', phone_number: '+2348031234567', member_since: '2026-10-01', last_sign_in: '' },
  content_access: 'lessons', sign_in_path: '/signin', csrf_token: 'token-2',
}

function renderRoute(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
}

function navigation() {
  return within(screen.getByRole('navigation', { name: 'Main navigation' }))
}

async function fillSignUp(details: Partial<Record<'email' | 'phone' | 'password' | 'confirm' | 'remember', string | boolean>> = {}) {
  fireEvent.change(await screen.findByLabelText('Email address'), { target: { value: details.email ?? 'ada@example.com' } })
  fireEvent.change(screen.getByLabelText('Phone number'), { target: { value: details.phone ?? '+234 803 123 4567' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: details.password ?? 'resistor-code' } })
  fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: details.confirm ?? 'resistor-code' } })
  if (details.remember) fireEvent.click(screen.getByRole('checkbox', { name: /Keep me signed in/ }))
}

beforeEach(() => {
  vi.mocked(getSession).mockResolvedValue(signedOut)
  vi.mocked(getCourses).mockResolvedValue(catalog)
  vi.mocked(getCourse).mockResolvedValue(course)
  vi.mocked(getLesson).mockResolvedValue(lesson)
  vi.mocked(getSiteProfile).mockResolvedValue(profile)
  vi.mocked(signUpAccount).mockResolvedValue(signedIn)
  vi.mocked(signInAccount).mockResolvedValue(signedIn)
  vi.mocked(signOutAccount).mockResolvedValue(signedOut)
})

describe('safeNextPath', () => {
  it.each([
    ['/lessons/ohms', '/lessons/ohms'],
    ['/courses/resistors', '/courses/resistors'],
    ['/courses?page=2', '/courses?page=2'],
    [null, '/courses'],
    ['', '/courses'],
    ['//evil.example/courses', '/courses'],
    ['/\\evil.example', '/courses'],
    ['https://evil.example/', '/courses'],
    ['javascript:alert(1)', '/courses'],
    ['/signin', '/courses'],
    ['/signup?next=%2Fadmin', '/courses'],
    ['/admin', '/courses'],
  ])('only accepts a relative path on this origin: %s', (input, expected) => {
    expect(safeNextPath(input)).toBe(expected)
  })
})

describe('sign-up', () => {
  it('records an email address and phone number, then opens the lesson the learner wanted', async () => {
    renderRoute('/signup?next=%2Flessons%2Fohms')

    await fillSignUp({ email: '  Ada@Example.com ' })
    fireEvent.click(screen.getByRole('button', { name: /Create my account/ }))

    await waitFor(() => expect(signUpAccount).toHaveBeenCalledWith({
      email: 'Ada@Example.com',
      phone_number: '+234 803 123 4567',
      password: 'resistor-code',
      confirm_password: 'resistor-code',
      remember: false,
    }, 'token-1'))
    expect(await screen.findByRole('heading', { name: 'Resistance in ohms' })).toBeInTheDocument()
  })

  it('checks the details in the browser before spending a round trip', async () => {
    renderRoute('/signup')

    await fillSignUp({ email: 'ada@', phone: '12', password: '1234567', confirm: '1234567' })
    fireEvent.click(screen.getByRole('button', { name: /Create my account/ }))

    expect(await screen.findByText('Enter a valid email address, for example ada@example.com.')).toBeInTheDocument()
    expect(screen.getByText('Enter 7 to 15 digits, for example +234 803 123 4567.')).toBeInTheDocument()
    expect(screen.getByText('Use at least 8 characters.')).toBeInTheDocument()
    expect(signUpAccount).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Email address')).toHaveAttribute('aria-invalid', 'true')
  })

  it('shows the exact field the server rejected', async () => {
    vi.mocked(signUpAccount).mockRejectedValue(new ApiError('Please correct the highlighted fields.', 400, {
      errors: { phone_number: ['Enter a phone number with 7 to 15 digits.'] },
    }))
    renderRoute('/signup')

    await fillSignUp()
    fireEvent.click(screen.getByRole('button', { name: /Create my account/ }))

    expect(await screen.findByText('Enter a phone number with 7 to 15 digits.')).toBeInTheDocument()
    expect(screen.getByLabelText('Phone number')).toHaveAttribute('aria-invalid', 'true')
  })

  it('points an already-registered email at sign-in instead of making a duplicate', async () => {
    vi.mocked(signUpAccount).mockRejectedValue(new ApiError('That email address already has an account. Sign in instead.', 409, {
      account_exists: true,
      errors: { email: ['That email address already has an account.'] },
    }))
    renderRoute('/signup')

    await fillSignUp()
    fireEvent.click(screen.getByRole('button', { name: /Create my account/ }))

    expect(await screen.findByText('That email address already has an account.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in instead' })).toHaveAttribute('href', '/signin')
  })

  it('keeps the password hidden until the learner asks to see it', async () => {
    renderRoute('/signup')

    const password = await screen.findByLabelText('Password')
    expect(password).toHaveAttribute('type', 'password')
    fireEvent.click(screen.getByRole('button', { name: 'Show password' }))
    expect(password).toHaveAttribute('type', 'text')
    fireEvent.click(screen.getByRole('button', { name: 'Hide password' }))
    expect(password).toHaveAttribute('type', 'password')
  })
})

describe('sign-in', () => {
  it('signs in with the email and password and returns to the withheld lesson', async () => {
    renderRoute('/signin?next=%2Flessons%2Fohms')

    fireEvent.change(await screen.findByLabelText('Email address'), { target: { value: 'ada@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'resistor-code' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => expect(signInAccount).toHaveBeenCalledWith(
      { email: 'ada@example.com', password: 'resistor-code', remember: false },
      'token-1',
    ))
    expect(await screen.findByRole('heading', { name: 'Resistance in ohms' })).toBeInTheDocument()
  })

  it('passes the keep-me-signed-in choice through to the session', async () => {
    renderRoute('/signin')

    fireEvent.change(await screen.findByLabelText('Email address'), { target: { value: 'ada@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'resistor-code' } })
    fireEvent.click(screen.getByRole('checkbox', { name: /Keep me signed in/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => expect(signInAccount).toHaveBeenCalledWith(
      expect.objectContaining({ remember: true }),
      'token-1',
    ))
  })

  it('reports a wrong password and a lockout without inventing a reason', async () => {
    vi.mocked(signInAccount).mockRejectedValue(new ApiError('That email address and password do not match our records.', 401, {
      errors: { password: ['That email address and password do not match our records.'] },
    }))
    renderRoute('/signin')
    fireEvent.change(await screen.findByLabelText('Email address'), { target: { value: 'ada@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('That email address and password do not match our records.')).toBeInTheDocument()

    vi.mocked(signInAccount).mockRejectedValue(new ApiError('Too many sign-in attempts. Try again in 15 minutes.', 429, { locked: true }))
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Too many sign-in attempts. Try again in 15 minutes.')).toBeInTheDocument()
  })

  it('asks for both details before calling the API', async () => {
    renderRoute('/signin')
    fireEvent.click(await screen.findByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Enter your email address.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(signInAccount).not.toHaveBeenCalled()
  })

  it('sends a signed-in learner away from the auth pages', async () => {
    vi.mocked(getSession).mockResolvedValue(signedIn)
    renderRoute('/signin?next=%2Flessons%2Fohms')

    expect(await screen.findByRole('heading', { name: 'Resistance in ohms' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()
  })
})

describe('header account controls', () => {
  it('offers a visitor a way in', async () => {
    renderRoute('/')

    await screen.findByRole('link', { name: /Create free account/ })
    expect(navigation().getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/signin')
    expect(navigation().getByRole('link', { name: /Create free account/ })).toHaveAttribute('href', '/signup')
  })

  it('shows who is signed in and signs them out with the current token', async () => {
    vi.mocked(getSession).mockResolvedValue(signedIn)
    renderRoute('/')

    expect(await screen.findByText('ada@example.com')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Create free account/ })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Sign out/ }))
    await waitFor(() => expect(signOutAccount).toHaveBeenCalledWith('token-2'))
    expect(await screen.findByRole('link', { name: /Create free account/ })).toBeInTheDocument()
  })
})

describe('session resilience', () => {
  it('keeps the site usable when the session call fails', async () => {
    vi.mocked(getSession).mockRejectedValue(new ApiError('The learning service is not reachable right now.', 0, null))
    renderRoute('/courses')

    expect(await screen.findByRole('heading', { name: 'Resistors', level: 3 })).toBeInTheDocument()
    expect(navigation().getByRole('link', { name: /Create free account/ })).toBeInTheDocument()
  })
})

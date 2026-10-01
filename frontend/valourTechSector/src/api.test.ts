import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError, fieldErrors, getCourse, getCourses, getLesson, getSession, getSiteProfile,
  isAccountTaken, isSignInRequired, signInAccount, signInRequiredPayload, signUpAccount,
} from './api'

const fetchMock = vi.fn<typeof fetch>()
function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

describe('production API client', () => {
  it('uses same-origin relative URLs, no-store, and cancellable requests', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ count: 0, results: [] }))
    await getCourses(new URLSearchParams({ q: 'resistor', level: 'beginner' }))
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/courses/?q=resistor&level=beginner', expect.objectContaining({
      credentials: 'same-origin', cache: 'no-store', signal: expect.anything(),
      headers: { Accept: 'application/json' },
    }))
  })

  it('encodes course/lesson slugs instead of allowing URL path injection', async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ id: 1 }))
    await getCourse('unsafe/slug')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/courses/unsafe%2Fslug/')
    await getLesson('unsafe/slug')
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/lessons/unsafe%2Fslug/')
  })

  it('keeps backend lock notices and status codes', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ locked: true, message: 'This section opens next week.' }, 403))
    await expect(getLesson('locked')).rejects.toMatchObject({
      name: 'ApiError', status: 403, message: 'This section opens next week.',
    })
  })

  it('understands both message and error JSON envelopes', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ error: 'Choose a valid course level.' }, 400))
    await expect(getCourses()).rejects.toThrow('Choose a valid course level.')
  })

  it('rejects accidental HTML success responses from a misconfigured SPA proxy', async () => {
    fetchMock.mockResolvedValue(new Response('<html>SPA fallback</html>', { headers: { 'Content-Type': 'text/html' } }))
    await expect(getCourses()).rejects.toThrow('unexpected response')
  })

  it.each([[null], [[]], ['not an object']])('rejects invalid success payloads: %s', async (payload) => {
    fetchMock.mockResolvedValue(jsonResponse(payload))
    await expect(getCourses()).rejects.toBeInstanceOf(ApiError)
  })

  it('handles invalid JSON without returning null as valid course data', async () => {
    fetchMock.mockResolvedValue(new Response('{broken', { headers: { 'Content-Type': 'application/json' } }))
    await expect(getCourses()).rejects.toThrow('unexpected response')
  })

  it('shows a safe useful error when the platform returns a non-JSON 503', async () => {
    fetchMock.mockResolvedValue(new Response('Platform error', { status: 503 }))
    await expect(getCourses()).rejects.toMatchObject({ status: 503, message: expect.stringContaining('temporarily unavailable') })
  })

  it('handles offline/network failures without leaking low-level exception text', async () => {
    fetchMock.mockRejectedValue(new TypeError('private internal proxy details'))
    await expect(getSiteProfile()).rejects.toMatchObject({ status: 0, message: expect.stringContaining('not reachable') })
  })

  it('times out stalled requests instead of leaving the site loading forever', async () => {
    vi.useFakeTimers()
    fetchMock.mockImplementation((_path, options) => new Promise((_resolve, reject) => {
      options?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    }))
    const result = expect(getCourses()).rejects.toThrow('timed out')
    await vi.advanceTimersByTimeAsync(15_000)
    await result
  })

  it('distinguishes navigation cancellation from network failure', async () => {
    const controller = new AbortController()
    fetchMock.mockImplementation((_path, options) => new Promise((_resolve, reject) => {
      options?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    }))
    const result = expect(getCourses(new URLSearchParams(), { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
    controller.abort()
    await result
  })
})

describe('account API calls', () => {
  const session = { authenticated: false, learner: null, content_access: 'lessons', sign_in_path: '/signin', csrf_token: 'next-token' }

  it('posts JSON with the CSRF token the session issued', async () => {
    fetchMock.mockResolvedValue(jsonResponse(session))
    await signInAccount({ email: 'ada@example.com', password: 'resistor-code', remember: false }, 'token-1')
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/signin/', expect.objectContaining({
      method: 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': 'token-1' },
      body: JSON.stringify({ email: 'ada@example.com', password: 'resistor-code', remember: false }),
    }))
  })

  it('keeps reads free of a body and a CSRF header', async () => {
    fetchMock.mockResolvedValue(jsonResponse(session))
    await getSession()
    const [, init] = fetchMock.mock.calls[0]
    expect(init?.method).toBe('GET')
    expect(init?.body).toBeUndefined()
    expect(init?.headers).toEqual({ Accept: 'application/json' })
  })

  it('signs up through the same origin and returns the rotated token', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ...session, authenticated: true }, 201))
    const response = await signUpAccount({
      email: 'ada@example.com', phone_number: '+2348031234567', password: 'resistor-code',
      confirm_password: 'resistor-code', remember: true,
    }, 'token-1')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/auth/signup/')
    expect(response.csrf_token).toBe('next-token')
  })

  it('turns a rejected sign-up into per-field messages', async () => {
    fetchMock.mockResolvedValue(jsonResponse({
      message: 'Please correct the highlighted fields.',
      errors: { email: ['Enter a valid email address.'], password: ['Use at least 8 characters.'] },
    }, 400))
    const error = await signUpAccount({
      email: 'ada@', phone_number: '12', password: 'short', confirm_password: 'short', remember: false,
    }, 'token-1').catch((reason: unknown) => reason)
    expect(fieldErrors(error)).toEqual({ email: ['Enter a valid email address.'], password: ['Use at least 8 characters.'] })
    expect(isSignInRequired(error)).toBe(false)
    expect(isAccountTaken(error)).toBe(false)
  })

  it('recognizes withheld lesson content as a sign-in prompt', async () => {
    fetchMock.mockResolvedValue(jsonResponse({
      sign_in_required: true,
      message: 'Sign in to open your lesson notes, videos, and downloads.',
      sign_in_path: '/signin',
      lesson: { id: 1, title: 'Resistance in ohms', slug: 'ohms', course: { title: 'Resistors', slug: 'resistors' } },
    }, 401))
    const error = await getLesson('ohms').catch((reason: unknown) => reason)
    expect(isSignInRequired(error)).toBe(true)
    expect(signInRequiredPayload(error)?.lesson?.title).toBe('Resistance in ohms')
    expect((error as ApiError).message).toBe('Sign in to open your lesson notes, videos, and downloads.')
  })

  it('spots an email address that already has an account', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ message: 'Already registered.', account_exists: true }, 409))
    const error = await signUpAccount({
      email: 'ada@example.com', phone_number: '+2348031234567', password: 'resistor-code',
      confirm_password: 'resistor-code', remember: false,
    }, 'token-1').catch((reason: unknown) => reason)
    expect(isAccountTaken(error)).toBe(true)
  })

  it.each([
    [null],
    [{ errors: 'not an object' }],
    [{ errors: { email: 'a string' } }],
    [{ errors: { email: [1, null, 'kept'] } }],
    [undefined],
  ])('never crashes on an unexpected error payload: %s', async (payload) => {
    const error = payload === undefined ? new Error('network') : new ApiError('failed', 400, payload)
    expect(() => fieldErrors(error)).not.toThrow()
    expect(isSignInRequired(error)).toBe(false)
    expect(isAccountTaken(error)).toBe(false)
    expect(signInRequiredPayload(error)).toBeNull()
  })

  it('normalizes a single string error into a list of messages', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ errors: { email: 'Enter a valid email address.' } }, 400))
    const error = await signInAccount({ email: 'ada@', password: 'x', remember: false }, 'token-1')
      .catch((reason: unknown) => reason)
    expect(fieldErrors(error)).toEqual({ email: ['Enter a valid email address.'] })
  })
})

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getCourse, getCourses, getLesson, getSiteProfile } from './api'

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

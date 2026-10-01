import { useEffect, useState, type FormEvent } from 'react'
import { ArrowLeft, ArrowRight, Search, SlidersHorizontal } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { getCourses, isSignInRequired, signInRequiredPayload, type CatalogResponse, type SignInRequiredPayload } from '../api'
import { CourseCard } from '../components/CourseCard'
import { EmptyCourses, ErrorState, LoadingState, SignInNotice } from '../components/States'

type CatalogState = { key: string; data?: CatalogResponse; error?: string; signIn?: SignInRequiredPayload }

export function CoursesPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filterKey = searchParams.toString()
  const query = searchParams.get('q') || ''
  const level = searchParams.get('level') || ''
  const [catalogState, setCatalogState] = useState<CatalogState>({ key: '__not-loaded__' })
  const isLoading = catalogState.key !== filterKey
  const catalog = isLoading ? undefined : catalogState.data
  const error = isLoading ? '' : catalogState.error || ''
  const signIn = isLoading ? undefined : catalogState.signIn

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    getCourses(new URLSearchParams(filterKey), { signal: controller.signal })
      .then((data) => { if (active) setCatalogState({ key: filterKey, data }) })
      .catch((reason: Error) => {
        if (!active) return
        if (isSignInRequired(reason)) setCatalogState({ key: filterKey, signIn: signInRequiredPayload(reason) ?? undefined })
        else setCatalogState({ key: filterKey, error: reason.message })
      })
    return () => { active = false; controller.abort() }
  }, [filterKey])

  function submitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const next = new URLSearchParams()
    const nextQuery = String(form.get('q') || '').trim()
    const nextLevel = String(form.get('level') || '')
    if (nextQuery) next.set('q', nextQuery)
    if (nextLevel) next.set('level', nextLevel)
    setSearchParams(next)
  }

  function changePage(nextPage: number) {
    const next = new URLSearchParams(searchParams)
    if (nextPage > 1) next.set('page', String(nextPage))
    else next.delete('page')
    setSearchParams(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <>
      <section className="page-hero section-shell">
        <div className="breadcrumb"><span>LEARNING LIBRARY</span><span className="breadcrumb-slash">/</span><span>COURSES</span></div>
        <div className="page-hero-content">
          <div><p className="eyebrow">THE COMPONENT INDEX</p><h1>Courses for<br /><em>curious minds.</em></h1></div>
          <p className="page-hero-note">Browse practical lessons on electronic components. Each course brings notes, videos, and reference files together by topic.</p>
        </div>
        <div className="page-hero-rule"><span>01 — 03</span><span>FIND YOUR NEXT SUBJECT</span></div>
      </section>

      <section className="catalog-page section-shell">
        <form className="filter-bar" key={filterKey} onSubmit={submitFilters}>
          <label className="search-field">
            <span className="visually-hidden">Search courses</span>
            <Search size={18} aria-hidden="true" />
            <input type="search" name="q" autoComplete="off" placeholder="Search components or topics…" defaultValue={query} />
          </label>
          <label className="level-field">
            <span className="visually-hidden">Filter by level</span>
            <SlidersHorizontal size={16} aria-hidden="true" />
            <select name="level" defaultValue={level}>
              <option value="">All levels</option>
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </label>
          <button className="button button-primary filter-submit" type="submit">Find courses <ArrowRight size={16} aria-hidden="true" /></button>
        </form>

        <div className="results-bar" aria-live="polite">
          <span>{isLoading ? 'Loading courses…' : catalog ? `${catalog.count} ${catalog.count === 1 ? 'course' : 'courses'}` : 'Course library'}</span>
          <span>BEGINNER TO ADVANCED</span>
        </div>

        {signIn ? <SignInNotice message={signIn.message} next="/courses" /> : error ? <ErrorState message={error} /> : isLoading ? <LoadingState label="Finding courses…" /> : catalog?.count ? (
          <>
            <div className="course-grid">
              {catalog.results.map((course, index) => <CourseCard key={course.id} course={course} index={index} />)}
            </div>
            {catalog.pages > 1 && <nav className="pagination" aria-label="Course pages">
              <button className="button button-outline" type="button" disabled={!catalog.has_previous} onClick={() => changePage(catalog.page - 1)}><ArrowLeft size={15} aria-hidden="true" /> Previous</button>
              <span>Page {catalog.page} of {catalog.pages}</span>
              <button className="button button-outline" type="button" disabled={!catalog.has_next} onClick={() => changePage(catalog.page + 1)}>Next <ArrowRight size={15} aria-hidden="true" /></button>
            </nav>}
          </>
        ) : <EmptyCourses filtered={Boolean(query || level)} />}
      </section>
    </>
  )
}

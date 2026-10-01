import { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, Clock3, LockKeyhole } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, getCourse, type CourseDetail } from '../api'
import { ErrorState, LoadingState, LockedNotice } from '../components/States'

type CourseState = { slug: string; course?: CourseDetail; error?: string }

export function CoursePage() {
  const { slug = '' } = useParams()
  const [state, setState] = useState<CourseState>({ slug: '__not-loaded__' })
  const isLoading = state.slug !== slug
  const course = isLoading ? undefined : state.course
  const error = isLoading ? '' : state.error || ''

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    getCourse(slug, { signal: controller.signal })
      .then((data) => { if (active) setState({ slug, course: data }) })
      .catch((reason: Error) => {
        if (!active) return
        const message = reason instanceof ApiError && reason.status === 404
          ? 'We couldn’t find that course. It may have moved or is not published yet.'
          : reason.message
        setState({ slug, error: message })
      })
    return () => { active = false; controller.abort() }
  }, [slug])

  if (isLoading) return <section className="section-shell detail-shell"><LoadingState label="Opening course…" /></section>
  if (error || !course) return <section className="section-shell detail-shell"><ErrorState message={error || 'This course is unavailable.'} /><Link className="text-link back-link" to="/courses"><ArrowLeft size={15} aria-hidden="true" /> Back to courses</Link></section>

  const lessonCount = course.sections.reduce((total, section) => total + section.lessons.length, 0)

  return (
    <>
      <section className="course-detail-hero section-shell">
        <div className="breadcrumb"><Link to="/courses">COURSES</Link><span className="breadcrumb-slash">/</span><span>{course.title.toUpperCase()}</span></div>
        <div className="course-detail-grid">
          <div className="course-intro">
            <div className="eyebrow-row"><span className={`level-tag level-${course.level}`}>{course.level_label}</span><span className="eyebrow">COMPONENT COURSE</span></div>
            <h1>{course.title}<br /><em>from the inside out.</em></h1>
            <p className="course-lede">{course.summary || course.description || 'Explore the lessons and resources in this course.'}</p>
            <div className="course-meta">
              <span><span className="book-dot" aria-hidden="true">↳</span>{lessonCount} {lessonCount === 1 ? 'lesson' : 'lessons'}</span>
              {course.estimated_minutes > 0 && <span><Clock3 size={16} aria-hidden="true" />About {course.estimated_minutes} minutes</span>}
            </div>
          </div>
          <div className="course-aside">
            <span className="aside-kicker">IN THIS COURSE</span>
            <span className="aside-big-number">{String(lessonCount).padStart(2, '0')}</span>
            <span className="aside-caption">LESSONS TO EXPLORE</span>
            <div className="aside-rule" />
            <p>Notes, demonstrations, and downloadable references are grouped with each lesson.</p>
          </div>
        </div>
      </section>

      <section className="course-content section-shell">
        {course.is_locked && <LockedNotice message={course.lock_notice} />}
        <div className="course-content-heading">
          <div><p className="eyebrow">COURSE OUTLINE</p><h2>What you’ll study</h2></div>
          <Link to="/courses" className="text-link"><ArrowLeft size={15} aria-hidden="true" /> All courses</Link>
        </div>
        {!course.sections.length ? <div className="empty-outline"><p>Lessons for this course are being prepared.</p></div> : (
          <div className="section-list">
            {course.sections.map((section, sectionIndex) => (
              <section className="syllabus-section" key={section.id}>
                <div className="syllabus-heading">
                  <span className="syllabus-index">SECTION {String(sectionIndex + 1).padStart(2, '0')}</span>
                  <div><h3>{section.title}</h3>{section.description && <p>{section.description}</p>}</div>
                  {section.is_locked && <span className="lock-chip"><LockKeyhole size={13} aria-hidden="true" /> Locked</span>}
                </div>
                {section.lessons.length > 0 && <div className="lesson-list">
                  {section.lessons.map((lesson, lessonIndex) => (
                    <Link className={`lesson-row${lesson.is_locked ? ' is-locked' : ''}`} to={`/lessons/${lesson.slug}`} key={lesson.id}>
                      <span className="lesson-order">{String(lessonIndex + 1).padStart(2, '0')}</span>
                      <span className="lesson-row-main"><strong>{lesson.title}</strong><span>{lesson.summary || (lesson.is_locked ? lesson.lock_notice : 'Notes, video, and lesson materials')}</span></span>
                      {lesson.estimated_minutes > 0 && <span className="lesson-duration">{lesson.estimated_minutes} min</span>}
                      {lesson.is_locked ? <LockKeyhole className="lesson-trailing" size={16} aria-hidden="true" /> : <ArrowRight className="lesson-trailing" size={16} aria-hidden="true" />}
                    </Link>
                  ))}
                </div>}
              </section>
            ))}
          </div>
        )}
      </section>
    </>
  )
}

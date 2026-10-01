import { useEffect, useState } from 'react'
import { AlertCircle, ArrowLeft, ArrowUpRight, Download, ExternalLink, FileText, LockKeyhole, Play } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, getLesson, isSignInRequired, signInRequiredPayload, type LessonDetail, type SignInRequiredPayload } from '../api'
import { ErrorState, LoadingState, LockedNotice, SignInNotice } from '../components/States'

type LessonState = {
  slug: string
  lesson?: LessonDetail
  error?: string
  lockedMessage?: string
  signIn?: SignInRequiredPayload
}

export function LessonPage() {
  const { slug = '' } = useParams()
  const [state, setState] = useState<LessonState>({ slug: '__not-loaded__' })
  const isLoading = state.slug !== slug
  const lesson = isLoading ? undefined : state.lesson
  const error = isLoading ? '' : state.error || ''
  const lockedMessage = isLoading ? '' : state.lockedMessage || ''
  const signIn = isLoading ? undefined : state.signIn

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    getLesson(slug, { signal: controller.signal })
      .then((data) => { if (active) setState({ slug, lesson: data }) })
      .catch((reason: Error) => {
        if (!active) return
        if (reason instanceof ApiError && reason.status === 403) setState({ slug, lockedMessage: reason.message })
        else if (isSignInRequired(reason)) setState({ slug, signIn: signInRequiredPayload(reason) ?? undefined })
        else {
          const message = reason instanceof ApiError && reason.status === 404
            ? 'We couldn’t find that lesson. It may be unpublished or unavailable.'
            : reason.message
          setState({ slug, error: message })
        }
      })
    return () => { active = false; controller.abort() }
  }, [slug])

  if (isLoading) return <section className="section-shell detail-shell"><LoadingState label="Opening lesson…" /></section>
  if (lockedMessage) return <section className="section-shell detail-shell locked-page">
    <div className="breadcrumb"><Link to="/courses">COURSES</Link><span className="breadcrumb-slash">/</span><span>LESSON</span></div>
    <LockedNotice message={lockedMessage} />
    <Link className="text-link back-link" to="/courses"><ArrowLeft size={15} aria-hidden="true" /> Return to the course library</Link>
  </section>
  if (signIn) return <section className="section-shell detail-shell locked-page">
    <div className="breadcrumb">
      {signIn.lesson && <><Link to={`/courses/${signIn.lesson.course.slug}`}>{signIn.lesson.course.title.toUpperCase()}</Link><span className="breadcrumb-slash">/</span></>}
      <span>LESSON</span>
    </div>
    <SignInNotice message={signIn.message} next={`/lessons/${slug}`} lessonTitle={signIn.lesson?.title} />
    <Link className="text-link back-link" to="/courses"><ArrowLeft size={15} aria-hidden="true" /> Return to the course library</Link>
  </section>
  if (error || !lesson) return <section className="section-shell detail-shell"><ErrorState message={error || 'This lesson is unavailable.'} /><Link className="text-link back-link" to="/courses"><ArrowLeft size={15} aria-hidden="true" /> Back to courses</Link></section>

  return (
    <>
      <section className="lesson-page-head section-shell">
        <div className="breadcrumb"><Link to={`/courses/${lesson.course.slug}`}>{lesson.course.title.toUpperCase()}</Link><span className="breadcrumb-slash">/</span><span>{lesson.section.title.toUpperCase()}</span></div>
        <Link className="back-to-course" to={`/courses/${lesson.course.slug}`}><ArrowLeft size={14} aria-hidden="true" /> Course outline</Link>
        <p className="eyebrow">LESSON NOTES <span className="eyebrow-divider">/</span> {lesson.section.title}</p>
        <h1>{lesson.title}</h1>
        {lesson.summary && <p className="lesson-summary">{lesson.summary}</p>}
        {lesson.estimated_minutes > 0 && <span className="lesson-time">{lesson.estimated_minutes} minute lesson</span>}
      </section>

      <div className="lesson-layout section-shell">
        <main className="lesson-main">
          {lesson.safety_notice && <aside className="safety-note"><AlertCircle size={18} aria-hidden="true" /><div><strong>Safety note</strong><p>{lesson.safety_notice}</p></div></aside>}
          {lesson.videos.length > 0 && <section className="lesson-block video-block" id="watch">
            <div className="content-block-heading"><span className="content-step">01</span><div><p className="eyebrow">WATCH</p><h2>See it in action</h2></div></div>
            <div className="video-list">
              {lesson.videos.map((video) => (
                <article className="video-card" key={video.id}>
                  {video.embed_url ? <div className="video-frame"><iframe src={video.embed_url} title={video.title} loading="lazy" allow="accelerometer; encrypted-media; picture-in-picture; web-share" referrerPolicy="strict-origin-when-cross-origin" allowFullScreen /></div> : (
                    <div className={`video-fallback video-${video.platform}`}>
                      <span className="video-fallback-icon"><Play size={20} aria-hidden="true" /></span>
                      <span><small>{video.platform_label.toUpperCase()} VIDEO</small><strong>{video.title}</strong></span>
                      <a href={video.source_url} target="_blank" rel="noreferrer" className="button button-light">Watch on {video.platform_label} <ExternalLink size={14} aria-hidden="true" /></a>
                    </div>
                  )}
                  <div className="video-caption"><span>{video.title}</span><a href={video.source_url} target="_blank" rel="noreferrer">Open original <ArrowUpRight size={14} aria-hidden="true" /></a></div>
                </article>
              ))}
            </div>
          </section>}

          <section className="lesson-block notes-block" id="notes">
            <div className="content-block-heading"><span className="content-step">{lesson.videos.length ? '02' : '01'}</span><div><p className="eyebrow">READ</p><h2>Lesson notes</h2></div></div>
            {lesson.notes ? <div className="lesson-notes">{lesson.notes}</div> : <p className="content-placeholder">Written notes for this lesson will appear here.</p>}
          </section>

          {lesson.materials.length > 0 && <section className="lesson-block resources-block" id="materials">
            <div className="content-block-heading"><span className="content-step">{lesson.videos.length ? '03' : '02'}</span><div><p className="eyebrow">KEEP FOR REFERENCE</p><h2>Lesson materials</h2></div></div>
            <div className="material-list">
              {lesson.materials.map((material) => (
                <article className={`material-row${material.is_locked ? ' material-locked' : ''}`} key={material.id}>
                  <span className={`material-icon material-${material.kind}`}><FileText size={20} aria-hidden="true" /></span>
                  <span className="material-main"><strong>{material.title}</strong><span>{material.kind_label}{material.description ? ` · ${material.description}` : ''}</span></span>
                  {material.is_locked ? <span className="material-state"><LockKeyhole size={15} aria-hidden="true" /> Locked</span> : material.download_url && <a className="download-link" href={material.download_url}><Download size={16} aria-hidden="true" /><span>Download</span></a>}
                </article>
              ))}
            </div>
          </section>}
        </main>
        <aside className="lesson-sidebar">
          <div className="sidebar-card"><span className="sidebar-kicker">IN THIS LESSON</span>
            {lesson.videos.length > 0 && <a href="#watch"><Play size={15} aria-hidden="true" />Video demonstration{lesson.videos.length > 1 ? 's' : ''}</a>}
            <a href="#notes"><span className="sidebar-index">01</span> Written notes</a>
            {lesson.materials.length > 0 && <a href="#materials"><span className="sidebar-index">02</span> Learning materials</a>}
          </div>
          <div className="sidebar-note"><span className="sidebar-kicker">COURSE</span><Link to={`/courses/${lesson.course.slug}`}>{lesson.course.title}<ArrowUpRight size={14} aria-hidden="true" /></Link></div>
        </aside>
      </div>
    </>
  )
}

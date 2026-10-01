import { useEffect, useState } from 'react'
import { ArrowDown, ArrowRight, ArrowUpRight, BookOpen, FileText, Play } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getCourses, type CatalogResponse } from '../api'
import { CircuitIllustration } from '../components/CircuitIllustration'
import { CourseCard } from '../components/CourseCard'
import { EmptyCourses, ErrorState, LoadingState } from '../components/States'

export function HomePage() {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    getCourses(new URLSearchParams({ page: '1' }))
      .then((data) => { if (active) setCatalog(data) })
      .catch((reason: Error) => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [])

  return (
    <>
      <section className="home-hero section-shell">
        <div className="hero-copy">
          <p className="eyebrow"><span className="eyebrow-mark" /> ELECTRONICS, MADE UNDERSTANDABLE</p>
          <h1>Know the part.<br /><em>Understand</em> the circuit.</h1>
          <p className="hero-lede">A practical learning space for students exploring the components that make electronic circuits work.</p>
          <div className="hero-actions">
            <Link className="button button-primary" to="/courses">Browse the courses <ArrowRight size={17} aria-hidden="true" /></Link>
            <a className="button button-quiet" href="#approach">How lessons work <ArrowDown size={15} aria-hidden="true" /></a>
          </div>
          <div className="hero-note"><span className="note-rule" />From first principles to the workbench</div>
        </div>
        <div className="hero-art-wrap">
          <CircuitIllustration />
          <div className="figure-caption"><span>COMPONENT STUDY</span><span>FIELD NOTE 001</span></div>
          <span className="hero-coordinate" aria-hidden="true">09° 54′ N<br />08° 54′ E</span>
        </div>
        <a className="hero-scroll" href="#approach"><span>SCROLL TO EXPLORE</span><ArrowDown size={14} aria-hidden="true" /></a>
      </section>

      <section className="approach-section section-shell" id="approach">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">A CLEARER WAY TO LEARN</p>
            <h2>Useful at the desk.<br /><em>Useful at the bench.</em></h2>
          </div>
          <p className="section-intro">Every component has a job. Lessons bring the written explanation, a demonstration, and the supporting files together in one place.</p>
        </div>
        <div className="approach-grid">
          <article className="approach-card">
            <span className="approach-number">01</span>
            <span className="approach-icon"><BookOpen size={20} aria-hidden="true" /></span>
            <h3>Start with the idea</h3>
            <p>Read clear notes about what a component does, how it is described, and where it belongs in a circuit.</p>
          </article>
          <article className="approach-card">
            <span className="approach-number">02</span>
            <span className="approach-icon"><Play size={19} aria-hidden="true" /></span>
            <h3>See it demonstrated</h3>
            <p>Watch lessons shared from ValourTech’s video channels, with the original post one tap away.</p>
          </article>
          <article className="approach-card">
            <span className="approach-number">03</span>
            <span className="approach-icon"><FileText size={19} aria-hidden="true" /></span>
            <h3>Keep the reference</h3>
            <p>Open a PDF or download a Word document attached to the lesson for later study.</p>
          </article>
        </div>
      </section>

      <section className="catalog-preview section-shell" id="courses">
        <div className="section-heading-row catalog-heading">
          <div>
            <p className="eyebrow">THE COURSE LIBRARY</p>
            <h2>Learn one component<br /><em>at a time.</em></h2>
          </div>
          <Link className="text-link heading-link" to="/courses">View all courses <ArrowUpRight size={16} aria-hidden="true" /></Link>
        </div>
        {error ? <ErrorState message={error} /> : !catalog ? <LoadingState label="Loading courses…" /> : catalog.count === 0 ? (
          <EmptyCourses />
        ) : (
          <div className="course-grid">
            {catalog.results.slice(0, 3).map((course, index) => <CourseCard key={course.id} course={course} index={index} />)}
          </div>
        )}
        {catalog && catalog.count > 3 && <div className="catalog-more"><Link className="button button-outline" to="/courses">See all {catalog.count} courses <ArrowRight size={16} aria-hidden="true" /></Link></div>}
      </section>

      <section className="closing-band section-shell">
        <div className="closing-index">VT / LEARNING</div>
        <div><p className="eyebrow">YOUR NEXT STEP</p><h2>Build understanding<br />one lesson at a time.</h2></div>
        <Link className="button button-light" to="/courses">Find a course <ArrowRight size={17} aria-hidden="true" /></Link>
      </section>
    </>
  )
}

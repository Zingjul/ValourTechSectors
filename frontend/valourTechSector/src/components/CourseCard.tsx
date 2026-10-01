import { ArrowUpRight, LockKeyhole } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Course } from '../api'

const visualClasses = ['course-visual-sand', 'course-visual-green', 'course-visual-clay']

export function CourseCard({ course, index = 0 }: { course: Course; index?: number }) {
  return (
    <article className="course-card">
      <Link className={`course-card-art ${visualClasses[index % visualClasses.length]}`} to={`/courses/${course.slug}`} aria-label={`View ${course.title} course`}>
        <span className="card-index">{String(index + 1).padStart(2, '0')}</span>
        <svg className="course-schematic" viewBox="0 0 180 64" aria-hidden="true">
          <path d="M8 32h42m80 0h42M50 32V10h80v22M50 32v22h80V32" fill="none" stroke="currentColor" strokeWidth="2" />
          <rect x="69" y="21" width="42" height="22" rx="2" fill="var(--paper-bright)" stroke="currentColor" strokeWidth="2" />
          <circle cx="50" cy="32" r="3" fill="var(--clay)" />
          <circle cx="130" cy="32" r="3" fill="var(--clay)" />
        </svg>
        {course.is_locked && <span className="card-lock"><LockKeyhole size={13} aria-hidden="true" /> Locked</span>}
      </Link>
      <div className="course-card-body">
        <div className="eyebrow-row">
          <span className={`level-tag level-${course.level}`}>{course.level_label}</span>
          {course.estimated_minutes > 0 && <span className="course-duration">{course.estimated_minutes} min</span>}
        </div>
        <h3><Link to={`/courses/${course.slug}`}>{course.title}</Link></h3>
        <p>{course.summary || 'Open the course to explore its lessons and learning materials.'}</p>
        <Link className="text-link" to={`/courses/${course.slug}`}>
          {course.is_locked ? 'View course' : 'Explore course'} <ArrowUpRight size={15} aria-hidden="true" />
        </Link>
      </div>
    </article>
  )
}

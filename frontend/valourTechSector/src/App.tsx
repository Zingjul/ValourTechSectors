import { lazy, useEffect } from 'react'
import { ArrowLeft } from 'lucide-react'
import { Link, Route, Routes, useLocation } from 'react-router-dom'
import { SiteLayout } from './components/SiteLayout'
const ContactPage = lazy(() => import('./pages/ContactPage').then((module) => ({ default: module.ContactPage })))
const CoursePage = lazy(() => import('./pages/CoursePage').then((module) => ({ default: module.CoursePage })))
const CoursesPage = lazy(() => import('./pages/CoursesPage').then((module) => ({ default: module.CoursesPage })))
const HomePage = lazy(() => import('./pages/HomePage').then((module) => ({ default: module.HomePage })))
const LessonPage = lazy(() => import('./pages/LessonPage').then((module) => ({ default: module.LessonPage })))

function RouteTitle() {
  const location = useLocation()
  useEffect(() => {
    const pageTitle = location.pathname === '/courses'
      ? 'Courses'
      : location.pathname === '/contact'
        ? 'Contact'
        : location.pathname.startsWith('/lessons/')
          ? 'Lesson'
          : location.pathname.startsWith('/courses/')
            ? 'Course'
            : ''
    document.title = pageTitle ? `${pageTitle} · ValourTech Sectors` : 'ValourTech Sectors · Learn electronics'
  }, [location.pathname])
  return null
}

function NotFoundPage() {
  return <section className="section-shell not-found"><p className="eyebrow">404 / PAGE NOT FOUND</p><h1>This page isn’t<br /><em>on the board.</em></h1><p>That address doesn’t lead to a published page.</p><Link className="button button-primary" to="/"><ArrowLeft size={16} aria-hidden="true" /> Back to the home page</Link></section>
}

function App() {
  return (
    <>
      <RouteTitle />
      <Routes>
        <Route element={<SiteLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/courses" element={<CoursesPage />} />
          <Route path="/courses/:slug" element={<CoursePage />} />
          <Route path="/lessons/:slug" element={<LessonPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </>
  )
}

export default App

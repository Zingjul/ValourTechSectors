import { lazy, useEffect } from 'react'
import { ArrowLeft } from 'lucide-react'
import { Link, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { SiteLayout } from './components/SiteLayout'
const ContactPage = lazy(() => import('./pages/ContactPage').then((module) => ({ default: module.ContactPage })))
const CoursePage = lazy(() => import('./pages/CoursePage').then((module) => ({ default: module.CoursePage })))
const CoursesPage = lazy(() => import('./pages/CoursesPage').then((module) => ({ default: module.CoursesPage })))
const HomePage = lazy(() => import('./pages/HomePage').then((module) => ({ default: module.HomePage })))
const LessonPage = lazy(() => import('./pages/LessonPage').then((module) => ({ default: module.LessonPage })))
const SignInPage = lazy(() => import('./pages/SignInPage').then((module) => ({ default: module.SignInPage })))
const SignUpPage = lazy(() => import('./pages/SignUpPage').then((module) => ({ default: module.SignUpPage })))

const ROUTE_TITLES: Record<string, string> = {
  '/courses': 'Courses',
  '/contact': 'Contact',
  '/signin': 'Sign in',
  '/signup': 'Create account',
}

function routeTitle(pathname: string) {
  if (ROUTE_TITLES[pathname]) return ROUTE_TITLES[pathname]
  if (pathname.startsWith('/lessons/')) return 'Lesson'
  if (pathname.startsWith('/courses/')) return 'Course'
  return ''
}

function RouteTitle() {
  const location = useLocation()
  useEffect(() => {
    const pageTitle = routeTitle(location.pathname)
    document.title = pageTitle ? `${pageTitle} · ValourTech Sectors` : 'ValourTech Sectors · Learn electronics'
  }, [location.pathname])
  return null
}

function NotFoundPage() {
  return <section className="section-shell not-found"><p className="eyebrow">404 / PAGE NOT FOUND</p><h1>This page isn’t<br /><em>on the board.</em></h1><p>That address doesn’t lead to a published page.</p><Link className="button button-primary" to="/"><ArrowLeft size={16} aria-hidden="true" /> Back to the home page</Link></section>
}

function App() {
  return (
    <AuthProvider>
      <RouteTitle />
      <Routes>
        <Route element={<SiteLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/courses" element={<CoursesPage />} />
          <Route path="/courses/:slug" element={<CoursePage />} />
          <Route path="/lessons/:slug" element={<LessonPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/signin" element={<SignInPage />} />
          <Route path="/signup" element={<SignUpPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}

export default App

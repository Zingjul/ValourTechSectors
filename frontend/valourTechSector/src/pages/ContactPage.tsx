import { useEffect, useState } from 'react'
import { ArrowUpRight, AtSign, MessageCircle, Phone } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getSiteProfile, type SiteProfile } from '../api'
import { ErrorState, LoadingState } from '../components/States'

export function ContactPage() {
  const [profile, setProfile] = useState<SiteProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    getSiteProfile({ signal: controller.signal })
      .then((data) => { if (active) setProfile(data) })
      .catch((reason: Error) => { if (active) setError(reason.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false; controller.abort() }
  }, [])

  return (
    <>
      <section className="page-hero contact-hero section-shell">
        <div className="breadcrumb"><Link to="/">HOME</Link><span className="breadcrumb-slash">/</span><span>CONTACT</span></div>
        <div className="page-hero-content">
          <div><p className="eyebrow">LET’S TALK ELECTRONICS</p><h1>Questions are<br /><em>part of learning.</em></h1></div>
          <p className="page-hero-note">Get in touch with the ValourTech team about course content, learning materials, or the next topic you’d like to study.</p>
        </div>
      </section>

      <section className="contact-content section-shell">
        <div className="contact-primary">
          <p className="eyebrow">CONTACT DETAILS</p>
          <h2>Reach the team.</h2>
          {loading ? <LoadingState label="Loading contact details…" /> : error ? <ErrorState message={error} /> : profile && (
            <div className="contact-methods">
              {profile.contact_email && <a className="contact-method" href={`mailto:${profile.contact_email}`}><span><AtSign size={19} aria-hidden="true" /></span><span><small>EMAIL</small><strong>{profile.contact_email}</strong></span><ArrowUpRight size={16} aria-hidden="true" /></a>}
              {profile.phone_number && <a className="contact-method" href={`tel:${profile.phone_number.replace(/[^+\d]/g, '')}`}><span><Phone size={19} aria-hidden="true" /></span><span><small>PHONE</small><strong>{profile.phone_number}</strong></span><ArrowUpRight size={16} aria-hidden="true" /></a>}
              {profile.whatsapp_url && <a className="contact-method" href={profile.whatsapp_url} target="_blank" rel="noreferrer"><span><MessageCircle size={19} aria-hidden="true" /></span><span><small>WHATSAPP</small><strong>Message ValourTech</strong></span><ArrowUpRight size={16} aria-hidden="true" /></a>}
              {!profile.contact_email && !profile.phone_number && !profile.whatsapp_url && <p className="contact-empty">The team’s direct contact details will be added here.</p>}
              {profile.contact_note && <p className="contact-note">{profile.contact_note}</p>}
            </div>
          )}
        </div>
        <aside className="contact-social-panel">
          <span className="sidebar-kicker">FIND US ONLINE</span>
          <h3>Follow the lessons<br />where they’re shared.</h3>
          {profile?.social_links.length ? <div className="social-list">{profile.social_links.map((link) => (
            <a href={link.url} key={link.id} target="_blank" rel="noreferrer"><span>{link.label}</span><small>{link.platform_label}</small><ArrowUpRight size={16} aria-hidden="true" /></a>
          ))}</div> : <p className="contact-empty">Social profiles will appear here when the team adds them.</p>}
        </aside>
      </section>
    </>
  )
}

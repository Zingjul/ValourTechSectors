# ValourTech Sectors — implementation plan

## Product decisions

- The learner-facing site is free. Learners create an account with an email address and a phone number, then sign in to open lesson content.
- The home page, course catalogue, course outlines, and contact details stay public; lesson notes, videos, and downloads need a signed-in learner. `LEARNER_CONTENT_ACCESS` can widen or narrow that line without a code change.
- Published courses and learning materials are open to signed-in learners by default.
- Staff can mark a course, lesson, or individual material as locked. Its listing and a lock notice remain visible, while its lesson content, video destinations, and file URLs are withheld.
- Staff manage content through a private Django admin, which also lists every learner who signed up (email, phone, when they joined, when they last signed in). No checkout, payment processing, or progress tracking in this release.
- Learner accounts live in their own table with their own authentication backend, so a learner can never reach the staff admin and the staff password policy stays stricter than the learner one.
- Videos stay on YouTube, TikTok, Instagram, or Facebook. Staff add the original URLs. YouTube, TikTok, and public Facebook videos use provider embeds; every video keeps a link to its source. Instagram uses a labelled source link until the site has the Meta embed integration needed for Instagram’s embed markup. If a provider blocks an embed, the source link remains available.
- PDF, DOC, and DOCX uploads use Supabase Storage. Postgres stores course data and file metadata, not the file bytes.
- Contact details and social links are editable and remain blank until the owner supplies the real information. No invented logo or profile links.

## Architecture

- React + TypeScript + Vite in `frontend/valourTechSector`.
- Django in `backend/valour_tech_sectors`; Django owns the public JSON API and protected staff admin.
- Supabase Postgres is configured through `DATABASE_URL`. Local development can use SQLite when that variable is absent.
- Supabase Storage is configured with server-only S3-compatible credentials. The course-material bucket should be private; Django returns short-lived signed file URLs only after checking publication and lock state.
- The browser never receives Postgres credentials or Supabase service/storage secrets. Frontend API calls use relative `/api/...` paths; Vite proxies these to Django in local development. Production should serve the React build and proxy `/api/`, `/admin/`, `/static/`, and protected file redirects through the same site origin.

## Course data model

`Course → Section → Lesson → (VideoLink, Material)`, plus `Learner` for accounts.

`Learner` stores a unique lowercased email address, a normalized phone number, a hashed password, sign-up and last sign-in timestamps, an active flag, and the failed sign-in counter that drives its lockout. It shares nothing with `auth.User`, which stays reserved for staff.

Courses have a level, summary, ordering, publication status, and lock state. Sections and lessons can also be unpublished or locked independently. Lessons hold written notes. Video links record the platform and canonical source URL. Materials hold an uploaded file plus title, type, ordering, and publication/lock state. Site profile and social-link records provide the contact page.

## Delivery phases

1. **Django foundation:** environment-based settings, Supabase-ready database/storage adapters, course/material models, staff admin workflow, public read API with access checks, and tests.
2. **React experience:** replace the Vite demo with the public landing page, course catalogue, course/lesson views, locked notices, contact page, and responsive navigation.
3. **Integration and launch checks:** connect frontend data to Django, test real Supabase credentials and uploads, verify video provider fallbacks, add real course/contact content, and review accessibility/security/deployment configuration.

## Initial API surface

- `GET /api/v1/courses/` — published course catalogue, optional search and level filter.
- `GET /api/v1/courses/<slug>/` — course overview and ordered outline; lesson content is withheld until sign-in.
- `GET /api/v1/lessons/<slug>/` — open lesson notes, videos, and materials; locked content returns a lock response, withheld content returns a sign-in response.
- `GET /api/v1/materials/<id>/download/` — checks publication, lock, and sign-in state before redirecting to the file.
- `GET /api/v1/site-profile/` — available contact and social details.
- `GET /api/v1/health/` — deployment health check.
- `POST /api/v1/auth/signup/` — email, phone number, and password; returns the signed-in session.
- `POST /api/v1/auth/signin/` — email and password; rotates the session key.
- `POST /api/v1/auth/signout/` — ends the session.
- `GET /api/v1/auth/session/` — who is signed in, what the account opens, and the CSRF token for the next POST.

## Out of scope for the first release

Course progress, payments, email campaigns, quizzes, certificates, custom logo design, video uploads, and guarantees that third-party videos embed on every device/account configuration. Self-service password reset, email verification, and a sign-up rate limit also wait on an email delivery provider or a CDN rule; until then staff reset a forgotten learner password from the admin and watch the learner list for junk records.

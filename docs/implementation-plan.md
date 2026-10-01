# ValourTech Sectors — implementation plan

## Product decisions

- The learner-facing site is free, and **registration is by invitation**: staff generate a single-use link in the admin and send it privately to whoever they are admitting. There is no public sign-up page. A link registers one person with an email address, a phone number, and a password of their own, then stops working; they sign in with that password from then on. `LEARNER_REGISTRATION=open` returns to public sign-up without a code change.
- The home page, course catalogue, course outlines, and contact details stay public; lesson notes, videos, and downloads need a signed-in learner. `LEARNER_CONTENT_ACCESS` can widen or narrow that line without a code change.
- Published courses and learning materials are open to signed-in learners by default.
- Staff can mark a course, lesson, or individual material as locked. Its listing and a lock notice remain visible, while its lesson content, video destinations, and file URLs are withheld.
- Staff manage content through a private Django admin, which also lists every learner who registered (email, phone, when they joined, when they last signed in, and which link admitted them) and every invitation link issued (note, expiry, state, who used it). No checkout, payment processing, or progress tracking in this release.
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

`Course → Section → Lesson → (VideoLink, Material)`, plus `Learner` for accounts and `RegistrationInvite` for the links that admit them.

`Learner` stores a unique lowercased email address, a normalized phone number, a hashed password, sign-up and last sign-in timestamps, an active flag, and the failed sign-in counter that drives its lockout. It shares nothing with `auth.User`, which stays reserved for staff.

`RegistrationInvite` stores a 256-bit random token, an optional private staff note, who generated it, when it expires, a revoke flag, and the one learner it admitted. Tokens are kept as generated so a link can be copied again while unused; the note never appears in an API response.

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
- `POST /api/v1/auth/signup/` — email, phone number, password, and a single-use `invite` token; spends the link and returns the signed-in session.
- `GET /api/v1/auth/invite/<token>/` — whether a link can still register someone, so the page explains a spent or expired link instead of showing a form that will be refused.
- `POST /api/v1/auth/signin/` — email and password; rotates the session key.
- `POST /api/v1/auth/signout/` — ends the session.
- `GET /api/v1/auth/session/` — who is signed in, what the account opens, and the CSRF token for the next POST.

## Out of scope for the first release

Course progress, payments, email campaigns, quizzes, certificates, custom logo design, video uploads, and guarantees that third-party videos embed on every device/account configuration. Self-service password reset and email verification wait on an email delivery provider; until then staff reset a forgotten learner password from the admin. Invitation links are copied and sent by hand for the same reason — sending them by email becomes a small addition once a provider exists. Junk sign-ups and sign-up abuse need no rate limit while registration is invitation-only.

# ValourTech Sectors — implementation plan

## Product decisions

- The learner-facing site is public and free for the first release; students do not create accounts.
- Published courses and learning materials are open by default.
- Staff can mark a course, lesson, or individual material as locked. Its listing and a lock notice remain visible, while its lesson content, video destinations, and file URLs are withheld.
- Staff manage content through a private Django admin. No student login, checkout, payment processing, or progress tracking in this release.
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

`Course → Section → Lesson → (VideoLink, Material)`

Courses have a level, summary, ordering, publication status, and lock state. Sections and lessons can also be unpublished or locked independently. Lessons hold written notes. Video links record the platform and canonical source URL. Materials hold an uploaded file plus title, type, ordering, and publication/lock state. Site profile and social-link records provide the contact page.

## Delivery phases

1. **Django foundation:** environment-based settings, Supabase-ready database/storage adapters, course/material models, staff admin workflow, public read API with access checks, and tests.
2. **React experience:** replace the Vite demo with the public landing page, course catalogue, course/lesson views, locked notices, contact page, and responsive navigation.
3. **Integration and launch checks:** connect frontend data to Django, test real Supabase credentials and uploads, verify video provider fallbacks, add real course/contact content, and review accessibility/security/deployment configuration.

## Initial API surface

- `GET /api/v1/courses/` — published course catalogue, optional search and level filter.
- `GET /api/v1/courses/<slug>/` — public course overview and ordered outline.
- `GET /api/v1/lessons/<slug>/` — open lesson notes, videos, and materials; locked content returns a lock response.
- `GET /api/v1/materials/<id>/download/` — checks all publication/lock states before redirecting to the file.
- `GET /api/v1/site-profile/` — available contact and social details.
- `GET /api/v1/health/` — deployment health check.

## Out of scope for the first release

Student accounts, course progress, payments, email campaigns, quizzes, certificates, custom logo design, video uploads, and guarantees that third-party videos embed on every device/account configuration.

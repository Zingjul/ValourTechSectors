# ValourTech Sectors

A learning site for electronic components. Learners create a free account with an email address and a phone number, then sign in to open lesson notes, videos, and downloads; staff manage course content and review sign-ups through Django admin.

## Project layout

- `frontend/valourTechSector` — React + TypeScript + Vite learner site.
- `backend/valour_tech_sectors` — Django application and API.
- `docs/implementation-plan.md` — agreed scope and architecture.

## Development and production

For local development, React/Vite proxies same-origin `/api`, `/admin`, `/static/admin`, and `/media` requests to Django. Django uses SQLite and local media only when developing; production explicitly requires PostgreSQL and private Supabase Storage. Storage/Postgres credentials stay server-side; the browser uses relative API paths and does not receive Supabase credentials.

**Production launch:** this repository includes a Render Blueprint (`render.yaml`), a multi-stage production Dockerfile, PostgreSQL/React CI checks, and secure-by-default production settings. Read [`docs/production-guide.md`](docs/production-guide.md) before provisioning Render/Supabase or adding live secrets. This checkout does not create cloud resources, set your secrets/domain, or publish course content on your behalf.

Local setup: [`backend/README.md`](backend/README.md) and [`frontend/valourTechSector/README.md`](frontend/valourTechSector/README.md).

## Learner accounts

Sign-up asks for an **email address**, a **phone number**, and a password the learner chooses, then signs them in immediately. Sign-in is email + password, with "keep me signed in" for a longer session. Learner records live in their own table, apart from the staff accounts that reach `/admin/`, and are listed in the admin under **Learners** (searchable by email or phone).

By default, lesson notes, videos, and file downloads need a signed-in learner, while the home page, course catalogue, course outlines, and contact details stay public so visitors can see what they are signing up for. `LEARNER_CONTENT_ACCESS` changes that without a code change: `open` keeps the whole site public (accounts are then only a record of who signed up), `lessons` is the default, and `everything` also closes the catalogue.

Learners cannot reset their own passwords yet, because the site has no email delivery configured. Until an email provider is added, staff set a new password from the learner's admin page and share it privately. Failed sign-ins are counted per email address and lock that address out for a while; no visitor IP address is stored.

## Scope for the first release

Free learner accounts, no payments or course progress tracking. Courses and materials are open to signed-in learners unless staff locks them. PDF/DOC/DOCX files are stored in Supabase Storage; social-video URLs remain on their source platforms.

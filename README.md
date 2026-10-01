# ValourTech Sectors

A public learning site for electronic components. Learners browse courses, notes, documents, and creator-hosted video lessons; staff manage course content through Django admin.

## Project layout

- `frontend/valourTechSector` — React + TypeScript + Vite learner site.
- `backend/valour_tech_sectors` — Django application and API.
- `docs/implementation-plan.md` — agreed scope and architecture.

## Development and production

For local development, React/Vite proxies same-origin `/api`, `/admin`, `/static/admin`, and `/media` requests to Django. Django uses SQLite and local media only when developing; production explicitly requires PostgreSQL and private Supabase Storage. Storage/Postgres credentials stay server-side; the browser uses relative API paths and does not receive Supabase credentials.

**Production launch:** this repository includes a Render Blueprint (`render.yaml`), a multi-stage production Dockerfile, PostgreSQL/React CI checks, and secure-by-default production settings. Read [`docs/production-guide.md`](docs/production-guide.md) before provisioning Render/Supabase or adding live secrets. This checkout does not create cloud resources, set your secrets/domain, or publish course content on your behalf.

Local setup: [`backend/README.md`](backend/README.md) and [`frontend/valourTechSector/README.md`](frontend/valourTechSector/README.md).

## Scope for the first release

Public site, no student accounts or payments. Courses and materials are open unless staff locks them. PDF/DOC/DOCX files are stored in Supabase Storage; social-video URLs remain on their source platforms.

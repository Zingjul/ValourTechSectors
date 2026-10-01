# ValourTech Sectors

A public learning site for electronic components. Learners browse courses, notes, documents, and creator-hosted video lessons; staff manage course content through Django admin.

## Project layout

- `frontend/valourTechSector` — React + TypeScript + Vite learner site.
- `backend/valour_tech_sectors` — Django application and API.
- `docs/implementation-plan.md` — agreed scope and architecture.

## Current development setup

The React app is configured with Vite. Django uses SQLite locally unless `DATABASE_URL` points to Supabase Postgres. Supabase Storage credentials are server-side only. See `.env.example` and the backend setup notes in `backend/README.md`. In production, serve React and proxy the API/admin routes through the same origin so the browser can use relative API paths.

## Scope for the first release

Public site, no student accounts or payments. Courses and materials are open unless staff locks them. PDF/DOC/DOCX files are stored in Supabase Storage; social-video URLs remain on their source platforms.

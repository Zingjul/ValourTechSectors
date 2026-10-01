# Django backend

## Local setup

From the repository root:

```bash
python -m venv backend/.venv
source backend/.venv/bin/activate  # Windows: backend\\.venv\\Scripts\\activate
pip install -r backend/requirements.txt
cp .env.example .env
python backend/valour_tech_sectors/manage.py migrate
python backend/valour_tech_sectors/manage.py createsuperuser
python backend/valour_tech_sectors/manage.py runserver 0.0.0.0:8000
```

The app defaults to local SQLite and local media storage. To connect Supabase, put the project Postgres connection string in `DATABASE_URL`. For uploads, set the S3-compatible Storage credentials in `.env` and create a **private** bucket matching `SUPABASE_STORAGE_BUCKET`. Never commit `.env` or expose these credentials in React/Vite variables.

Staff content management: `/admin/`. Public API: `/api/v1/`; process liveness: `/api/v1/health/`; database/build readiness: `/api/v1/ready/`.

For production, use PostgreSQL plus a private Supabase Storage bucket. Production settings default to `DJANGO_DEBUG=false` and fail closed if a strong secret, exact hosts/origins, Postgres URL, and complete storage credentials are missing. Local SQLite and media are development only. See [`docs/production-guide.md`](../docs/production-guide.md) for the Render Blueprint, S3 verification command, admin lockout recovery, security checks, backups, and launch checklist.

Before using the Django admin in production, create an administrator through a trusted interactive shell (`python backend/valour_tech_sectors/manage.py createsuperuser`). The production password validator requires at least 12 characters; failed admin logins are rate-limited. Uploaded course documents are format-checked but are **not** malware-scanned: only trusted staff should be allowed to upload.

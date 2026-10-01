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

Staff content management: `/admin/`. Public API: `/api/v1/`.

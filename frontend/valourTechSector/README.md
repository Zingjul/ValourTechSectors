# ValourTech Sectors · Frontend

React + TypeScript + Vite learner site.

From the repository root:

```bash
npm --prefix frontend/valourTechSector install
npm --prefix frontend/valourTechSector run dev -- --host 0.0.0.0
```

The Vite server proxies `/api`, `/admin`, `/static`, and `/media` to Django. Run the Django app at `http://127.0.0.1:8000`, or set `DJANGO_PROXY_TARGET` to another backend origin. Browser code uses relative API paths and does not need Supabase credentials.

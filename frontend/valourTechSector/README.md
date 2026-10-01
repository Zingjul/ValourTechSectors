# ValourTech Sectors · Frontend

React + TypeScript + Vite learner site.

From the repository root:

```bash
npm --prefix frontend/valourTechSector install
npm --prefix frontend/valourTechSector run dev -- --host 0.0.0.0
```

The Vite server proxies `/api`, `/admin`, `/static`, and `/media` to Django. Run the Django app at `http://127.0.0.1:8000`, or set `DJANGO_PROXY_TARGET` to another backend origin. Browser code uses relative API paths and does not need Supabase credentials.

Learner accounts live in `src/auth`: `AuthProvider` asks `GET /api/v1/auth/session/` once on load and keeps the learner and the CSRF token in memory (never in `localStorage`), and `useAuth()` exposes `signIn`, `signUp`, and `signOut` to the header and the `/signin` and `/signup` pages. Content the API withholds comes back as a `401` with `sign_in_required`, which `SignInNotice` turns into a prompt that keeps the learner's destination in a `next` parameter. Only a relative path on this origin is accepted for `next` (see `safeNextPath`).

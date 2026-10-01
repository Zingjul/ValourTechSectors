# ValourTech Sectors · Frontend

React + TypeScript + Vite learner site.

From the repository root:

```bash
npm --prefix frontend/valourTechSector install
npm --prefix frontend/valourTechSector run dev -- --host 0.0.0.0
```

The Vite server proxies `/api`, `/admin`, `/static`, and `/media` to Django. Run the Django app at `http://127.0.0.1:8000`, or set `DJANGO_PROXY_TARGET` to another backend origin. Browser code uses relative API paths and does not need Supabase credentials.

Learner accounts live in `src/auth`: `AuthProvider` asks `GET /api/v1/auth/session/` once on load and keeps the learner, the CSRF token, and the registration mode in memory (never in `localStorage`), and `useAuth()` exposes `signIn`, `signUp`, and `signOut` to the header and the `/signin` and `/signup` pages.

Registration is by invitation, so `/signup` is linked from nowhere: it reads an `?invite=` token, asks `GET /api/v1/auth/invite/<token>/` about it, and shows the form only when the link can still register someone — otherwise it explains that access is by invitation, or that the link was used, expired, or withdrawn. Content the API withholds comes back as a `401` with `sign_in_required`, which `SignInNotice` turns into a prompt that keeps the learner's destination in a `next` parameter and points at requesting access. Only a relative path on this origin is accepted for `next` (see `safeNextPath`).

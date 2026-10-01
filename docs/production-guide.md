# Production launch guide (Render + Supabase)

The code in this repository is prepared for **one Render web service** running Django and the built React site, with **Supabase Postgres** and **private Supabase Storage**. Browsers use relative `/api/...` paths, so the public site and API share one origin; you do not need CORS configuration or a Supabase key in the frontend.

The first production database is intentionally **empty**. There is no automatic sample content or account import.

> **This is an operator guide, not a completed cloud launch.** You must connect your Render/GitHub/Supabase accounts, add secrets and a domain, verify real database/storage access, create the staff account, and publish your actual courses before inviting learners. Never paste credentials into chat, GitHub issues, commits, build arguments, or `VITE_*` variables.

## 1. Choose the production domain and services

1. Decide your canonical public domain (for example, `learn.example.com`) and whether you will use a second hostname such as `www.learn.example.com`. Every public HTTPS hostname must be added to Django's exact host/origin allowlists.
2. This repository's `render.yaml` selects the **Frankfurt** Render region and a paid, always-on-sized web service plan. Create Supabase in the closest practical region too (Frankfurt is a sensible starting point for Lagos), then keep the application, database, and object storage in the same region when possible. The service region cannot be changed in-place later; if you pick another Supabase region, edit `region:` in `render.yaml` **before** provisioning.
3. Use a paid production plan and set a budget/spend alert. Render's free web instances can sleep and have ephemeral local files; free Render Postgres expires, and Supabase says free projects can pause for inactivity and do not include downloadable database backups. This site requires an external durable Postgres and private object storage. [Render service limitations](https://render.com/docs/free) · [Supabase production checklist](https://supabase.com/docs/guides/deployment/going-into-prod) · [Supabase backups](https://supabase.com/docs/guides/platform/backups).
4. Before launch, choose a suitable privacy/contact notice, the real support email, approved learning content, and who is permitted to access the staff admin.

## 2. Create the Supabase project, database, and private bucket

### Postgres

1. Create a **new production Supabase project**. Store its database password in your password manager. Enable SSL enforcement in the project database settings.
2. Open **Connect** in the Supabase project and copy the **Session pooler** connection string (port `5432`). Render's IPv4 egress can use this mode; use the URI supplied for your project rather than constructing a pooler hostname. Keep its password URL-encoded if it contains characters such as `@`, `:`, `/`, `#`, `?`, or `%`. Leave `sslmode=require` on the URI.
3. The private value for Render is named `DATABASE_URL`. Use the Supabase **database password**, not a Supabase browser/anon key. Do not put the connection URI in source control. Supabase explains how to select a connection method and retrieve its exact string in [Connect to Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres).
4. Django's first deploy applies the committed migrations, including row-level security (RLS) on the Django/admin tables and on the learner and invitation-link tables in the exposed `public` schema. Django connects as the database owner; browser-facing Supabase `anon`/`authenticated` Data API roles receive no table policies. **Do not add an unrestricted Supabase RLS policy** to these tables. Use the Django API/admin as the application access path and review the Supabase Security Advisor after deployment.

### File storage

1. In Supabase **Storage**, create a bucket named `course-materials` and mark it **private** (not public). Set the bucket's maximum file size to 25 MB. The Django upload form only accepts PDF, DOC, and non-macro DOCX files; a file signature/structure check supplements the extension/size checks. It is not a malware scanner.
2. Enable the S3 protocol if the project's Storage settings require it. In **Storage → S3 configuration**, generate an S3 **Access Key ID + Secret Access Key**, and copy the endpoint/project URL **and region shown in that screen**. Set the S3 region to the value provided by Supabase for this project; do not guess it based on the Render region. See [Supabase S3 authentication](https://supabase.com/docs/guides/storage/s3/authentication) and [S3 compatibility](https://supabase.com/docs/guides/storage/s3/compatibility).
3. Supabase S3 keys are powerful **server-side credentials** (they can access buckets and bypass Storage RLS). Use these keys only in Render's protected service environment. Never use an anon key, service-role key, or S3 secret in the browser. Rotate S3 credentials immediately if they are exposed.
4. Record the origin-only HTTPS project URL, bucket name, access key, secret, and S3 region in your password manager. The Render variables are `SUPABASE_URL`, `SUPABASE_STORAGE_BUCKET`, `SUPABASE_S3_ACCESS_KEY_ID`, `SUPABASE_S3_SECRET_ACCESS_KEY`, and `SUPABASE_S3_REGION`.
5. Supabase's S3 adapter does not turn a public bucket private. Signed downloads are generated only after Django verifies publication and lock state; their default lifetime is five minutes. Private buckets are served only with a time-limited signed URL. [Supabase private-file downloads](https://supabase.com/docs/guides/storage/serving/downloads).

## 3. Run the checks, then merge to the deploy branch

From the repository root, with Node.js 22 and Python 3.12 available:

```bash
npm --prefix frontend/valourTechSector ci
npm --prefix frontend/valourTechSector run check
npm --prefix frontend/valourTechSector audit

python -m venv backend/.venv
# macOS/Linux:
source backend/.venv/bin/activate
# Windows PowerShell: backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
```

Backend tests use PostgreSQL in GitHub Actions. For a safe local SQLite-only run, explicitly prevent `.env` from supplying any production URL or storage key:

```bash
DJANGO_DEBUG=true DATABASE_URL='' \
SUPABASE_URL='' SUPABASE_STORAGE_BUCKET='' \
SUPABASE_S3_ACCESS_KEY_ID='' SUPABASE_S3_SECRET_ACCESS_KEY='' \
python backend/valour_tech_sectors/manage.py test valour --verbosity 2
```

PowerShell alternative: set the same six environment variables with `$env:...` before running `python`. Never point a test run at your live Supabase database. Check Django's migration state too:

```bash
DJANGO_DEBUG=true DATABASE_URL='' python backend/valour_tech_sectors/manage.py makemigrations --check --dry-run
```

The GitHub Actions workflows run backend/Postgres tests, frontend tests/lint/build, dependency audits, production settings validation, and a built-container smoke test. Connect GitHub to Render and deploy the branch that contains these changes (normally merge the reviewed pull request into `main`). `autoDeployTrigger: checksPass` is deliberate: a failed or missing CI check should stop an automatic production deploy.

## 4. Provision the Render service from the Blueprint

1. Push/merge the reviewed changes to the branch Render should deploy. In Render, choose **New → Blueprint**, connect this repository, select that production branch, and sync the root `render.yaml`.
2. Review the service name, Frankfurt region, **paid** service plan, Dockerfile path, and `healthCheckPath: /api/v1/ready/`. Pre-deploy database migrations require a paid Render web service; this Blueprint does not create a second database or a persistent local-media disk.
3. In the Render service's **Environment** page, fill every `sync: false` prompt securely. Generate a new Django secret locally:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

   Use the resulting value for `DJANGO_SECRET_KEY`. Do not reuse the development key or any project's password.
4. Add the Supabase values from step 2. `DATABASE_URL` must be the project’s Session pooler URI; storage values must be from that same Supabase project. Keep `DJANGO_DEBUG=false`, `DJANGO_SECURE_SSL_REDIRECT=true`, and leave private signed URLs short-lived.
5. Review the learner account settings. `LEARNER_REGISTRATION=invite` (the Blueprint default) means nobody can register on their own: `/signup` is linked from nowhere and only accepts a single-use link generated in `/admin/`. Set it to `open` if you ever want public sign-up back. `LEARNER_CONTENT_ACCESS=lessons` keeps the home page, catalogue, course outlines, and contact details public, and asks for a sign-in before lesson notes, videos, and downloads; `open` keeps the whole site public while accounts are only a record of who joined, and `everything` also closes the catalogue. `LEARNER_INVITE_VALID_DAYS` (14; `0` means links never expire on their own), `LEARNER_PASSWORD_MIN_LENGTH`, `LEARNER_LOGIN_FAILURE_LIMIT`, `LEARNER_LOGIN_LOCKOUT_MINUTES`, and `LEARNER_SESSION_REMEMBER_DAYS` are safe to leave as they are. Changing any of them needs a redeploy, not a code change.
6. For a custom domain, set `DJANGO_ALLOWED_HOSTS` to the exact hostname(s), comma-separated, with **no scheme, wildcard, or port**. Set `DJANGO_CSRF_TRUSTED_ORIGINS` to the matching exact HTTPS origins, comma-separated (for example, `https://learn.example.com,https://www.learn.example.com`). The Render-generated `your-service.onrender.com` hostname is allowed automatically; a custom hostname is not. If you use only the Render-generated domain initially, you can leave both custom-domain variables unset.
7. Trigger **Save, rebuild, and deploy** after saving required secrets. The sequence is build image → run Django deployment checks → apply Postgres migrations → upload/read/delete a storage probe and verify the bucket is private → start Gunicorn → pass the schema-aware readiness check. The image's entrypoint also runs deployment checks and `prepare_database` **before** starting Gunicorn, so migrations cannot be skipped by a manually created service without the Blueprint's pre-deploy hook. `prepare_database` applies only committed migrations, verifies managed tables/columns without reading any rows, and uses a PostgreSQL session advisory lock to serialize pre-deploy/startup migrations (waits up to 60 seconds for another deploy). Repeated starts are safe; migration or schema-check failures prevent web startup, and `DJANGO_DEBUG=true` is rejected. Keep using the Supabase **Session** pooler, not transaction pooling, so the lock stays on the same connection. The paid pre-deploy hook remains recommended: it catches failures before replacing the running service and also verifies private storage. Render runs it separately and documents that feature as paid-service-only. [Render Blueprints](https://render.com/docs/blueprint-spec) · [pre-deploy commands](https://render.com/docs/deploys#pre-deploy-command).
8. Wait for a successful deployment and a passing Render health check. If configuration is rejected, inspect the deploy logs **without copying secret values** into a ticket or screenshot.

## 5. Create the staff login and verify storage on the deployed service

Use the Render service's interactive **Shell** (available on paid services) after the first migration/deploy:

```bash
python backend/valour_tech_sectors/manage.py createsuperuser
python backend/valour_tech_sectors/manage.py verify_storage
```

The storage check makes a uniquely named temporary PDF, confirms that upload and signed download work, checks that the corresponding public URL cannot read the object, then deletes the probe. If it fails, verify the bucket is private and the endpoint, S3 region, credentials, and project URL all belong to the same project. If the command warns that it could not delete the probe, remove that temporary object manually and correct S3 delete permissions.

If an administrator is locked out after repeated failures, enter the **exact Django username** in Render's Shell:

```bash
python backend/valour_tech_sectors/manage.py axes_reset_username your_admin_username
```

To reset an administrator password from the interactive shell:

```bash
python backend/valour_tech_sectors/manage.py changepassword your_admin_username
```

Use unique staff accounts and long unique passwords; password rules require at least 12 characters. Open `https://YOUR-RENDER-HOST/admin/`, sign in, then enter the same HTTPS host in a second tab to confirm secure staff cookies, admin static files, and logout/login behavior.

### Handing out access

Learners cannot register by themselves. In `/admin/` → **Registration invites**, choose **Generate invitation link**: the link appears at the top of the page ready to copy, with shortcuts to open it in email or share it on WhatsApp.

1. Check the host in that link is your real domain. Django builds it from the request it received, so a wrong hostname here means `DJANGO_ALLOWED_HOSTS` or the proxy's forwarded headers need attention — fix that before sending links out.
2. Add a private note (for example, "Ada — WhatsApp, October cohort"). Notes stay in the admin and never appear on the site or in an API response.
3. Send the link privately. Each one registers a single person and then shows as **Used** with that learner's email; a forwarded link cannot admit anyone else.
4. Use **Revoke selected unused links** when a link should stop working, and **Give selected unused links the full validity again** when one has expired before the person used it. Never turn off CSRF to fix a login error; verify HTTPS, the exact allowed host/origin, and Render's `X-Forwarded-Proto` first.

## 6. Attach the real domain and make it public

1. In Render **Settings → Custom Domains**, add your chosen hostname. Follow Render's exact DNS instructions at your domain registrar and verify the domain. Render provisions TLS for configured domains and redirects HTTP to HTTPS. Do not remove/change existing records blindly; use Render's current instructions for your DNS provider. [Render custom domains](https://render.com/docs/custom-domains).
2. Save the exact custom hostname(s) in `DJANGO_ALLOWED_HOSTS` and corresponding `https://...` origins in `DJANGO_CSRF_TRUSTED_ORIGINS`; redeploy and verify `/admin/` login and `/api/v1/ready/` on the custom hostname.
3. Test the learner website with direct loads and refreshes of `/`, `/courses`, a course URL, a lesson URL, and `/contact`. Confirm the browser Network panel only calls same-origin `/api/v1/...` for app data. Expected checks:

   - `https://YOUR-HOST/api/v1/health/` returns `{"status":"ok"}` (process liveness).
   - `https://YOUR-HOST/api/v1/ready/` returns `{"status":"ok"}` only while Postgres and the production build are available.
   - A made-up `/api/v1/...` path returns JSON `404`, not the React HTML page.
   - Unknown learner URLs return a real HTTP `404` with a helpful page.
   - A locked/unpublished lesson or file cannot disclose lesson text, links, or a signed URL.
   - `/signup` on its own explains that registration is by invitation and shows no form. The header and footer offer sign-in and a way to request access, not a sign-up link.
   - Generating a link in the admin and opening it registers that person: the header shows their email, the lesson opens, and a download works. After signing out, the same lesson shows a sign-in prompt and its Network response contains no lesson text.
   - Re-opening the same link says it has already been used, and the admin lists it as **Used** against that learner.
   - Signing back in with that password works, a wrong password is refused, and repeated failures eventually lock only that one email address.
   - Clicking a download link after the session ends lands on the sign-in page and returns to the lesson afterwards.
   - After enabling storage in the admin, an open sample file redirects to a short-lived signed URL. An unlisted private-bucket URL fails without a signature.
   - HTTPS admin login works; HTTP is redirected to HTTPS; no mixed-content, CSRF, JavaScript console, or missing static chunk errors appear.
4. Check the one-hour HSTS default after HTTPS is stable. Then consider setting `DJANGO_SECURE_HSTS_SECONDS=31536000` (one year). Only set `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=true` if **every** affected subdomain supports HTTPS. Leave preload false unless you deliberately enroll the whole domain in browser preload lists; HSTS can make a misconfigured domain inaccessible for its max-age.
5. In Supabase, review **Database → Advisors → Security Advisor** and SSL enforcement. Use IP/network restrictions only if your Render egress networking supports stable addresses and you have tested that they do not block Render. Protect your provider accounts with MFA.

## 7. Add the real courses before sharing the link

1. Create the real course catalog, sections, lessons, safety notices, video links, and contact/profile data in `/admin/`. There is no dummy seed data. Registrations appear under **Learners** (with the link that admitted each one), which is also where a forgotten learner password is reset, because no email provider is configured yet.
2. Leave courses/sections/lessons unpublished until the copy and links have been reviewed. Preview draft content in the admin, publish the course, then validate it on the public site.
3. Upload an intentionally harmless sample PDF and DOCX in a draft lesson. Test validation, downloads, filename, and signed link expiry. Do not upload confidential or copyrighted material without authorization.
4. Review every course/section/lesson/material publication and lock flag. Remember that a 403 lock notice is visible to learners; lock state hides private content and the file signer rejects access at every ancestor level.
5. Add the actual support email, phone/WhatsApp, social links, privacy/contact information, and any required legal disclosures. Leave details blank until verified; this app intentionally invents none.
6. Have another staff member test mobile layout, keyboard navigation, zoom, navigation, course filters, deep links, the empty state, locked content, an unavailable video provider, and admin access before a public announcement.

## 8. Backups, monitoring, and ongoing maintenance

- Enable provider deploy/error notifications. Review Render request/deploy logs and service health after each release; check Render usage/spend alerts and database/storage quotas.
- Monitor `/api/v1/ready/` with an external uptime checker that supports HTTP checks. It is a readiness probe, not a traffic-generation/wake-up workaround for a free/sleeping plan.
- Decide and test a database backup/restore process before launch. Supabase's paid plans have scheduled database backups, but **database backups do not include the bytes in Storage buckets**. Keep a separate, encrypted off-provider copy of important uploaded course files and periodically test restoring both the database and its objects. [Supabase backup contents/retention](https://supabase.com/docs/guides/platform/backups).
- Review **Registration invites** and **Learners** occasionally. While registration is invitation-only there is no open sign-up to abuse, so no rate limit is needed; the risk moves to the links themselves. Send them privately rather than posting them publicly, keep the default expiry, revoke anything that leaked, and deactivate a learner in the admin if an account should stop working. Sign-in stays rate limited per email address. If you switch `LEARNER_REGISTRATION` to `open`, put a CDN/WAF rate limit in front of the domain first.
- Keep production database and Storage project credentials in Render secrets only. Rotate the Django key, database password, and powerful S3 key through a planned deploy if access is suspected to be exposed.
- Review Dependabot pull requests and GitHub Actions. Deploy only when the checks pass. Test migrations/backups with staging data first. Do not use `--fake` migrations or edit live database tables by hand.
- Increase service/database capacity when real monitoring/load tests demonstrate a need; run a load test against a non-production environment before campaigns or high-traffic announcements.
- The built Docker image and local `.env` files are never the source of truth for uploaded documents. Production uploads are in Supabase Storage; database content is in Supabase Postgres.

## Troubleshooting

### Missing database tables after a deploy

`ProgrammingError: relation "valour_registrationinvite" does not exist` means the running code can reach PostgreSQL, but its schema is missing the invitation table. The table is already defined in committed migration `valour.0006_registrationinvite`; **do not generate a new migration, create the table by hand, reset the database, or use `--fake`**.

In the affected **Render web service's Shell**, from `/app`, use the same configured `DATABASE_URL` as the web process:

```bash
python backend/valour_tech_sectors/manage.py showmigrations valour
python backend/valour_tech_sectors/manage.py migrate --noinput
python backend/valour_tech_sectors/manage.py showmigrations valour
```

The last output should include `[X] 0006_registrationinvite` (and `[X] 0005_learner`). Refresh `/admin/valour/registrationinvite/` and check `/api/v1/ready/`. Applying pending migrations preserves existing courses, staff accounts, and learners. If `0006` is not listed at all, the deployed image is old: deploy the commit containing it first. If it is **already marked `[X]` before migrating** but the table is still absent, stop and investigate the database/project, schema/search path, and migration history. `migrate` will not recreate a table whose migration was marked applied; resolve that discrepancy with a backup/staging copy rather than faking or deleting history on the live database.

For future deploys:

- Rebuild/deploy the updated Docker image and use its default command/entrypoint. In a manually created Render Docker service, clear any old **Docker Command** override unless needed; editing `render.yaml` alone does **not** update a service that is not managed by that Blueprint.
- On paid services, set/sync **Pre-Deploy Command** to the checks → `prepare_database` → `verify_storage` command in [`render.yaml`](../render.yaml). Startup remains a fallback if that hook is absent, and the readiness probe now rejects missing tables or columns.
- Set Render's **Health Check Path** to `/api/v1/ready/`, not the liveness-only `/api/v1/health/`.
- Keep `DJANGO_DEBUG=false` in Render's Environment page and redeploy. A detailed Django traceback shown in the browser indicates debug mode is enabled; it must not be used in production. The updated production entrypoint refuses to start in that mode.

### Other symptoms

| Symptom | First checks |
| --- | --- |
| Deploy stops at Django checks | Confirm exact hosts/origins, a unique 50+ character secret, `DEBUG=false`, PostgreSQL `DATABASE_URL`, private Storage credentials, and S3 region. Run the deployment check from the Render Shell after configuration: `python backend/valour_tech_sectors/manage.py check --deploy`. |
| Health check is red / readiness is 503 | Confirm the pooler hostname/port/username and URL-encoded password, Supabase database is available, SSL is required, and Render uses the same service region. A live health route does **not** imply database readiness. |
| Database login/deploy times out | Use the project-specific Session pooler string from Supabase **Connect** (not `localhost`, not a guessed host, not the transaction-mode string). Confirm the Supabase project is not paused and network restrictions allow Render. Do not paste the full URI into logs. |
| Admin login redirects repeatedly or says CSRF failed | Use HTTPS and the exact hostname. Set the exact `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`, then redeploy. Never disable CSRF or secure cookies in production. |
| Admin displays without styling / frontend chunks 404 | Check the image build completed `npm ci`, `npm run build`, and Django `collectstatic`; inspect `/static/admin/...` and `/static/site/assets/...` in the browser Network panel. Rebuild the image after source/build configuration changes. |
| Storage upload fails | Recheck the private bucket name, allowed max size, S3 protocol, region, project URL, generated S3 key/secret, and delete/write permissions. Run `verify_storage` in Render Shell. Do not switch the bucket public to fix a signing problem. |
| A link shows a stale access error | Signed download URLs intentionally expire after five minutes. Reload the lesson to obtain a new authorized link. Changing a lock/publish flag cannot revoke a URL already signed until its short expiry; contact Supabase support for immediate project-wide URL signing-key incidents. |
| The admin username is temporarily locked | Wait for the 15-minute cool-off or use `axes_reset_username` from an authorized Render Shell. Do not disable login protections. |
| A learner says sign-in does not work | Check the address is spelled as registered (accounts are stored lowercased), then open **Learners** in `/admin/`: the Access column shows a lockout or a deactivated account, and the **Unlock sign-in** action clears a lockout at once. |
| A learner says their invitation link does not work | The page tells them why. Check the link in **Registration invites**: **Used** means it already registered someone (possibly them — look under **Learners**), **Expired** can be fixed with the extend action, **Revoked** was withdrawn on purpose. Otherwise generate a new link. |
| A generated invitation link has the wrong hostname | Django builds the absolute link from the request it received. Confirm `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` list the real domain and that Render forwards `X-Forwarded-Proto`; then generate the link again while signed in on that domain. |
| A learner forgot their password | Self-service reset needs email delivery, which is not configured. Open the learner in `/admin/`, choose **Set a new sign-in password**, and share it through a private channel. |
| Lesson content opens without a sign-in | Confirm `LEARNER_CONTENT_ACCESS` is `lessons` or `everything` in Render's Environment page, and that the service redeployed after the change. |

## Configuration reference files

- [`render.yaml`](../render.yaml) — Render service, paid plan, checks, migration command, and secret prompts.
- [`.env.production.example`](../.env.production.example) — names/formats of runtime settings; intentionally filled with placeholders.
- [`Dockerfile`](../Dockerfile) — reproducible multi-stage frontend build and non-root Gunicorn runtime.
- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) — backend/Postgres, production setting, frontend, audit, and image checks.
- [Backend setup](../backend/README.md) — local Django commands.

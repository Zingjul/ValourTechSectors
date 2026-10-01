#!/bin/sh
set -eu

# Render services created outside the Blueprint may not run its pre-deploy
# hook. Never serve new code against an old schema, even on those services.
cd "$(dirname "$0")/.."
python backend/valour_tech_sectors/manage.py check --deploy --fail-level ERROR
python backend/valour_tech_sectors/manage.py prepare_database

# Replace the shell so Gunicorn receives shutdown signals directly.
exec "$@"

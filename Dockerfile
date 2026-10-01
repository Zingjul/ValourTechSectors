# syntax=docker/dockerfile:1
# Build the browser bundle separately; Node and dev dependencies do not ship.
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/valourTechSector/package.json frontend/valourTechSector/package-lock.json ./
RUN npm ci
COPY frontend/valourTechSector/ ./
RUN npm run build

FROM python:3.14-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_DEBUG=false \
    PORT=10000
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app
COPY backend/ ./backend/
COPY --from=frontend /frontend/dist ./frontend/valourTechSector/dist
# Static collection needs no database or production secrets. Debug is scoped to
# this build command only; production settings are validated at runtime.
RUN DJANGO_DEBUG=true python backend/valour_tech_sectors/manage.py collectstatic --noinput \
    && chown -R app:app /app
USER app
EXPOSE 10000
# Apply/check migrations before serving, even without Render's pre-deploy hook.
ENTRYPOINT ["/bin/sh", "/app/backend/entrypoint.sh"]
CMD ["gunicorn", "--config", "backend/gunicorn.conf.py", "valour_tech_sectors.wsgi:application"]

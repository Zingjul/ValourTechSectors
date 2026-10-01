import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

import dj_database_url
from botocore.config import Config
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parents[1]
load_dotenv(REPO_ROOT / ".env", override=False)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip().lower()
    if value not in {"1", "true", "yes", "on", "0", "false", "no", "off"}:
        raise ImproperlyConfigured(f"{name} must be true or false.")
    return value in {"1", "true", "yes", "on"}


def env_int(name: str, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be an integer.") from None
    if value < minimum or (maximum is not None and value > maximum):
        raise ImproperlyConfigured(f"{name} is outside its supported range.")
    return value


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# Fail closed: local development explicitly enables debug in the untracked .env.
DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-local-development-only")
if not DEBUG and (
    len(SECRET_KEY) < 50
    or len(set(SECRET_KEY)) < 5
    or SECRET_KEY.startswith(("django-insecure-", "replace-with"))
):
    raise ImproperlyConfigured("Set a unique, random DJANGO_SECRET_KEY of at least 50 characters before deployment.")

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    "localhost,127.0.0.1,0.0.0.0,testserver,.e2b.app" if DEBUG else "",
)
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip().lower()
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS))
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "https://*.e2b.app" if DEBUG else "",
)
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS))
if not DEBUG:
    if not ALLOWED_HOSTS or any(
        "*" in host or host.startswith(".") or "/" in host or ":" in host
        for host in ALLOWED_HOSTS
    ):
        raise ImproperlyConfigured("Production DJANGO_ALLOWED_HOSTS must contain exact hostnames without schemes, ports, or wildcards.")
    if any(
        not origin.startswith("https://") or "*" in origin
        or not urlparse(origin).hostname
        or urlparse(origin).path not in {"", "/"}
        for origin in CSRF_TRUSTED_ORIGINS
    ):
        raise ImproperlyConfigured("Production DJANGO_CSRF_TRUSTED_ORIGINS must contain exact HTTPS origins without wildcards.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "storages",
    "axes",
    "valour.apps.ValourConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "valour.middleware.ApiResponseMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "valour_tech_sectors.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "valour_tech_sectors.wsgi.application"
ASGI_APPLICATION = "valour_tech_sectors.asgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DEBUG and (not DATABASE_URL or urlparse(DATABASE_URL).scheme not in {"postgres", "postgresql"}):
    raise ImproperlyConfigured("Set DATABASE_URL to a PostgreSQL connection string before deployment.")
if DATABASE_URL:
    try:
        database = dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=env_int("DATABASE_CONN_MAX_AGE", 60),
            conn_health_checks=True,
            ssl_require=not DEBUG,
        )
    except (ValueError, KeyError):
        # Do not include the connection string (or password) in startup errors.
        raise ImproperlyConfigured("DATABASE_URL is not a valid database connection string.") from None
    if database["ENGINE"] == "django.db.backends.postgresql":
        database["DISABLE_SERVER_SIDE_CURSORS"] = True
        database.setdefault("OPTIONS", {}).update(
            connect_timeout=env_int("DATABASE_CONNECT_TIMEOUT", 5, minimum=1, maximum=30),
            prepare_threshold=None,
        )
    DATABASES = {"default": database}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "local.sqlite3"}}

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Database-backed lockouts work across workers and deploys. Lock by username,
# not spoofable forwarded IP headers; do not retain staff IP addresses.
AXES_ONLY_ADMIN_SITE = True
AXES_LOCKOUT_PARAMETERS = ["username"]
AXES_CLIENT_IP_CALLABLE = "valour.security.no_client_ip"
AXES_FAILURE_LIMIT = env_int("ADMIN_LOGIN_FAILURE_LIMIT", 5, minimum=3, maximum=20)
AXES_COOLOFF_TIME = timedelta(minutes=env_int("ADMIN_LOGIN_COOLOFF_MINUTES", 15, minimum=1))
AXES_RESET_ON_SUCCESS = True
AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT = False
AXES_DISABLE_ACCESS_LOG = True
AXES_ENABLE_ACCESS_FAILURE_LOG = False
AXES_ALLOWED_CORS_ORIGINS = []
# Axes' generic IP warning also flags its documented username-only privacy
# configuration. Rotation of IP/user-agent/cookies cannot bypass a username
# lockout (covered by tests); do not trust arbitrary proxy headers instead.
SILENCED_SYSTEM_CHECKS = ["axes.W006"]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
FRONTEND_DIST = REPO_ROOT / "frontend" / "valourTechSector" / "dist"
STATICFILES_DIRS = [FRONTEND_DIST / "static"] if (FRONTEND_DIST / "static").is_dir() else []
WHITENOISE_IMMUTABLE_FILE_TEST = "valour.security.immutable_static_file"
WHITENOISE_MAX_AGE = 60
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "").strip()
SUPABASE_S3_ACCESS_KEY_ID = os.getenv("SUPABASE_S3_ACCESS_KEY_ID", "").strip()
SUPABASE_S3_SECRET_ACCESS_KEY = os.getenv("SUPABASE_S3_SECRET_ACCESS_KEY", "").strip()
SUPABASE_S3_REGION = os.getenv("SUPABASE_S3_REGION", "us-east-1" if DEBUG else "").strip()
SUPABASE_STORAGE_SIGNED_URL_TTL = env_int("SUPABASE_STORAGE_SIGNED_URL_TTL", 300, minimum=30, maximum=3600)
MAX_COURSE_FILE_SIZE_MB = env_int("MAX_COURSE_FILE_SIZE_MB", 25, minimum=1, maximum=100)

_storage_credentials = (SUPABASE_URL, SUPABASE_STORAGE_BUCKET, SUPABASE_S3_ACCESS_KEY_ID, SUPABASE_S3_SECRET_ACCESS_KEY)
if any(_storage_credentials) and not all(_storage_credentials):
    raise ImproperlyConfigured(
        "Configure SUPABASE_URL, SUPABASE_STORAGE_BUCKET, SUPABASE_S3_ACCESS_KEY_ID, "
        "and SUPABASE_S3_SECRET_ACCESS_KEY together, or leave all four blank for local development storage."
    )
if not DEBUG and not all(_storage_credentials):
    raise ImproperlyConfigured("Configure private Supabase Storage before deployment; local media is development-only.")
if SUPABASE_URL:
    _storage_url = urlparse(SUPABASE_URL)
    if (
        _storage_url.scheme != "https" or not _storage_url.hostname
        or _storage_url.username or _storage_url.password
        or _storage_url.path or _storage_url.query or _storage_url.fragment
    ):
        raise ImproperlyConfigured("SUPABASE_URL must be the HTTPS project origin, without a path or credentials.")
if all(_storage_credentials) and not SUPABASE_S3_REGION:
    raise ImproperlyConfigured("Set SUPABASE_S3_REGION to the region shown in Supabase Storage S3 settings.")

if all(_storage_credentials):
    default_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": SUPABASE_STORAGE_BUCKET,
            "endpoint_url": f"{SUPABASE_URL}/storage/v1/s3",
            "region_name": SUPABASE_S3_REGION,
            "access_key": SUPABASE_S3_ACCESS_KEY_ID,
            "secret_key": SUPABASE_S3_SECRET_ACCESS_KEY,
            "signature_version": "s3v4",
            "addressing_style": "path",
            "querystring_auth": True,
            "querystring_expire": SUPABASE_STORAGE_SIGNED_URL_TTL,
            "file_overwrite": False,
            "default_acl": None,
            "client_config": Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 2, "mode": "standard"},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
            "object_parameters": {
                "CacheControl": "private, max-age=0, no-store",
                "ContentDisposition": "attachment",
            },
        },
    }
else:
    default_storage = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
STORAGES = {
    "default": default_storage,
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Render terminates TLS and sets this header. If deploying elsewhere, put the
# application behind a trusted proxy that overwrites X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SECURE_REDIRECT_EXEMPT = [r"^api/v1/(?:health|ready)/$"]
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 3600 if not DEBUG else 0)
# Opt in only after verifying HTTPS on every affected subdomain.
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
if not DEBUG and not SECURE_SSL_REDIRECT:
    raise ImproperlyConfigured("HTTPS redirects must remain enabled in production.")

FRONTEND_CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "frame-src https://www.youtube-nocookie.com https://www.tiktok.com https://www.facebook.com",
    "upgrade-insecure-requests",
])

EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "webmaster@localhost")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"standard": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout", "formatter": "standard"}},
    "root": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")},
    "loggers": {
        "django": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"), "propagate": False},
        "axes": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

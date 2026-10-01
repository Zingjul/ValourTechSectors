import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import skipUnless
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from zipfile import ZipFile

from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import Course, Lesson, Material, Section, VideoLink, validate_material_size
from .security import immutable_static_file
from .site import _frontend_html
from .testing import force_sign_in
from .validators import validate_material_content


@override_settings(DEBUG=True)
class HealthTests(TestCase):
    def test_liveness_does_not_query_the_database(self):
        with self.assertNumQueries(0):
            response = self.client.get(reverse("valour:health"))
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertIn("no-store", response["Cache-Control"])

    def test_readiness_checks_the_database(self):
        with self.assertNumQueries(1):
            response = self.client.get(reverse("valour:ready"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_readiness_failure_does_not_leak_connection_details(self):
        with patch("valour.views.connections") as connections:
            connections["default"].cursor.side_effect = DatabaseError("password=do-not-leak")
            with self.assertLogs("valour.views", level="ERROR") as logs:
                response = self.client.get(reverse("valour:ready"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotIn("do-not-leak", " ".join(logs.output) + response.content.decode())

    @override_settings(DEBUG=False, FRONTEND_DIST=Path("/missing-frontend-build"))
    def test_production_readiness_requires_a_frontend_build(self):
        with self.assertLogs("valour.views", level="ERROR"):
            response = self.client.get(reverse("valour:ready"))
        self.assertEqual(response.status_code, 503)

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_probe_endpoints_accept_internal_http_and_head(self):
        for name in ("valour:health", "valour:ready"):
            with self.subTest(name=name):
                response = self.client.head(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, b"")

    def test_api_methods_return_json_and_preserve_allow_header(self):
        response = self.client.post(reverse("valour:course-list"))
        self.assertEqual(response.status_code, 405)
        self.assertIn("GET", response["Allow"])
        self.assertIn("HEAD", response["Allow"])
        self.assertIn("message", response.json())
        self.assertIn("no-store", response["Cache-Control"])


class FrontendServingTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.html = '<!doctype html><html><body><div id="root">test frontend</div></body></html>'
        (Path(self.directory.name) / "index.html").write_text(self.html)
        self.override = override_settings(DEBUG=False, FRONTEND_DIST=Path(self.directory.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        _frontend_html.cache_clear()
        self.addCleanup(_frontend_html.cache_clear)

    def test_deep_links_and_optional_trailing_slashes_serve_the_spa(self):
        for path in ("/", "/courses", "/courses/", "/courses/resistors", "/lessons/ohms/", "/contact", "/signin", "/signup/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content.decode(), self.html)
                self.assertEqual(response["Cache-Control"], "no-store")
                self.assertIn("script-src 'self'", response["Content-Security-Policy"])
                self.assertIn("style-src 'self'", response["Content-Security-Policy"])
                self.assertNotIn("unsafe-inline", response["Content-Security-Policy"])
                self.assertIn("youtube-nocookie.com", response["Content-Security-Policy"])

    def test_unknown_learner_route_has_real_404_with_spa_error_screen(self):
        response = self.client.get("/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content.decode(), self.html)

    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_HSTS_SECONDS=3600)
    def test_production_redirects_http_and_sets_hsts_for_https(self):
        response = self.client.get("/courses")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "https://testserver/courses")
        response = self.client.get("/courses", HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Strict-Transport-Security"], "max-age=3600")

    def test_api_admin_and_missing_assets_are_not_rewritten_to_html(self):
        response = self.client.get("/api/v1/does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("message", response.json())
        admin_response = self.client.get("/admin/missing/")
        self.assertIn(admin_response.status_code, (302, 404))
        self.assertNotIn("test frontend", admin_response.content.decode())
        for path in ("/static/site/assets/missing.js", "/media/missing.pdf"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("test frontend", response.content.decode())

    def test_missing_frontend_build_is_503_not_a_blank_success_page(self):
        (Path(self.directory.name) / "index.html").unlink()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "60")

    def test_robots_excludes_staff_and_api_routes(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Disallow: /admin/", response.content)
        self.assertIn(b"Disallow: /api/", response.content)
        self.assertIn(b"Disallow: /signin", response.content)
        self.assertIn(b"Disallow: /signup", response.content)

    def test_only_hashed_static_assets_are_immutable(self):
        for path in ("/static/site/assets/index-AbCd1234.js", "/static/admin/css/base.123456abcdef.css"):
            self.assertTrue(immutable_static_file("unused", path))
        for path in ("/static/site/index.html", "/static/site/favicon.svg", "/static/admin/css/base.css"):
            self.assertFalse(immutable_static_file("unused", path))


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class AdminSecurityTests(TestCase):
    def setUp(self):
        self.password = "A-unique-test-password-1234"
        get_user_model().objects.create_superuser("staff", "staff@example.com", self.password)
        self.login_url = reverse("admin:login")

    def fail_logins(self):
        for _ in range(settings.AXES_FAILURE_LIMIT):
            response = self.client.post(self.login_url, {"username": "staff", "password": "wrong"})
        return response

    def test_staff_login_lockout_cannot_be_bypassed_by_forwarded_ip_or_user_agent(self):
        self.assertEqual(self.fail_logins().status_code, 429)
        for address in ("203.0.113.1", "198.51.100.2"):
            with self.subTest(address=address):
                response = Client().post(
                    self.login_url,
                    {"username": "staff", "password": self.password, "next": "/admin/"},
                    HTTP_X_FORWARDED_FOR=address,
                    HTTP_USER_AGENT=address,
                )
                self.assertEqual(response.status_code, 429)
        from axes.models import AccessAttempt
        self.assertFalse(AccessAttempt.objects.exclude(ip_address=None).exists())

    def test_a_locked_username_does_not_lock_other_staff_accounts(self):
        self.fail_logins()
        get_user_model().objects.create_superuser("second", "second@example.com", self.password)
        response = Client().post(self.login_url, {"username": "second", "password": self.password, "next": "/admin/"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/admin/")

    def test_lockout_can_be_reset_from_render_shell(self):
        self.fail_logins()
        call_command("axes_reset_username", "staff", stdout=io.StringIO())
        response = self.client.post(self.login_url, {"username": "staff", "password": self.password, "next": "/admin/"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/admin/")

    def test_admin_post_requires_csrf(self):
        response = Client(enforce_csrf_checks=True).post(self.login_url, {"username": "staff", "password": self.password})
        self.assertEqual(response.status_code, 403)

    @override_settings(SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_staff_session_cookies_are_secure_http_only_and_same_site(self):
        self.client.get(self.login_url)
        self.client.post(self.login_url, {"username": "staff", "password": self.password})
        cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")

    def test_passwords_require_at_least_twelve_characters(self):
        with self.assertRaises(ValidationError):
            validate_password("small")


class AccessAndQueryTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(title="Resistors", slug="resistors", is_published=True)
        self.section = Section.objects.create(course=self.course, title="Basics")
        self.lesson = Lesson.objects.create(section=self.section, title="Ohms", slug="ohms", notes="Protected lesson notes")
        self.material = Material.objects.create(lesson=self.lesson, title="Notes", kind="pdf", file="course-materials/notes.pdf")

    def test_course_outline_query_count_does_not_grow_with_lessons(self):
        for index in range(8):
            section = Section.objects.create(course=self.course, title=f"Section {index}")
            lesson = Lesson.objects.create(section=section, title=f"Lesson {index}", slug=f"lesson-{index}")
            VideoLink.objects.create(lesson=lesson, platform="youtube", url="https://youtu.be/dQw4w9WgXcQ")
            Material.objects.create(lesson=lesson, title="PDF", kind="pdf", file="course-materials/test.pdf")
        with self.assertNumQueries(5):
            response = self.client.get(reverse("valour:course-detail", args=[self.course.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["sections"]), 9)

    def test_lesson_prefetches_only_public_materials_and_active_videos(self):
        VideoLink.objects.create(lesson=self.lesson, platform="youtube", url="https://youtu.be/dQw4w9WgXcQ", is_active=False)
        Material.objects.create(lesson=self.lesson, title="Draft", kind="pdf", file="course-materials/draft.pdf", is_published=False)
        force_sign_in(self.client)
        # 3 content queries plus the session and learner lookups a signed-in
        # request needs; neither grows with the number of materials or videos.
        with self.assertNumQueries(5):
            response = self.client.get(reverse("valour:lesson-detail", args=[self.lesson.slug]))
        self.assertEqual(response.json()["videos"], [])
        self.assertEqual(len(response.json()["materials"]), 1)

    def test_each_ancestor_lock_prevents_file_signing(self):
        for item in (self.course, self.section, self.lesson, self.material):
            with self.subTest(model=type(item).__name__):
                item.is_locked = True
                item.save()
                with patch("django.core.files.storage.FileSystemStorage.url") as signer:
                    response = self.client.get(reverse("valour:material-download", args=[self.material.pk]))
                self.assertEqual(response.status_code, 403)
                signer.assert_not_called()
                item.is_locked = False
                item.save()

    def test_each_unpublished_ancestor_prevents_file_signing(self):
        for item in (self.course, self.section, self.lesson, self.material):
            with self.subTest(model=type(item).__name__):
                item.is_published = False
                item.save()
                with patch("django.core.files.storage.FileSystemStorage.url") as signer:
                    response = self.client.get(reverse("valour:material-download", args=[self.material.pk]))
                self.assertEqual(response.status_code, 404)
                signer.assert_not_called()
                item.is_published = True
                item.save()

    @override_settings(SUPABASE_URL="https://example.supabase.co")
    def test_signed_redirects_cannot_be_cached_or_leak_referrers(self):
        force_sign_in(self.client)
        with patch("django.core.files.storage.FileSystemStorage.url", return_value="https://example.supabase.co/file?X-Amz-Signature=secret"):
            response = self.client.get(reverse("valour:material-download", args=[self.material.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["Referrer-Policy"], "no-referrer")

    def test_file_download_rejects_untrusted_and_insecure_redirect_targets(self):
        force_sign_in(self.client)
        for file_url in ("//attacker.example/file.pdf", "http://example.supabase.co/file.pdf", "https://attacker.example/file.pdf"):
            with self.subTest(file_url=file_url):
                with patch("django.core.files.storage.FileSystemStorage.url", return_value=file_url):
                    response = self.client.get(reverse("valour:material-download", args=[self.material.pk]))
                self.assertEqual(response.status_code, 404)

    def test_storage_errors_are_sanitized_and_return_503(self):
        force_sign_in(self.client)
        error = ClientError({"Error": {"Code": "InvalidAccessKey", "Message": "private-secret"}}, "GetObject")
        with patch("django.core.files.storage.FileSystemStorage.url", side_effect=error):
            with self.assertLogs("valour.views", level="ERROR") as logs:
                response = self.client.get(reverse("valour:material-download", args=[self.material.pk]))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private-secret", response.content.decode() + " ".join(logs.output))


class SupabaseRowLevelSecurityTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(title="Private by default", slug="private-by-default", is_published=False)

    @skipUnless(connection.vendor == "postgresql", "Supabase RLS behavior requires PostgreSQL")
    def test_browser_data_api_role_cannot_read_django_tables_without_a_policy(self):
        role = "valour_rls_test_anon"
        # valour_learner holds sign-up records, so it needs the same protection
        # that migration 0004 gave the tables that already existed.
        for table in ("valour_course", "valour_learner"):
            with self.subTest(table=table), connection.cursor() as cursor:
                cursor.execute(f"CREATE ROLE {role} NOLOGIN")
                try:
                    cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
                    cursor.execute(f"GRANT SELECT ON TABLE {table} TO {role}")
                    cursor.execute(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{table}'")
                    self.assertTrue(cursor.fetchone()[0], "RLS migration must protect every Django-managed table")
                    cursor.execute(f"SET ROLE {role}")
                    cursor.execute(f"SELECT count(*) FROM {table}")
                    self.assertEqual(cursor.fetchone()[0], 0, "No RLS policy should expose Django rows to browser roles")
                finally:
                    cursor.execute("RESET ROLE")
                    cursor.execute(f"REVOKE ALL ON TABLE {table} FROM {role}")
                    cursor.execute(f"REVOKE USAGE ON SCHEMA public FROM {role}")
                    cursor.execute(f"DROP ROLE {role}")
        self.assertTrue(Course.objects.filter(pk=self.course.pk).exists(), "The database owner must retain Django access")


class UploadValidationTests(SimpleTestCase):
    def test_pdf_signature_is_checked_and_stream_position_restored(self):
        upload = SimpleUploadedFile("notes.pdf", b"%PDF-1.4\nexample")
        upload.seek(5)
        validate_material_content(upload)
        self.assertEqual(upload.tell(), 5)
        with self.assertRaises(ValidationError):
            validate_material_content(SimpleUploadedFile("renamed.pdf", b"<html>not a PDF</html>"))

    def test_word_doc_signature_is_checked(self):
        validate_material_content(SimpleUploadedFile("notes.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1data"))
        with self.assertRaises(ValidationError):
            validate_material_content(SimpleUploadedFile("renamed.doc", b"not a Word document"))

    def docx(self, *, macros=False):
        stream = io.BytesIO()
        with ZipFile(stream, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("word/document.xml", "<document/>")
            if macros:
                archive.writestr("word/vbaProject.bin", "macro")
        return SimpleUploadedFile("notes.docx", stream.getvalue())

    def test_docx_requires_word_structure_and_rejects_macros_and_bad_zip(self):
        validate_material_content(self.docx())
        for upload in (self.docx(macros=True), SimpleUploadedFile("bad.docx", b"PK-invalid")):
            with self.assertRaises(ValidationError):
                validate_material_content(upload)

    @override_settings(MAX_COURSE_FILE_SIZE_MB=1)
    def test_upload_limit_and_error_message_use_the_configured_size(self):
        upload = SimpleUploadedFile("notes.pdf", b"x" * (1024 * 1024 + 1))
        with self.assertRaisesMessage(ValidationError, "1 MB or smaller"):
            validate_material_size(upload)

    def test_editing_existing_file_metadata_does_not_fetch_the_s3_object(self):
        saved_file = MagicMock(_committed=True)
        validate_material_content(saved_file)
        saved_file.read.assert_not_called()


class ProductionSettingsTests(SimpleTestCase):
    def settings_environment(self, **overrides):
        environment = dict(os.environ)
        environment.update({
            "DJANGO_SETTINGS_MODULE": "valour_tech_sectors.settings",
            "DJANGO_DEBUG": "false",
            "DJANGO_SECRET_KEY": "ci-only-unique-secret-for-production-configuration-tests-1234567890",
            "DJANGO_ALLOWED_HOSTS": "learn.example.com",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://learn.example.com",
            "DJANGO_SECURE_SSL_REDIRECT": "true",
            "RENDER_EXTERNAL_HOSTNAME": "",
            "DATABASE_URL": "postgres://example:example@db.example.com:5432/postgres",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_STORAGE_BUCKET": "course-materials",
            "SUPABASE_S3_ACCESS_KEY_ID": "example-access-key",
            "SUPABASE_S3_SECRET_ACCESS_KEY": "example-secret-key",
            "SUPABASE_S3_REGION": "eu-central-1",
            "SUPABASE_STORAGE_SIGNED_URL_TTL": "300",
            "MAX_COURSE_FILE_SIZE_MB": "25",
        })
        for name, value in overrides.items():
            if value is None:
                environment.pop(name, None)
            else:
                environment[name] = value
        return environment

    def run_settings_code(self, code, **overrides):
        """Import the settings module in a subprocess with a production environment."""
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=settings.BASE_DIR,
            env=self.settings_environment(**overrides),
            text=True,
            capture_output=True,
            timeout=15,
        )

    def load_settings(self, **overrides):
        code = (
            "import dotenv; dotenv.load_dotenv = lambda *args, **kwargs: False; "
            "import json; from django.conf import settings as s; "
            "print(json.dumps({'debug': s.DEBUG, 'hosts': s.ALLOWED_HOSTS, "
            "'origins': s.CSRF_TRUSTED_ORIGINS, 'ssl': s.DATABASES['default']['OPTIONS']['sslmode'], "
            "'secure_cookies': s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE, "
            "'health_checks': s.DATABASES['default']['CONN_HEALTH_CHECKS']}))"
        )
        return self.run_settings_code(code, **overrides)

    def test_production_defaults_disable_debug_and_enforce_database_tls(self):
        result = self.load_settings(DJANGO_DEBUG=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data["debug"])
        self.assertEqual(data["ssl"], "require")
        self.assertTrue(data["secure_cookies"])
        self.assertTrue(data["health_checks"])

    def test_render_hostname_is_allowed_without_a_custom_domain(self):
        result = self.load_settings(
            DJANGO_ALLOWED_HOSTS="", DJANGO_CSRF_TRUSTED_ORIGINS="",
            RENDER_EXTERNAL_HOSTNAME="valourtech.onrender.com",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["hosts"], ["valourtech.onrender.com"])
        self.assertEqual(data["origins"], ["https://valourtech.onrender.com"])

    def test_missing_or_weak_secret_fails_closed(self):
        for secret in (None, "short", "x" * 60):
            with self.subTest(secret=secret):
                result = self.load_settings(DJANGO_SECRET_KEY=secret)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_local_database_and_missing_storage_are_not_production_fallbacks(self):
        for values in ({"DATABASE_URL": ""}, {"DATABASE_URL": "sqlite:///local.sqlite3"}, {"SUPABASE_S3_SECRET_ACCESS_KEY": ""}, {"SUPABASE_S3_REGION": ""}):
            with self.subTest(values=values):
                self.assertNotEqual(self.load_settings(**values).returncode, 0)

    def test_wildcard_hosts_and_insecure_or_wildcard_csrf_origins_are_rejected(self):
        for values in (
            {"DJANGO_ALLOWED_HOSTS": "*"}, {"DJANGO_ALLOWED_HOSTS": ".e2b.app"},
            {"DJANGO_CSRF_TRUSTED_ORIGINS": "http://learn.example.com"},
            {"DJANGO_CSRF_TRUSTED_ORIGINS": "https://*.example.com"},
        ):
            with self.subTest(values=values):
                self.assertNotEqual(self.load_settings(**values).returncode, 0)

    def test_invalid_flags_ttl_and_storage_origin_are_rejected(self):
        for values in (
            {"DJANGO_DEBUG": "tru"}, {"DJANGO_SECURE_SSL_REDIRECT": "false"},
            {"SUPABASE_STORAGE_SIGNED_URL_TTL": "0"}, {"SUPABASE_STORAGE_SIGNED_URL_TTL": "7200"},
            {"SUPABASE_URL": "https://example.supabase.co/storage/v1/s3"},
        ):
            with self.subTest(values=values):
                self.assertNotEqual(self.load_settings(**values).returncode, 0)

    def test_invalid_learner_account_settings_are_rejected(self):
        for values in (
            {"LEARNER_CONTENT_ACCESS": "members"}, {"LEARNER_CONTENT_ACCESS": ""},
            {"LEARNER_LOGIN_FAILURE_LIMIT": "2"}, {"LEARNER_LOGIN_LOCKOUT_MINUTES": "0"},
            {"LEARNER_PASSWORD_MIN_LENGTH": "6"}, {"LEARNER_SESSION_REMEMBER_DAYS": "0"},
        ):
            with self.subTest(values=values):
                result = self.load_settings(**values)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(next(iter(values)), result.stderr)

    def test_learner_defaults_gate_lessons_without_touching_the_staff_policy(self):
        code = (
            "import dotenv; dotenv.load_dotenv = lambda *args, **kwargs: False; "
            "import json; from django.conf import settings as s; "
            "print(json.dumps({'access': s.LEARNER_CONTENT_ACCESS, "
            "'backends': s.AUTHENTICATION_BACKENDS, "
            "'staff_minimum': s.AUTH_PASSWORD_VALIDATORS[1]['OPTIONS']['min_length'], "
            "'learner_minimum': s.LEARNER_PASSWORD_MIN_LENGTH}))"
        )
        result = self.run_settings_code(code)

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["access"], "lessons")
        self.assertEqual(data["staff_minimum"], 12)
        self.assertEqual(data["learner_minimum"], 8)
        # django-axes stays first so admin lockouts keep working, and the learner
        # backend runs before ModelBackend for email sign-ins.
        self.assertEqual(
            data["backends"],
            [
                "axes.backends.AxesStandaloneBackend",
                "valour.auth_backends.LearnerBackend",
                "django.contrib.auth.backends.ModelBackend",
            ],
        )


@override_settings(SUPABASE_URL="https://example.supabase.co", SUPABASE_STORAGE_BUCKET="course-materials")
class StorageVerificationTests(SimpleTestCase):
    def run_probe(self, public=True):
        storage = MagicMock()
        storage.save.return_value = "deployment-checks/test.pdf"
        storage.url.return_value = "https://example.supabase.co/file?X-Amz-Signature=example"
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"%PDF-1.4\n% ValourTech storage permission probe\n%%EOF\n"
        responses = [response, response if public else HTTPError("https://example.supabase.co/public", 404, "Not found", {}, None)]
        return storage, responses

    def test_storage_probe_requires_private_objects_and_always_cleans_up(self):
        storage, responses = self.run_probe(public=False)
        output = io.StringIO()
        with patch("valour.management.commands.verify_storage.default_storage", storage):
            with patch("valour.management.commands.verify_storage.urlopen", side_effect=responses):
                call_command("verify_storage", stdout=output)
        storage.delete.assert_called_once_with("deployment-checks/test.pdf")
        self.assertIn("Storage verified", output.getvalue())

    def test_public_bucket_fails_verification_and_probe_is_deleted(self):
        storage, responses = self.run_probe(public=True)
        with patch("valour.management.commands.verify_storage.default_storage", storage):
            with patch("valour.management.commands.verify_storage.urlopen", side_effect=responses):
                with self.assertRaisesMessage(CommandError, "PRIVATE"):
                    call_command("verify_storage", stdout=io.StringIO())
        storage.delete.assert_called_once()

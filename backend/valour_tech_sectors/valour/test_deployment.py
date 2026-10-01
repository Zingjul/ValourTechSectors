"""Regression coverage for production startup and upgrades of an existing DB."""

import io
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse

from .models import Course, Learner, RegistrationInvite


@override_settings(
    DEBUG=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class InvitationSchemaUpgradeTests(TransactionTestCase):
    """Reproduce a deployed app whose DB predates the invitation migration."""

    def setUp(self):
        executor = MigrationExecutor(connection)
        self.latest = executor.loader.graph.leaf_nodes()
        self.addCleanup(self.restore_schema)
        executor.migrate([("valour", "0005_learner")])
        self.old_apps = executor.loader.project_state([("valour", "0005_learner")]).apps
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        (Path(directory.name) / "index.html").write_text("<!doctype html><title>Test site</title>")
        frontend = override_settings(FRONTEND_DIST=Path(directory.name))
        frontend.enable()
        self.addCleanup(frontend.disable)

    def restore_schema(self):
        MigrationExecutor(connection).migrate(self.latest)

    def test_missing_invitation_table_is_not_reported_as_ready(self):
        self.assertNotIn("valour_registrationinvite", connection.introspection.table_names())
        # The server itself is alive and Postgres/SQLite accepts connections.
        self.assertEqual(self.client.get(reverse("valour:health")).status_code, 200)
        with self.assertLogs("valour.views", level="ERROR") as logs:
            response = self.client.get(reverse("valour:ready"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotIn("valour_registrationinvite", response.content.decode() + " ".join(logs.output))

    def test_startup_applies_existing_migration_without_losing_data(self):
        course = self.old_apps.get_model("valour", "Course").objects.create(
            title="Existing course", slug="existing-course"
        )
        learner = self.old_apps.get_model("valour", "Learner").objects.create(
            email="existing@example.com", phone_number="+2348031234567", password="!"
        )
        staff = get_user_model().objects.create_superuser("staff", "staff@example.com", "test-password")

        call_command("prepare_database", stdout=io.StringIO())
        self.assertIn("valour_registrationinvite", connection.introspection.table_names())
        self.assertEqual(Course.objects.get(pk=course.pk).title, "Existing course")
        self.assertEqual(Learner.objects.get(pk=learner.pk).email, "existing@example.com")
        invite = RegistrationInvite.objects.create(created_by=staff, note="New invitation")
        self.client.force_login(staff, backend="django.contrib.auth.backends.ModelBackend")
        self.assertEqual(self.client.get(reverse("admin:valour_registrationinvite_changelist")).status_code, 200)
        self.assertEqual(self.client.get(reverse("valour:ready")).status_code, 200)

        # Repeated container starts must neither recreate tables nor lose links.
        call_command("prepare_database", stdout=io.StringIO())
        self.assertEqual(RegistrationInvite.objects.get(pk=invite.pk).note, "New invitation")
        self.assertEqual(Course.objects.count(), 1)
        self.assertEqual(Learner.objects.count(), 1)

    def test_recorded_migrations_cannot_hide_a_missing_column(self):
        call_command("prepare_database", stdout=io.StringIO())
        table = connection.ops.quote_name("valour_registrationinvite")
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE {table} RENAME COLUMN note TO missing_note")
        try:
            with self.assertLogs("valour.views", level="ERROR"):
                response = self.client.get(reverse("valour:ready"))
            self.assertEqual(response.status_code, 503)
            with self.assertRaisesMessage(CommandError, "schema verification failed"):
                call_command("prepare_database", stdout=io.StringIO())
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"ALTER TABLE {table} RENAME COLUMN missing_note TO note")
        self.assertEqual(self.client.get(reverse("valour:ready")).status_code, 200)


class ContainerEntrypointTests(SimpleTestCase):
    """Exercise shell ordering and fail-closed behavior without running a server."""

    def run_entrypoint(self, failure=""):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            calls = directory / "calls"
            python = directory / "python"
            python.write_text(
                '#!/bin/sh\n'
                'echo "python $*" >> "$CALLS"\n'
                'case "$*" in\n'
                '  *"check --deploy"*) [ "$FAILURE" != "check" ] || exit 11 ;;\n'
                '  *"prepare_database"*) [ "$FAILURE" != "prepare" ] || exit 12 ;;\n'
                'esac\n'
            )
            gunicorn = directory / "gunicorn"
            gunicorn.write_text('#!/bin/sh\necho "gunicorn $*" >> "$CALLS"\n')
            python.chmod(0o755)
            gunicorn.chmod(0o755)
            environment = {
                **os.environ,
                "PATH": f"{directory}:{os.environ['PATH']}",
                "CALLS": str(calls),
                "FAILURE": failure,
            }
            result = subprocess.run(
                ["/bin/sh", str(settings.REPO_ROOT / "backend" / "entrypoint.sh"), "gunicorn", "--config", "backend/gunicorn.conf.py", "valour_tech_sectors.wsgi:application"],
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result, calls.read_text().splitlines() if calls.exists() else []

    def test_database_is_prepared_before_gunicorn(self):
        result, calls = self.run_entrypoint()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [
            "python backend/valour_tech_sectors/manage.py check --deploy --fail-level ERROR",
            "python backend/valour_tech_sectors/manage.py prepare_database",
            "gunicorn --config backend/gunicorn.conf.py valour_tech_sectors.wsgi:application",
        ])

    def test_failed_check_or_migration_does_not_start_gunicorn(self):
        for failure, code, count in (("check", 11, 1), ("prepare", 12, 2)):
            with self.subTest(failure=failure):
                result, calls = self.run_entrypoint(failure)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(len(calls), count)
                self.assertFalse(any(call.startswith("gunicorn") for call in calls))


class DatabasePreparationTests(SimpleTestCase):
    @override_settings(DEBUG=True)
    def test_production_startup_rejects_debug_mode(self):
        with self.assertRaisesMessage(CommandError, "DJANGO_DEBUG=false"):
            call_command("prepare_database", stdout=io.StringIO())

    @override_settings(DEBUG=False)
    def test_migration_lock_covers_migration_and_schema_verification(self):
        database = MagicMock(vendor="postgresql")
        cursor = database.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (True,)
        events = []
        cursor.execute.side_effect = lambda sql, params: events.append(sql.split("(")[0])
        with patch("valour.management.commands.prepare_database.connection", database), \
                patch("valour.management.commands.prepare_database.call_command", side_effect=lambda *args, **kwargs: events.append("migrate")) as migrate, \
                patch("valour.management.commands.prepare_database.probe_schema", side_effect=lambda db: events.append("schema")) as probe:
            call_command("prepare_database", stdout=io.StringIO())
        self.assertEqual(events, ["SELECT pg_try_advisory_lock", "migrate", "schema", "SELECT pg_advisory_unlock"])
        self.assertEqual(migrate.call_args.args, ("migrate",))
        self.assertFalse(migrate.call_args.kwargs["interactive"])
        probe.assert_called_once_with(database)

    @override_settings(DEBUG=False)
    def test_migration_failure_releases_the_lock_and_skips_the_probe(self):
        database = MagicMock(vendor="postgresql")
        cursor = database.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (True,)
        with patch("valour.management.commands.prepare_database.connection", database), \
                patch("valour.management.commands.prepare_database.call_command", side_effect=CommandError("migration failed")), \
                patch("valour.management.commands.prepare_database.probe_schema") as probe:
            with self.assertRaisesMessage(CommandError, "migration failed"):
                call_command("prepare_database", stdout=io.StringIO())
        self.assertIn("pg_advisory_unlock", cursor.execute.call_args.args[0])
        probe.assert_not_called()

    @override_settings(DEBUG=False)
    def test_lock_timeout_fails_instead_of_racing_another_deploy(self):
        database = MagicMock(vendor="postgresql")
        database.cursor.return_value.__enter__.return_value.fetchone.return_value = (False,)
        with patch("valour.management.commands.prepare_database.connection", database), \
                patch("valour.management.commands.prepare_database.monotonic", side_effect=[0, 61]), \
                patch("valour.management.commands.prepare_database.call_command") as migrate:
            with self.assertRaisesMessage(CommandError, "migration lock"):
                call_command("prepare_database", stdout=io.StringIO())
        migrate.assert_not_called()

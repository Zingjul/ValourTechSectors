from time import monotonic, sleep

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection

from valour.db_health import probe_schema


# Stable, application-specific session lock shared by pre-deploy and startup.
# Supabase must use the Session pooler, not the transaction pooler.
MIGRATION_LOCK_KEY = int.from_bytes(b"VALOUR", "big")
MIGRATION_LOCK_TIMEOUT_SECONDS = 60


class Command(BaseCommand):
    help = "Apply committed migrations and verify the schema before production web startup."
    # Run migration checks inside the lock; entrypoint/pre-deploy runs check --deploy.
    requires_system_checks = []

    def handle(self, *args, **options):
        if settings.DEBUG:
            raise CommandError("Production startup requires DJANGO_DEBUG=false; use migrate for local development.")
        if connection.vendor != "postgresql":
            # Keeps the upgrade regression tests runnable on local SQLite.
            self.prepare(options)
            return

        deadline = monotonic() + MIGRATION_LOCK_TIMEOUT_SECONDS
        with connection.cursor() as cursor:
            while True:
                cursor.execute("SELECT pg_try_advisory_lock(%s)", [MIGRATION_LOCK_KEY])
                if cursor.fetchone()[0]:
                    break
                if monotonic() >= deadline:
                    raise CommandError("Timed out waiting for the database migration lock; another deploy may be running.")
                sleep(1)
        try:
            self.prepare(options)
        finally:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [MIGRATION_LOCK_KEY])
            except DatabaseError:
                # A failed connection cannot safely be reused. Closing it also
                # releases the session lock without masking the migration error.
                connection.close()

    def prepare(self, options):
        # Never fake migrations, generate new ones at boot, or roll back data.
        call_command(
            "migrate",
            interactive=False,
            verbosity=options["verbosity"],
            stdout=self.stdout,
            stderr=self.stderr,
        )
        try:
            probe_schema(connection)
        except DatabaseError:
            raise CommandError(
                "Database schema verification failed after migrations. Check DATABASE_URL, "
                "the database schema/search path, and migration history; do not use --fake."
            ) from None
        self.stdout.write(self.style.SUCCESS("Database migrations applied and schema verified."))

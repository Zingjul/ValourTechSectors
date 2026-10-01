from django.db import migrations


PROTECTED_APP_LABELS = {"admin", "auth", "axes", "contenttypes", "sessions", "valour"}


def set_row_level_security(apps, schema_editor, *, enabled):
    """Block Supabase anon/authenticated Data API access to Django's public tables."""
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    tables = {
        model._meta.db_table
        for model in apps.get_models(include_auto_created=True)
        if model._meta.app_label in PROTECTED_APP_LABELS
    }
    # Django's migration recorder is not represented by an installed model.
    tables.add("django_migrations")
    with connection.cursor() as cursor:
        existing = set(connection.introspection.table_names(cursor))
        for table in sorted(tables & existing):
            statement = "ENABLE" if enabled else "DISABLE"
            cursor.execute(f"ALTER TABLE {connection.ops.quote_name(table)} {statement} ROW LEVEL SECURITY")


def enable_rls(apps, schema_editor):
    set_row_level_security(apps, schema_editor, enabled=True)


def disable_rls(apps, schema_editor):
    set_row_level_security(apps, schema_editor, enabled=False)


class Migration(migrations.Migration):
    dependencies = [
        ("axes", "0010_accessattemptexpiration"),
        ("valour", "0003_alter_material_file"),
    ]

    operations = [
        migrations.RunPython(enable_rls, reverse_code=disable_rls),
    ]

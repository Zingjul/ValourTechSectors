"""Database probes shared by startup and the readiness endpoint."""

from django.apps import apps


def probe_schema(connection):
    """Resolve managed tables and columns in one query, without reading any rows.

    A successful SELECT 1 proves connectivity, not that migrations ran. The
    database resolves these names even with a constant-false WHERE clause, so a
    missing table/column raises DatabaseError without fetching learner details,
    password hashes, invitation tokens, or course content.
    """
    quote = connection.ops.quote_name
    tables = []
    columns = []
    for index, model in enumerate(apps.get_models(include_auto_created=True)):
        if not model._meta.can_migrate(connection):
            continue
        alias = quote(f"probe_{index}")
        tables.append(f"{quote(model._meta.db_table)} AS {alias}")
        columns.extend(f"{alias}.{quote(field.column)}" for field in model._meta.local_concrete_fields)
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {', '.join(columns)} FROM {', '.join(tables)} WHERE 1 = 0")

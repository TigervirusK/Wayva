"""Explicit migrations use the same cwd-independent database path as the API."""

from alembic import context

from app import models  # noqa: F401 -- register model metadata
from app.config import Settings
from app.database import Base, Database, resolve_database_url

config = context.config
target_metadata = Base.metadata


def run_with_connection(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=resolve_database_url(Settings().database_url),
        target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        # Tests supply an isolated connection and never read the application's .env.
        run_with_connection(supplied_connection)
    else:
        database = Database(Settings().database_url)
        try:
            with database.engine.begin() as connection:
                run_with_connection(connection)
        finally:
            database.dispose()

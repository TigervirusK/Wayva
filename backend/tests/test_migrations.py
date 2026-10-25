from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from app.config import BACKEND_DIR
from app.database import Base, Database
from app import models  # noqa: F401 -- register metadata


def test_additive_migration_preserves_unrelated_records_and_is_repeatable(tmp_path):
    database = Database(f"sqlite:///{(tmp_path / 'migration.db').as_posix()}")
    try:
        with database.engine.begin() as connection:
            connection.execute(text("CREATE TABLE existing_records (id INTEGER PRIMARY KEY, label TEXT NOT NULL)"))
            connection.execute(text("INSERT INTO existing_records (id, label) VALUES (1, 'keep me')"))
            migration = Config(str(BACKEND_DIR / "alembic.ini"))
            migration.attributes["connection"] = connection
            command.upgrade(migration, "head")
            command.upgrade(migration, "head")
            assert connection.execute(text("SELECT label FROM existing_records WHERE id=1")).scalar_one() == "keep me"
            assert set(inspect(connection).get_table_names()) == {
                "existing_records", "alembic_version", "users", "trips", "itinerary_items", "proposals",
                "reservations", "reservation_dependencies", "disruption_events", "recovery_plans", "rescue_audit_logs",
                "traveler_vaults", "traveler_vault_audit",
                "accounts", "account_sessions", "account_attempts", "account_audit",
            }
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0005_accounts"
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    finally:
        database.dispose()


def test_migrated_schema_matches_sqlalchemy_models(tmp_path):
    database = Database(f"sqlite:///{(tmp_path / 'schema.db').as_posix()}")
    try:
        with database.engine.begin() as connection:
            migration = Config(str(BACKEND_DIR / "alembic.ini"))
            migration.attributes["connection"] = connection
            command.upgrade(migration, "head")
            context = MigrationContext.configure(connection)
            assert compare_metadata(context, Base.metadata) == []
    finally:
        database.dispose()


def test_rescue_migration_preserves_existing_profile_trip_activity_and_proposal(tmp_path):
    database = Database(f"sqlite:///{(tmp_path / 'rescue-upgrade.db').as_posix()}")
    try:
        with database.engine.begin() as connection:
            migration = Config(str(BACKEND_DIR / "alembic.ini"))
            migration.attributes["connection"] = connection
            command.upgrade(migration, "0002_itinerary_proposals")
            connection.execute(text("INSERT INTO users (id, display_name, token_hash) VALUES ('user', 'Keep Alex', 'private-hash')"))
            connection.execute(text("INSERT INTO trips (id, owner_id, name, destination, start_date, end_date, travelers, budget, currency) VALUES ('trip', 'user', 'Keep Japan', 'Tokyo', '2027-05-01', '2027-05-05', 2, 1200, 'USD')"))
            connection.execute(text("INSERT INTO itinerary_items (id, trip_id, date, start_time, end_time, title, estimated_cost, item_type) VALUES ('item', 'trip', '2027-05-02', '10:00', '11:00', 'Keep walk', 12, 'activity')"))
            connection.execute(text("INSERT INTO proposals (id, trip_id, request, payload, base_fingerprint, status, mode, created_at) VALUES ('proposal', 'trip', 'Keep draft', '{}', 'fingerprint', 'pending', 'demo', CURRENT_TIMESTAMP)"))
            original = {table: connection.exec_driver_sql(f"SELECT * FROM {table}").fetchall() for table in ("users", "trips", "itinerary_items", "proposals")}
            command.upgrade(migration, "head")
            command.upgrade(migration, "head")
            assert {table: connection.exec_driver_sql(f"SELECT * FROM {table}").fetchall() for table in original} == original
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM reservations").scalar_one() == 0
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    finally:
        database.dispose()

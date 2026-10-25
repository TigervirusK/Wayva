import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.config import BACKEND_DIR
from app.database import Database, resolve_database_url


def test_relative_database_path_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    resolved = resolve_database_url("sqlite:///./data/triprescue.db")

    assert resolved.database == str((BACKEND_DIR / "data" / "triprescue.db").resolve())


def test_sqlite_data_persists_across_database_instances(tmp_path):
    url = f"sqlite:///{(tmp_path / 'persistence.db').as_posix()}"
    first_database = Database(url)
    try:
        with first_database.session_factory() as session:
            session.execute(text("CREATE TABLE foundation_probe (value TEXT NOT NULL)"))
            session.execute(text("INSERT INTO foundation_probe (value) VALUES (:value)"), {"value": "saved"})
            session.commit()
    finally:
        first_database.dispose()

    reopened_database = Database(url)
    try:
        with reopened_database.session_factory() as session:
            assert session.execute(text("SELECT value FROM foundation_probe")).scalar_one() == "saved"
    finally:
        reopened_database.dispose()


def test_sqlite_enforces_foreign_keys(tmp_path):
    database = Database(f"sqlite:///{(tmp_path / 'relationships.db').as_posix()}")
    try:
        with database.session_factory() as session:
            session.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
            session.execute(text("CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))"))
            session.commit()
            with pytest.raises(IntegrityError):
                session.execute(text("INSERT INTO child (parent_id) VALUES (999)"))
            session.rollback()
    finally:
        database.dispose()

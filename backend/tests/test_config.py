import pytest
from pydantic import ValidationError

from app.config import Settings


def test_environment_variables_override_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:9000"]')

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///:memory:"
    assert settings.cors_origins == ["http://localhost:9000"]


def test_wildcard_origins_are_rejected():
    with pytest.raises(ValidationError, match="explicit HTTP"):
        Settings(_env_file=None, cors_origins=["*"])


def test_non_sqlite_database_is_rejected():
    with pytest.raises(ValidationError, match="SQLite"):
        Settings(_env_file=None, database_url="postgresql://localhost/triprescue")

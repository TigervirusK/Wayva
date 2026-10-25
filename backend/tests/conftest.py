import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.config import BACKEND_DIR, Settings
from app.database import Database
from app.main import create_app


@pytest.fixture
def application(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'isolated.db').as_posix()}",
        cors_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        ai_mode="demo",
        openai_api_key=None,
    )
    database = Database(settings.database_url)
    try:
        with database.engine.begin() as connection:
            migration = Config(str(BACKEND_DIR / "alembic.ini"))
            migration.attributes["connection"] = connection
            command.upgrade(migration, "head")
    finally:
        database.dispose()
    return create_app(settings)


@pytest.fixture
def client(application):
    with TestClient(application) as test_client:
        yield test_client

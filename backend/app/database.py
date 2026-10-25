"""SQLAlchemy foundation without creating or resetting application tables."""

from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import BACKEND_DIR


class Base(DeclarativeBase):
    """Future application models will share this metadata."""


def resolve_database_url(database_url: str) -> URL:
    """Resolve relative database paths from backend/, not the terminal directory."""
    url = make_url(database_url)
    if url.database and url.database != ":memory:":
        database_path = Path(url.database).expanduser()
        if not database_path.is_absolute():
            database_path = BACKEND_DIR / database_path
        url = url.set(database=str(database_path.resolve()))
    return url


def configure_sqlite(connection, _connection_record) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


class Database:
    def __init__(self, database_url: str) -> None:
        url = resolve_database_url(database_url)
        if url.database and url.database != ":memory:":
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)

        engine_options = {"poolclass": StaticPool} if url.database == ":memory:" else {}
        self.engine: Engine = create_engine(
            url,
            connect_args={"check_same_thread": False, "timeout": 5},
            pool_pre_ping=True,
            **engine_options,
        )
        event.listen(self.engine, "connect", configure_sqlite)
        self.session_factory = sessionmaker(
            bind=self.engine, class_=Session, expire_on_commit=False
        )

    def dispose(self) -> None:
        self.engine.dispose()


def get_db(request: Request) -> Iterator[Session]:
    """One session per request; callers explicitly commit approved mutations."""
    with request.app.state.database.session_factory() as session:
        yield session

"""Validated server configuration. Environment files never belong in Git."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/triprescue.db"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    ai_mode: Literal["demo", "openai", "ollama"] = "demo"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.4-mini"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b-q4_K_M"
    ollama_context_length: int = 8192
    auth_cookie_secure: bool = False  # Enable with HTTPS before any public hosting.

    @field_validator("openai_model", "ollama_model")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 120 or any(character.isspace() for character in value):
            raise ValueError("The AI model must be a nonempty model identifier.")
        return value

    @field_validator("ollama_model")
    @classmethod
    def validate_local_model(cls, value: str) -> str:
        if value.casefold().endswith(("-cloud", ":cloud")):
            raise ValueError("Choose a local Ollama model, not a cloud model.")
        return value

    @field_validator("ollama_context_length")
    @classmethod
    def validate_context_length(cls, value: int) -> int:
        if not 2048 <= value <= 32768:
            raise ValueError("OLLAMA_CONTEXT_LENGTH must be between 2048 and 32768.")
        return value

    @field_validator("ollama_base_url")
    @classmethod
    def validate_local_url(cls, value: str) -> str:
        try:
            parsed = urlsplit(value.strip())
            port = parsed.port
        except ValueError:
            raise ValueError("OLLAMA_BASE_URL must be a loopback HTTP address.") from None
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
                or (port is not None and not 1 <= port <= 65535)):
            raise ValueError("OLLAMA_BASE_URL must be a loopback HTTP address without credentials or a path.")
        return value.strip().rstrip("/")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        try:
            url = make_url(value)
        except Exception as exc:
            raise ValueError("DATABASE_URL must be a valid SQLite URL.") from exc
        if url.drivername not in {"sqlite", "sqlite+pysqlite"}:
            raise ValueError("Phase 1 supports SQLite databases only.")
        if not url.database or url.database.startswith("file:") or url.query:
            raise ValueError("Use a SQLite file path or :memory: without URL options.")
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, values: list[str]) -> list[str]:
        origins = []
        for value in values:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.hostname is None
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or "*" in value
            ):
                raise ValueError("CORS_ORIGINS must contain explicit HTTP(S) origins.")
            origins.append(value.rstrip("/"))
        return origins

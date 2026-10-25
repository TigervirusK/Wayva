from unittest.mock import Mock

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import get_db


def test_health_checks_database_and_returns_expected_contract(client, application):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "triprescue-api",
        "database": "connected",
        "version": "0.1.0",
    }
    assert application.state.database.engine.url.database.endswith("isolated.db")


def test_database_failure_returns_503_without_exposing_details(client, application, caplog):
    broken_session = Mock(spec=Session)
    broken_session.execute.side_effect = OperationalError(
        "SELECT secret_column", {}, Exception("private-database-password")
    )

    def unavailable_database():
        yield broken_session

    application.dependency_overrides[get_db] = unavailable_database
    try:
        response = client.get("/api/health")
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Database unavailable. Check the backend configuration."
    }
    assert "private-database-password" not in response.text + caplog.text
    assert "secret_column" not in response.text + caplog.text


def test_openapi_exposes_health_contract(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/health" in response.json()["paths"]
    assert client.get("/docs").status_code == 200


def test_cors_allows_configured_frontend(client):
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_does_not_allow_unknown_origins(client):
    response = client.options(
        "/api/health",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers

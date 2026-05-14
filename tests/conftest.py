"""Fixtures compartidas para todos los tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_data_files(tmp_path, monkeypatch):
    """Redirige los archivos JSON de datos a un directorio temporal para aislar cada test."""
    import app.routers.auth as auth_mod
    import app.routers.newsletter as nl_mod

    monkeypatch.setattr(auth_mod, "_USERS_F",   tmp_path / "users.json")
    monkeypatch.setattr(auth_mod, "_SESSION_F", tmp_path / "sessions.json")
    monkeypatch.setattr(nl_mod,   "_DATA_FILE", tmp_path / "newsletter.json")

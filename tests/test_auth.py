"""Tests del flujo de autenticación."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_register_ok(client: TestClient):
    r = client.post("/auth/register", json={"email": "test@example.com", "password": "securepass"})
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert data["email"] == "test@example.com"


def test_register_duplicate(client: TestClient):
    payload = {"email": "dup@example.com", "password": "securepass"}
    client.post("/auth/register", json=payload)
    r = client.post("/auth/register", json=payload)
    assert r.status_code == 409


def test_register_short_password(client: TestClient):
    r = client.post("/auth/register", json={"email": "short@example.com", "password": "abc"})
    assert r.status_code == 422


def test_login_ok(client: TestClient):
    client.post("/auth/register", json={"email": "login@example.com", "password": "securepass"})
    r = client.post("/auth/login", json={"email": "login@example.com", "password": "securepass"})
    assert r.status_code == 200
    assert "token" in r.json()


def test_login_wrong_password(client: TestClient):
    client.post("/auth/register", json={"email": "wrong@example.com", "password": "securepass"})
    r = client.post("/auth/login", json={"email": "wrong@example.com", "password": "wrongpass"})
    assert r.status_code == 401


def test_login_nonexistent(client: TestClient):
    r = client.post("/auth/login", json={"email": "nobody@example.com", "password": "securepass"})
    assert r.status_code == 401


def test_me_with_valid_token(client: TestClient):
    reg = client.post("/auth/register", json={"email": "me@example.com", "password": "securepass"})
    token = reg.json()["token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "me@example.com"


def test_me_no_token(client: TestClient):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_logout(client: TestClient):
    reg = client.post("/auth/register", json={"email": "bye@example.com", "password": "securepass"})
    token = reg.json()["token"]
    r = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    # Después de logout, /me debe fallar
    r2 = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 401

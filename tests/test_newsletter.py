"""Tests del endpoint de newsletter."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_subscribe_ok(client: TestClient):
    r = client.post("/v1/newsletter/subscribe", json={"email": "sub@example.com", "lang": "es"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_subscribe_duplicate_same_response(client: TestClient):
    payload = {"email": "dup@example.com", "lang": "es"}
    r1 = client.post("/v1/newsletter/subscribe", json=payload)
    r2 = client.post("/v1/newsletter/subscribe", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["ok"] is True
    assert r2.json()["ok"] is True


def test_subscribe_invalid_email(client: TestClient):
    r = client.post("/v1/newsletter/subscribe", json={"email": "not-an-email", "lang": "es"})
    assert r.status_code == 422


def test_subscribe_en_lang(client: TestClient):
    r = client.post("/v1/newsletter/subscribe", json={"email": "en@example.com", "lang": "en"})
    assert r.status_code == 200


def test_subscriber_count(client: TestClient):
    client.post("/v1/newsletter/subscribe", json={"email": "a@example.com", "lang": "es"})
    client.post("/v1/newsletter/subscribe", json={"email": "b@example.com", "lang": "es"})
    r = client.get("/v1/newsletter/count")
    assert r.status_code == 200
    assert r.json()["total"] >= 2

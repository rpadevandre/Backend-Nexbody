"""Tests del módulo de pagos (sin Stripe real — verifica comportamiento sin keys)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient) -> dict:
    """Registra un usuario y devuelve headers con token."""
    r = client.post("/auth/register", json={"email": "pay@example.com", "password": "securepass"})
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_subscription_status_no_auth(client: TestClient):
    r = client.get("/v1/payments/subscription")
    assert r.status_code == 401


def test_subscription_status_authenticated(client: TestClient):
    headers = _auth_headers(client)
    r = client.get("/v1/payments/subscription", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] == "free"
    assert "stripe_configured" in data
    # Sin key configurada, stripe_configured debe ser False
    assert data["stripe_configured"] is False


def test_create_checkout_no_stripe(client: TestClient):
    """Sin STRIPE_SECRET_KEY debe retornar 503."""
    headers = _auth_headers(client)
    r = client.post("/v1/payments/create-checkout", json={"plan": "monthly"}, headers=headers)
    assert r.status_code == 503
    assert "no configurado" in r.json()["detail"].lower() or "not configured" in r.json()["detail"].lower()


def test_create_checkout_invalid_plan(client: TestClient):
    """Plan inválido sin Stripe configurado retorna 503 primero."""
    headers = _auth_headers(client)
    r = client.post("/v1/payments/create-checkout", json={"plan": "enterprise"}, headers=headers)
    # Sin Stripe, el 503 se dispara antes de validar el plan
    assert r.status_code in (400, 503)


def test_create_checkout_no_auth(client: TestClient):
    r = client.post("/v1/payments/create-checkout", json={"plan": "monthly"})
    assert r.status_code == 401


def test_portal_no_stripe(client: TestClient):
    headers = _auth_headers(client)
    r = client.post("/v1/payments/portal", headers=headers)
    assert r.status_code == 503


def test_portal_no_auth(client: TestClient):
    r = client.post("/v1/payments/portal")
    assert r.status_code == 401


def test_webhook_no_stripe(client: TestClient):
    """Sin Stripe configurado el webhook retorna 503."""
    r = client.post("/v1/payments/webhook", content=b"{}",
                    headers={"stripe-signature": "fake", "content-type": "application/json"})
    assert r.status_code == 503

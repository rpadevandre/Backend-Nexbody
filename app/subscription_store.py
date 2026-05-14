"""Persistencia de suscripciones en JSON local (reemplazar por MongoDB en producción)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

_DATA = Path(__file__).parent / "data"
_SUBS_F = _DATA / "subscriptions.json"


def _load() -> dict:
    _DATA.mkdir(parents=True, exist_ok=True)
    if _SUBS_F.exists():
        try:
            return json.loads(_SUBS_F.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _dump(data: dict) -> None:
    _DATA.mkdir(parents=True, exist_ok=True)
    _SUBS_F.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_subscription(email: str) -> dict:
    return _load().get(email, {
        "status": "free",
        "plan": None,
        "stripe_customer_id": None,
        "current_period_end": None,
        "cancel_at_period_end": False,
    })


def upsert_subscription(email: str, data: dict) -> None:
    subs = _load()
    existing = subs.get(email, {})
    existing.update(data)
    existing["updated_at"] = datetime.now(UTC).isoformat()
    subs[email] = existing
    _dump(subs)


def set_customer_id(email: str, customer_id: str) -> None:
    subs = _load()
    entry = subs.get(email, {})
    entry["stripe_customer_id"] = customer_id
    entry["updated_at"] = datetime.now(UTC).isoformat()
    subs[email] = entry
    _dump(subs)


def get_customer_id(email: str) -> str | None:
    return _load().get(email, {}).get("stripe_customer_id")

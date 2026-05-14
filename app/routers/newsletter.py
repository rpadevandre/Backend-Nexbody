"""Newsletter: guarda suscriptores en JSON local y en MongoDB si esta disponible."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.security.logging_cfg import get_logger
from app.security.sanitize import sanitize_str
from app.email_service import send_newsletter_confirm

limiter = Limiter(key_func=get_remote_address)
log     = get_logger("newsletter")
router  = APIRouter(prefix="/v1/newsletter", tags=["newsletter"])

_DATA_FILE = Path(__file__).parent.parent / "data" / "newsletter_subscribers.json"
_EMAIL_RE  = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


class SubscribeRequest(BaseModel):
    email: str
    lang:  str = "es"

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = sanitize_str(v.strip().lower(), "email")[:254]
        if not _EMAIL_RE.match(v):
            raise ValueError("Email invalido")
        return v

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, v: str) -> str:
        return v if v in ("es", "en") else "es"


def _load() -> list[dict]:
    if _DATA_FILE.exists():
        try:
            return json.loads(_DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save(subscribers: list[dict]) -> None:
    _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DATA_FILE.write_text(json.dumps(subscribers, ensure_ascii=False, indent=2), encoding="utf-8")


@router.post("/subscribe")
@limiter.limit("3/minute")
async def subscribe(request: Request, body: SubscribeRequest):
    subscribers = _load()
    emails = [s["email"] for s in subscribers]

    if body.email in emails:
        # Respuesta identica para no revelar si ya existe
        return {"ok": True, "message": "Suscripcion registrada."}

    subscribers.append({
        "email":      body.email,
        "lang":       body.lang,
        "subscribed_at": datetime.now(UTC).isoformat(),
        "source":     "website",
    })
    _save(subscribers)
    log.info("newsletter.subscribed", email=body.email[:4] + "***", lang=body.lang)
    send_newsletter_confirm(body.email)
    return {"ok": True, "message": "Suscripcion registrada."}


@router.get("/count")
@limiter.limit("10/minute")
async def count(request: Request):
    """Retorna el total de suscriptores (sin emails)."""
    return {"total": len(_load())}

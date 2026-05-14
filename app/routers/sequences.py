"""Endpoints para disparar email sequences desde el panel de admin."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.email_service import send_churn_recovery, send_day7_reminder
from app.security.logging_cfg import get_logger, mask_email

limiter = Limiter(key_func=get_remote_address)
log     = get_logger("sequences")
router  = APIRouter(prefix="/v1/sequences", tags=["sequences"])

_DATA     = Path(__file__).parent.parent / "data"
_USERS_F  = _DATA / "users.json"


def _load_users() -> dict:
    if _USERS_F.exists():
        try:
            return json.loads(_USERS_F.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


class TriggerRequest(BaseModel):
    type: str   # "day7" | "churn"
    dry_run: bool = True   # True = solo cuenta, no envia


@router.post("/trigger")
@limiter.limit("5/minute")
async def trigger_sequence(request: Request, body: TriggerRequest):
    """Dispara una secuencia de emails a los usuarios elegibles.
    dry_run=True (defecto) solo cuenta sin enviar.
    """
    users     = _load_users()
    now       = datetime.now(UTC)
    sent      = 0
    eligible  = 0

    for email, data in users.items():
        created_str = data.get("created_at", "")
        if not created_str:
            continue
        try:
            created = datetime.fromisoformat(created_str)
        except ValueError:
            continue

        if body.type == "day7":
            days_since = (now - created).days
            if 7 <= days_since <= 8:
                eligible += 1
                if not body.dry_run:
                    send_day7_reminder(email)
                    sent += 1

        elif body.type == "churn":
            # Usuarios sin login en 5+ días (aproximado por created_at sin tabla de logins)
            days_since = (now - created).days
            if days_since >= 5:
                eligible += 1
                if not body.dry_run:
                    send_churn_recovery(email, days_since)
                    sent += 1

        else:
            raise HTTPException(status_code=400, detail=f"Tipo desconocido: {body.type}")

    log.info("sequences.triggered", type=body.type, eligible=eligible, sent=sent, dry_run=body.dry_run)
    return {
        "type":     body.type,
        "eligible": eligible,
        "sent":     sent,
        "dry_run":  body.dry_run,
        "message":  f"{'Simulado' if body.dry_run else 'Enviado'}: {eligible} usuarios elegibles, {sent} emails enviados.",
    }


@router.get("/stats")
@limiter.limit("20/minute")
async def sequence_stats(request: Request):
    """Estadísticas de usuarios para sequences (sin enviar nada)."""
    users = _load_users()
    now   = datetime.now(UTC)
    total = len(users)
    day7  = 0
    churn = 0

    for data in users.values():
        created_str = data.get("created_at", "")
        if not created_str:
            continue
        try:
            created = datetime.fromisoformat(created_str)
        except ValueError:
            continue
        days = (now - created).days
        if 7 <= days <= 8:
            day7 += 1
        if days >= 5:
            churn += 1

    return {
        "total_users":         total,
        "eligible_day7":       day7,
        "eligible_churn":      churn,
        "as_of":               now.isoformat(),
    }

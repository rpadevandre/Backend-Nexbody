"""Checkins diarios, log de peso y NPS."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.ai_adapt_engine import adapt_plan, generate_explanation
from app.forma_models import CheckinStatus, WeightEntry
from app.forma_store import load_state, save_full
from app.routers.auth import _token_from_request, _validate_session
from app.security.logging_cfg import get_logger

limiter = Limiter(key_func=get_remote_address)
log     = get_logger("tracking")
router  = APIRouter(prefix="/v1/forma", tags=["tracking"])

_DATA   = Path(__file__).parent.parent / "data"
_NPS_F  = _DATA / "nps.json"


def _auth(request: Request) -> str:
    try:
        return _validate_session(_token_from_request(request))
    except HTTPException:
        return "anon"   # demo sin auth también funciona


# ── Checkin ───────────────────────────────────────────────────────────────────

class CheckinRequest(BaseModel):
    workout_done:      bool | None = None
    skipped_exercises: list[str]   = []
    meals_done:        list[bool]  = []
    skipped_meals:     list[str]   = []


@router.post("/checkin")
@limiter.limit("30/minute")
async def save_checkin(request: Request, body: CheckinRequest):
    """Marca el estado del día (hecho / salteado). Si hay algo salteado, adapta mañana."""
    state = load_state()
    if state.daily_plan is None:
        raise HTTPException(status_code=400, detail="No hay plan activo.")

    checkin = CheckinStatus(
        workout_done=body.workout_done,
        skipped_exercises=body.skipped_exercises,
        meals_done=body.meals_done,
        skipped_meals=body.skipped_meals,
    )
    state.daily_plan.checkin = checkin

    # Si salteo algo y no se adaptó aún → pedir adaptación a IA
    has_skip = (
        body.workout_done is False
        or bool(body.skipped_exercises)
        or bool(body.skipped_meals)
    )
    adaptation = None
    if has_skip and not checkin.adapted:
        adaptation = adapt_plan(state.profile, state.daily_plan, checkin)
        if adaptation:
            state.daily_plan.checkin.adapted = True

    save_full(state)
    log.info("checkin.saved", workout_done=body.workout_done)
    return {
        "ok":        True,
        "checkin":   state.daily_plan.checkin.model_dump(),
        "adaptation": adaptation,
    }


@router.get("/checkin")
@limiter.limit("60/minute")
async def get_checkin(request: Request):
    """Estado del checkin de hoy."""
    state = load_state()
    if state.daily_plan is None:
        return {"checkin": None}
    return {"checkin": state.daily_plan.checkin.model_dump()}


# ── Explicación del plan ──────────────────────────────────────────────────────

@router.get("/plan/explanation")
@limiter.limit("10/minute")
async def get_plan_explanation(request: Request):
    """Genera (o recupera del cache) la explicación del plan actual."""
    state = load_state()
    if state.daily_plan is None:
        raise HTTPException(status_code=400, detail="No hay plan activo.")

    if not state.daily_plan.explanation:
        state.daily_plan.explanation = generate_explanation(state.profile, state.daily_plan)
        save_full(state)

    return {"explanation": state.daily_plan.explanation}


# ── Log de peso ───────────────────────────────────────────────────────────────

class WeightRequest(BaseModel):
    kg: float

    @field_validator("kg")
    @classmethod
    def validate_kg(cls, v: float) -> float:
        if v < 20 or v > 400:
            raise ValueError("Peso fuera de rango.")
        return round(v, 1)


@router.post("/logs/weight")
@limiter.limit("10/minute")
async def log_weight(request: Request, body: WeightRequest):
    """Agrega una entrada de peso para hoy (reemplaza si ya existe)."""
    state   = load_state()
    today   = datetime.now(UTC).date().isoformat()
    entries = [e for e in state.weight_log if e.date != today]
    entries.append(WeightEntry(date=today, kg=body.kg))
    # Mantener últimas 90 entradas
    state.weight_log = sorted(entries, key=lambda e: e.date)[-90:]
    save_full(state)
    log.info("weight.logged", kg=body.kg)
    return {"ok": True, "entry": {"date": today, "kg": body.kg}}


@router.get("/logs/weight")
@limiter.limit("60/minute")
async def get_weight_log(request: Request):
    """Historial de peso (últimas 90 entradas)."""
    state = load_state()
    return {"entries": [e.model_dump() for e in state.weight_log]}


# ── NPS ───────────────────────────────────────────────────────────────────────

def _load_nps() -> list:
    _DATA.mkdir(parents=True, exist_ok=True)
    if _NPS_F.exists():
        try:
            return json.loads(_NPS_F.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_nps(data: list) -> None:
    _DATA.mkdir(parents=True, exist_ok=True)
    _NPS_F.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class NpsRequest(BaseModel):
    score:   int
    comment: str = ""

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: int) -> int:
        if v < 0 or v > 10:
            raise ValueError("Score debe ser 0–10.")
        return v


@router.post("/nps")
@limiter.limit("2/day")
async def submit_nps(request: Request, body: NpsRequest):
    """Guarda la respuesta de NPS del usuario."""
    email = _auth(request)
    entries = _load_nps()
    entries.append({
        "email":     email,
        "score":     body.score,
        "comment":   body.comment,
        "submitted_at": datetime.now(UTC).isoformat(),
    })
    _save_nps(entries)
    log.info("nps.submitted", score=body.score)
    return {"ok": True, "score": body.score}


@router.get("/nps/eligible")
@limiter.limit("30/minute")
async def nps_eligible(request: Request):
    """Chequea si el usuario puede responder el NPS (30+ días desde registro)."""
    from app.routers.auth import _load as _load_users, _USERS_F
    email = _auth(request)
    if email == "anon":
        return {"eligible": False}

    users = _load_users(_USERS_F)
    user  = users.get(email, {})
    created_str = user.get("created_at", "")
    if not created_str:
        return {"eligible": False}

    try:
        created = datetime.fromisoformat(created_str)
        days    = (datetime.now(UTC) - created).days
    except ValueError:
        return {"eligible": False}

    # Ya respondió?
    already = any(e.get("email") == email for e in _load_nps())
    return {"eligible": days >= 30 and not already, "days_since_register": days}

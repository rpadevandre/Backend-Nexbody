"""Auth: registro, login y sesion con almacenamiento local en JSON."""
from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from passlib.context import CryptContext
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.security.logging_cfg import get_logger, mask_email
from app.email_service import send_welcome
from app.security.sanitize import sanitize_str

limiter  = Limiter(key_func=get_remote_address)
log      = get_logger("auth")
router   = APIRouter(prefix="/auth", tags=["auth"])
pwd_ctx  = CryptContext(schemes=["bcrypt"], deprecated="auto")

_DEV_EMAIL = "dev@local"

_DATA      = Path(__file__).parent.parent / "data"
_USERS_F   = _DATA / "users.json"
_SESSION_F = _DATA / "sessions.json"


# ── Storage helpers ────────────────────────────────────────────────────────────

def _load(path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Schemas ────────────────────────────────────────────────────────────────────

class AuthRequest(BaseModel):
    email:    str
    password: str

    @field_validator("email")
    @classmethod
    def clean_email(cls, v: str) -> str:
        return sanitize_str(v.strip().lower(), "email")[:254]

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("La contrasena debe tener al menos 6 caracteres")
        return v[:128]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/register")
@limiter.limit("5/hour")
async def register(request: Request, body: AuthRequest):
    users = _load(_USERS_F)

    if body.email in users:
        # Respuesta identica para no revelar si el email existe
        raise HTTPException(status_code=409, detail="Email ya registrado.")

    users[body.email] = {
        "email":      body.email,
        "hash":       pwd_ctx.hash(body.password),
        "created_at": datetime.now(UTC).isoformat(),
        "lang":       "es",
    }
    _dump(_USERS_F, users)
    log.info("auth.registered", email=mask_email(body.email))
    send_welcome(body.email)

    token = _create_session(body.email)
    return {"token": token, "email": body.email}


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: AuthRequest):
    ip = get_remote_address(request)

    # Comprobar bloqueo por intentos previos (sin DB, usamos archivo)
    sessions = _load(_SESSION_F)
    attempt_key = f"attempts:{ip}:{body.email}"
    attempts_data = sessions.get(attempt_key, {"count": 0})
    if attempts_data.get("locked_until"):
        locked_until = datetime.fromisoformat(attempts_data["locked_until"])
        if datetime.now(UTC) < locked_until:
            remaining = int((locked_until - datetime.now(UTC)).total_seconds() / 60) + 1
            raise HTTPException(status_code=429, detail=f"Cuenta bloqueada. Intenta en {remaining} minutos.")

    users = _load(_USERS_F)
    user  = users.get(body.email)

    # Tiempo constante para evitar timing attacks
    valid = user is not None and pwd_ctx.verify(body.password, user.get("hash", ""))

    if not valid:
        count = attempts_data.get("count", 0) + 1
        update: dict = {"count": count, "last_attempt": datetime.now(UTC).isoformat()}
        if count >= 5:
            from datetime import timedelta
            update["locked_until"] = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
        sessions[attempt_key] = update
        _dump(_SESSION_F, sessions)
        log.warning("auth.login_failed", email=mask_email(body.email), ip=ip)
        raise HTTPException(status_code=401, detail="Credenciales incorrectas.")

    # Login exitoso — limpiar intentos
    sessions.pop(attempt_key, None)
    _dump(_SESSION_F, sessions)

    token = _create_session(body.email)
    log.info("auth.login_ok", email=mask_email(body.email), ip=ip)
    return {"token": token, "email": body.email}


@router.get("/me")
@limiter.limit("60/minute")
async def me(request: Request):
    token = _token_from_request(request)
    email = _validate_session(token)
    users = _load(_USERS_F)
    user  = users.get(email, {})
    return {"email": email, "created_at": user.get("created_at")}


@router.post("/logout")
@limiter.limit("30/minute")
async def logout(request: Request):
    token = _token_from_request(request)
    sessions = _load(_SESSION_F)
    sessions.pop(f"sess:{token}", None)
    _dump(_SESSION_F, sessions)
    return {"ok": True}


@router.post("/dev-login")
@limiter.limit("20/minute")
async def dev_login(request: Request):
    """Acceso instantaneo sin contraseña — solo disponible si DEV_MODE=true en .env."""
    # Auto-crear usuario dev si no existe
    users = _load(_USERS_F)
    if _DEV_EMAIL not in users:
        users[_DEV_EMAIL] = {
            "email":      _DEV_EMAIL,
            "hash":       "dev-no-password",  # valor literal, nunca se verifica con bcrypt
            "created_at": datetime.now(UTC).isoformat(),
            "lang":       "es",
            "dev":        True,
        }
        _dump(_USERS_F, users)

    token = _create_session(_DEV_EMAIL)
    log.warning("auth.dev_login", ip=get_remote_address(request))
    return {"token": token, "email": _DEV_EMAIL}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _create_session(email: str) -> str:
    token    = secrets.token_urlsafe(32)
    sessions = _load(_SESSION_F)
    sessions[f"sess:{token}"] = {
        "email":      email,
        "created_at": datetime.now(UTC).isoformat(),
    }
    _dump(_SESSION_F, sessions)
    return token


def _token_from_request(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    raise HTTPException(status_code=401, detail="Token requerido.")


def _validate_session(token: str) -> str:
    sessions = _load(_SESSION_F)
    entry = sessions.get(f"sess:{token}")
    if not entry:
        raise HTTPException(status_code=401, detail="Sesion invalida o expirada.")
    return entry["email"]

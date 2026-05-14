"""API local para OUTPUT: datos reales desde MongoDB del monorepo (mismo esquema que `masaas`)."""
from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import Settings, get_settings
from app.db import close_mongo, connect_mongo, get_db, mongo_ping
from app.routers.auth import router as auth_router
from app.routers.forma import router as forma_router
from app.routers.newsletter import router as newsletter_router
from app.routers.payments import router as payments_router
from app.routers.sequences import router as sequences_router
from app.routers.tracking import router as tracking_router
from app.security.brute_force import ensure_ttl_index
from app.security.headers import SecurityHeadersMiddleware
from app.security.logging_cfg import configure_logging, get_logger
from app.stats_service import compute_platform_overview, latest_execution_summary, recent_executions

# ── Logging ──────────────────────────────────────────────────────────────────
configure_logging()
log = get_logger()

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    try:
        await connect_mongo(settings)
        app.state.mongo_connected = True
        await ensure_ttl_index(get_db())
        log.info("startup.ok", mongo=True)
    except Exception as exc:
        app.state.mongo_connected = False
        log.warning("startup.no_mongo", error=str(exc))
    yield
    await close_mongo()
    log.info("shutdown.ok")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="FormaRuta API",
    version="0.3.0",
    docs_url="/docs",
    redoc_url=None,           # Deshabilitar redoc en produccion
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Adjuntar limiter al estado de la app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Middlewares (orden importa: de afuera hacia adentro) ──────────────────────

# 1. Security headers — siempre primero
app.add_middleware(SecurityHeadersMiddleware)

# 2. CORS — solo origenes autorizados
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    max_age=86400,
)

# ── Request logging middleware ────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    # No loguear health checks para no saturar los logs
    if request.url.path not in ("/health",):
        log.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ip=get_remote_address(request),
        )
    return response


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(forma_router)
app.include_router(newsletter_router)
app.include_router(payments_router)
app.include_router(sequences_router)
app.include_router(tracking_router)


# ── Dependency ────────────────────────────────────────────────────────────────
async def require_db(request: Request):
    if not getattr(request.app.state, "mongo_connected", False):
        raise HTTPException(
            status_code=503,
            detail="MongoDB no disponible. Ejecuta `docker-compose up -d` y revisa MONGO_URI en `.env`.",
        )
    return get_db()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
@limiter.limit("120/minute")
async def health(request: Request):
    ok = await mongo_ping()
    return {
        "status": "ok" if ok else "degraded",
        "service": "forma-ruta-api",
        "mongo": ok,
    }


@app.get("/v1/integrations/status")
@limiter.limit("30/minute")
async def integrations_status(request: Request, settings: Settings = Depends(get_settings)):
    """Estado de APIs configuradas en `.env` (sin exponer secretos)."""
    out: dict = {
        "mongo_uri_configured": bool(settings.mongo_uri),
        "mongo_reachable": await mongo_ping(),
        "anthropic_configured": bool(settings.anthropic_api_key.strip()),
        "tavily_configured": bool(settings.tavily_api_key.strip()),
        "ollama_host": settings.ollama_host,
        "ollama_reachable": False,
    }
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{settings.ollama_host.rstrip('/')}/api/tags")
            out["ollama_reachable"] = r.status_code == 200
    except Exception:
        pass
    return out


@app.get("/v1/metrics/overview")
@limiter.limit("30/minute")
async def metrics_overview(request: Request, db=Depends(require_db)):
    return await compute_platform_overview(db)


@app.get("/v1/metrics/no_show")
@limiter.limit("30/minute")
async def metrics_no_show_legacy(request: Request, db=Depends(require_db)):
    overview = await compute_platform_overview(db)
    return {
        "range": overview["range"],
        "rate": 1.0 - overview["adherence_rate"],
        "series": [
            {"week": s["week"], "no_show_rate": 1.0 - s["adherence"]}
            for s in overview["series"]
        ],
        "appointments_total": overview["active_plans"],
        "confirmed": overview["workouts_logged"],
    }


@app.get("/v1/tenants/current")
@limiter.limit("60/minute")
async def tenants_current(request: Request):
    if not getattr(request.app.state, "mongo_connected", False):
        return {
            "id": "local", "name": "FormaRuta", "slug": "forma-ruta",
            "timezone": "UTC",
            "tagline": "Conecta MongoDB y define MONGO_URI en `.env` para ver datos reales.",
            "mongo_connected": False,
        }
    latest = await latest_execution_summary(get_db())
    if latest:
        gid = str(latest.get("execution_id", ""))[:8]
        return {
            "id": latest.get("execution_id", "unknown"),
            "name": "FormaRuta", "slug": "forma-ruta",
            "timezone": "America/Argentina/Buenos_Aires",
            "tagline": (latest.get("goal") or "")[:400],
            "execution_mode": latest.get("mode"),
            "workspace_path": latest.get("workspace_path"),
            "updated_at": latest.get("updated_at"),
            "execution_short_id": gid,
            "mongo_connected": True,
        }
    return {
        "id": "local", "name": "FormaRuta", "slug": "forma-ruta",
        "timezone": "UTC",
        "tagline": "Mongo vacio: ejecuta `masaas run --goal` para poblar ejecuciones.",
        "mongo_connected": True,
    }


@app.get("/v1/executions/recent")
@limiter.limit("30/minute")
async def executions_recent(request: Request, limit: int = 20, db=Depends(require_db)):
    safe_limit = max(1, min(limit, 50))
    return {"items": await recent_executions(db, limit=safe_limit)}

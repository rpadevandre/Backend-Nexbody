"""Pagos con Stripe: checkout, webhook, estado de suscripción y portal."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings
from app.routers.auth import _token_from_request, _validate_session
from app.security.logging_cfg import get_logger, mask_email
from app.subscription_store import (
    get_customer_id,
    get_subscription,
    set_customer_id,
    upsert_subscription,
)

limiter = Limiter(key_func=get_remote_address)
log     = get_logger("payments")
router  = APIRouter(prefix="/v1/payments", tags=["payments"])


def _stripe():
    """Retorna el módulo stripe configurado, o None si no hay key."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        return None
    try:
        import stripe as _s
        _s.api_key = settings.stripe_secret_key
        return _s
    except ImportError:
        return None


def _require_auth(request: Request) -> str:
    """Extrae y valida el token del header. Retorna el email del usuario."""
    token = _token_from_request(request)
    return _validate_session(token)


# ── Schemas ───────────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan: str  # "monthly" | "annual"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/create-checkout")
@limiter.limit("10/minute")
async def create_checkout(request: Request, body: CheckoutRequest):
    """Crea una Stripe Checkout Session y devuelve la URL de pago."""
    email = _require_auth(request)

    stripe = _stripe()
    if not stripe:
        raise HTTPException(
            status_code=503,
            detail="Stripe no configurado. Agregá STRIPE_SECRET_KEY al .env.",
        )

    settings  = get_settings()
    price_map = {"monthly": settings.stripe_price_monthly, "annual": settings.stripe_price_annual}
    price_id  = price_map.get(body.plan)

    if not price_id:
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{body.plan}' inválido o precio no configurado en .env.",
        )

    # Reusar customer_id si ya existe para que Stripe recuerde al usuario
    customer_id = get_customer_id(email)
    customer_args: dict = {}
    if customer_id:
        customer_args = {"customer": customer_id}
    else:
        customer_args = {"customer_email": email}

    base = settings.app_url.rstrip("/")
    session = stripe.checkout.Session.create(
        **customer_args,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{base}/pago/exito?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/pago/cancelado",
        metadata={"email": email, "plan": body.plan},
        allow_promotion_codes=True,
        billing_address_collection="auto",
    )

    log.info("payments.checkout_created", email=mask_email(email), plan=body.plan)
    return {"url": session.url, "session_id": session.id}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Recibe y procesa eventos de Stripe. Requiere STRIPE_WEBHOOK_SECRET."""
    stripe = _stripe()
    if not stripe:
        raise HTTPException(status_code=503, detail="Stripe no configurado.")

    settings = get_settings()
    payload   = await request.body()
    sig       = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        log.warning("payments.webhook_invalid_sig")
        raise HTTPException(status_code=400, detail="Firma inválida.")
    except Exception as exc:
        log.warning("payments.webhook_error", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))

    etype = event["type"]
    data  = event["data"]["object"]
    log.info("payments.webhook", event_type=etype)

    if etype == "checkout.session.completed":
        _handle_checkout_completed(stripe, data)

    elif etype in ("customer.subscription.updated", "customer.subscription.created"):
        _handle_subscription_updated(data)

    elif etype == "customer.subscription.deleted":
        _handle_subscription_deleted(data)

    elif etype == "invoice.payment_failed":
        _handle_payment_failed(data)

    return {"ok": True}


@router.get("/subscription")
@limiter.limit("30/minute")
async def get_subscription_status(request: Request):
    """Estado actual de la suscripción del usuario autenticado."""
    email = _require_auth(request)
    sub = get_subscription(email)
    return {
        "email":               email,
        "status":              sub.get("status", "free"),
        "plan":                sub.get("plan"),
        "current_period_end":  sub.get("current_period_end"),
        "cancel_at_period_end": sub.get("cancel_at_period_end", False),
        "stripe_configured":   bool(get_settings().stripe_secret_key),
    }


@router.post("/portal")
@limiter.limit("5/minute")
async def create_portal_session(request: Request):
    """Abre el Customer Portal de Stripe para gestionar la suscripción."""
    email = _require_auth(request)

    stripe = _stripe()
    if not stripe:
        raise HTTPException(status_code=503, detail="Stripe no configurado.")

    customer_id = get_customer_id(email)
    if not customer_id:
        raise HTTPException(
            status_code=400,
            detail="No se encontró suscripción activa para este usuario.",
        )

    settings = get_settings()
    base = settings.app_url.rstrip("/")
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{base}/app",
    )
    log.info("payments.portal_created", email=mask_email(email))
    return {"url": session.url}


# ── Handlers internos ─────────────────────────────────────────────────────────

def _handle_checkout_completed(stripe, session: dict) -> None:
    email       = session.get("metadata", {}).get("email", "")
    customer_id = session.get("customer", "")
    plan        = session.get("metadata", {}).get("plan", "")

    if not email:
        return

    if customer_id:
        set_customer_id(email, customer_id)

    # Recuperar la suscripción creada para obtener fechas
    sub_id = session.get("subscription")
    period_end = None
    if sub_id:
        try:
            sub = stripe.Subscription.retrieve(sub_id)
            period_end = sub.get("current_period_end")
        except Exception:
            pass

    upsert_subscription(email, {
        "status":              "active",
        "plan":                plan,
        "stripe_customer_id":  customer_id,
        "current_period_end":  period_end,
        "cancel_at_period_end": False,
    })
    log.info("payments.activated", email=mask_email(email), plan=plan)


def _handle_subscription_updated(sub: dict) -> None:
    customer_id = sub.get("customer", "")
    if not customer_id:
        return

    from app.subscription_store import _load
    subs = _load()
    email = next((e for e, d in subs.items() if d.get("stripe_customer_id") == customer_id), None)
    if not email:
        return

    upsert_subscription(email, {
        "status":              sub.get("status", "active"),
        "current_period_end":  sub.get("current_period_end"),
        "cancel_at_period_end": sub.get("cancel_at_period_end", False),
    })


def _handle_subscription_deleted(sub: dict) -> None:
    customer_id = sub.get("customer", "")
    if not customer_id:
        return

    from app.subscription_store import _load
    subs = _load()
    email = next((e for e, d in subs.items() if d.get("stripe_customer_id") == customer_id), None)
    if not email:
        return

    upsert_subscription(email, {"status": "canceled", "cancel_at_period_end": False})
    log.info("payments.canceled", email=mask_email(email))


def _handle_payment_failed(invoice: dict) -> None:
    customer_id = invoice.get("customer", "")
    if not customer_id:
        return

    from app.subscription_store import _load
    subs = _load()
    email = next((e for e, d in subs.items() if d.get("stripe_customer_id") == customer_id), None)
    if not email:
        return

    upsert_subscription(email, {"status": "past_due"})
    log.warning("payments.payment_failed", email=mask_email(email))

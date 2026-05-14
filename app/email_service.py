"""Servicio de email transaccional via Resend. Sin clave configurada: no-op silencioso."""
from __future__ import annotations

from app.config import get_settings
from app.security.logging_cfg import get_logger, mask_email

log = get_logger("email")


def _client():
    try:
        import resend
        settings = get_settings()
        if not settings.resend_api_key:
            return None
        resend.api_key = settings.resend_api_key
        return resend
    except ImportError:
        return None


def _from() -> str:
    return get_settings().resend_from


def send_welcome(email: str) -> None:
    r = _client()
    if not r:
        log.debug("email.skipped", reason="no_resend_key", to=mask_email(email))
        return
    try:
        r.Emails.send({
            "from": _from(),
            "to": [email],
            "subject": "Bienvenido a NexBody — Tu plan te espera",
            "html": _welcome_html(email),
        })
        log.info("email.sent", type="welcome", to=mask_email(email))
    except Exception as exc:
        log.warning("email.error", type="welcome", error=str(exc))


def send_newsletter_confirm(email: str) -> None:
    r = _client()
    if not r:
        log.debug("email.skipped", reason="no_resend_key", to=mask_email(email))
        return
    try:
        r.Emails.send({
            "from": _from(),
            "to": [email],
            "subject": "Confirmado — Estás en la lista de NexBody",
            "html": _newsletter_confirm_html(email),
        })
        log.info("email.sent", type="newsletter_confirm", to=mask_email(email))
    except Exception as exc:
        log.warning("email.error", type="newsletter_confirm", error=str(exc))


def send_day7_reminder(email: str) -> None:
    r = _client()
    if not r:
        return
    try:
        r.Emails.send({
            "from": _from(),
            "to": [email],
            "subject": "¿Cómo va tu primera semana? — NexBody",
            "html": _day7_html(email),
        })
        log.info("email.sent", type="day7_reminder", to=mask_email(email))
    except Exception as exc:
        log.warning("email.error", type="day7_reminder", error=str(exc))


def send_churn_recovery(email: str, days_inactive: int) -> None:
    r = _client()
    if not r:
        return
    try:
        r.Emails.send({
            "from": _from(),
            "to": [email],
            "subject": f"Te extrañamos — volvé a tu plan NexBody",
            "html": _churn_recovery_html(email, days_inactive),
        })
        log.info("email.sent", type="churn_recovery", to=mask_email(email))
    except Exception as exc:
        log.warning("email.error", type="churn_recovery", error=str(exc))


def send_plan_ready(email: str, template_name: str) -> None:
    r = _client()
    if not r:
        return
    try:
        r.Emails.send({
            "from": _from(),
            "to": [email],
            "subject": f"Tu plan {template_name} está listo — NexBody",
            "html": _plan_ready_html(email, template_name),
        })
        log.info("email.sent", type="plan_ready", to=mask_email(email))
    except Exception as exc:
        log.warning("email.error", type="plan_ready", error=str(exc))


# ── Templates HTML ────────────────────────────────────────────────────────────

def _base_html(content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #08080E; color: #F1F5F9; margin: 0; padding: 0; }}
  .wrap {{ max-width: 560px; margin: 0 auto; padding: 2rem 1.5rem; }}
  .logo {{ font-size: 1.25rem; font-weight: 900; color: #3B82F6; margin-bottom: 2rem; display: block; }}
  h1 {{ font-size: 1.5rem; font-weight: 800; margin: 0 0 1rem; color: #F1F5F9; }}
  p {{ font-size: 0.9375rem; line-height: 1.65; color: #94A3B8; margin: 0 0 1rem; }}
  .btn {{ display: inline-block; background: #3B82F6; color: #fff; padding: 0.75rem 1.5rem; border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 0.9375rem; margin: 1rem 0; }}
  .footer {{ font-size: 0.75rem; color: #475569; margin-top: 2.5rem; border-top: 1px solid #1E293B; padding-top: 1rem; }}
</style>
</head>
<body>
<div class="wrap">
  <span class="logo">NexBody</span>
  {content}
  <div class="footer">NexBody · <a href="https://nexbody.app/legal/privacidad" style="color:#475569;">Privacidad</a> · <a href="https://nexbody.app/legal/terminos" style="color:#475569;">Términos</a></div>
</div>
</body>
</html>"""


def _welcome_html(email: str) -> str:
    return _base_html(f"""
<h1>Tu cuerpo, tu plan.</h1>
<p>Hola, <strong>{email}</strong>. Ya tenés acceso a NexBody — la plataforma que genera planes de entrenamiento y nutrición adaptados a tu cuerpo y tu región.</p>
<p>El siguiente paso es completar tu perfil (2 minutos) para que generemos tu primer plan del día:</p>
<a href="https://nexbody.app/app" class="btn">Crear mi plan ahora</a>
<p>Si tenés preguntas, respondé este mail directamente.</p>
""")


def _newsletter_confirm_html(email: str) -> str:
    return _base_html(f"""
<h1>Ya estás en la lista.</h1>
<p>Confirmado, <strong>{email}</strong>. Vas a recibir los tips semanales de entrenamiento y nutrición de NexBody.</p>
<p>Mientras tanto, podés explorar el blog o crear tu plan personalizado:</p>
<a href="https://nexbody.app/app" class="btn">Ir a la app</a>
""")


def _plan_ready_html(email: str, template_name: str) -> str:
    return _base_html(f"""
<h1>Tu plan {template_name} está listo.</h1>
<p>Hola, <strong>{email}</strong>. Generamos tu plan del día en base a tu perfil. Incluye rutina, comidas sugeridas y tips de hidratación.</p>
<a href="https://nexbody.app/app" class="btn">Ver mi plan de hoy</a>
""")


def _day7_html(email: str) -> str:
    return _base_html(f"""
<h1>Una semana adentro — ¿cómo te fue?</h1>
<p>Hola, <strong>{email}</strong>. Pasó tu primera semana en NexBody. Queremos saber cómo está yendo.</p>
<p>Si completaste al menos 2 sesiones, tu cuerpo ya empezó a adaptarse. Si te costó, está bien — el plan se ajusta a vos.</p>
<p>Revisá tu plan de hoy y marcá el día cumplido:</p>
<a href="https://nexbody.app/app" class="btn">Ver mi plan de hoy</a>
<p style="margin-top:1.5rem;font-size:0.8125rem;">Si algo no funciona — horarios, ejercicios, comidas — respondé este mail y lo ajustamos.</p>
""")


def _churn_recovery_html(email: str, days: int) -> str:
    return _base_html(f"""
<h1>Hace {days} días que no te vemos.</h1>
<p>Hola, <strong>{email}</strong>. Tu plan NexBody te está esperando. Sabemos que la vida a veces complica los entrenamientos.</p>
<p>Por eso regeneramos tu plan con una carga más liviana, pensada para retomar sin frustrarte:</p>
<a href="https://nexbody.app/app" class="btn">Volver a mi plan</a>
<p style="margin-top:1.5rem;font-size:0.8125rem;">Si querés pausar temporalmente o cambiar el objetivo, podés hacerlo desde la app en cualquier momento.</p>
""")

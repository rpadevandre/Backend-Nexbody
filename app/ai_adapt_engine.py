"""Adapta el plan del día siguiente cuando el usuario saltea ejercicios o comidas."""
from __future__ import annotations

import json
from typing import Any

from app.config import get_settings
from app.forma_models import CheckinStatus, DailyPlan, ExerciseItem, MealItem, UserProfile
from app.security.logging_cfg import get_logger

log = get_logger("ai-adapt")

_SYSTEM = """\
Sos un IA Coach de fitness y nutrición para usuarios de LATAM.
El usuario salteo parte de su plan de hoy. Ajustá el plan del día siguiente para compensar de forma inteligente, sin castigar ni sobrecargar.
Respondé SOLO con JSON válido, sin texto extra, sin markdown.
"""


def _build_adapt_prompt(
    profile: UserProfile,
    today_plan: DailyPlan,
    checkin: CheckinStatus,
) -> str:
    skipped_ex  = checkin.skipped_exercises
    skipped_m   = checkin.skipped_meals
    workout_done = checkin.workout_done

    ctx_parts = []
    if not workout_done and not skipped_ex:
        ctx_parts.append("El usuario NO hizo el entrenamiento de hoy.")
    elif skipped_ex:
        ctx_parts.append(f"El usuario salteo estos ejercicios: {', '.join(skipped_ex)}.")
    if skipped_m:
        ctx_parts.append(f"El usuario salteo estas comidas: {', '.join(skipped_m)}.")

    context = " ".join(ctx_parts) or "El usuario salteo parte de su plan."

    plan_summary = {
        "objetivo": profile.desired_body_template_id,
        "ejercicios_hoy": [e.name for e in today_plan.workout],
        "comidas_hoy": [m.slot for m in today_plan.meals],
        "biotipo": profile.current_body_type,
        "dias_entreno_semana": profile.training_days_per_week,
    }

    schema = """{
  "adaptation_note": "string — explicación breve de cómo se ajusta el plan mañana (max 2 oraciones)",
  "workout_adjustment": "string — qué agregar/quitar/modificar en el próximo entreno",
  "nutrition_adjustment": "string — cómo ajustar las comidas del día siguiente",
  "extra_exercise": {"name":"string","sets":number,"reps":"string","rest_sec":number,"notes":"string"} | null,
  "kcal_adjustment": number | null
}"""

    return (
        f"{context}\n\n"
        f"Plan de hoy: {json.dumps(plan_summary, ensure_ascii=False)}\n\n"
        f"Generá las instrucciones de adaptación para MAÑANA con este esquema JSON:\n{schema}"
    )


def adapt_plan(
    profile: UserProfile,
    today_plan: DailyPlan,
    checkin: CheckinStatus,
) -> dict[str, Any] | None:
    """Llama a Claude para adaptar el plan del día siguiente. Retorna dict o None si falla."""
    settings = get_settings()
    if not settings.anthropic_api_key.strip():
        return None
    try:
        import anthropic
    except ImportError:
        return None

    try:
        client  = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg     = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _build_adapt_prompt(profile, today_plan, checkin)}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        log.info("ai_adapt.ok")
        return result
    except Exception as exc:
        log.warning("ai_adapt.error", error=str(exc))
        return None


def generate_explanation(profile: UserProfile, plan: DailyPlan) -> str:
    """Genera una explicación breve de por qué se armó este plan."""
    settings = get_settings()
    if not settings.anthropic_api_key.strip():
        return _fallback_explanation(profile)
    try:
        import anthropic
    except ImportError:
        return _fallback_explanation(profile)

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        prompt = (
            f"En 2-3 oraciones, explicá en español informal por qué se generó este plan de entrenamiento y nutrición. "
            f"Biotipo: {profile.current_body_type}. Objetivo: {profile.desired_body_template_id}. "
            f"Días disponibles: {profile.training_days_per_week}. Gym: {profile.gym_type}. "
            f"Dieta: {profile.diet_style}. País: {profile.country_code}. "
            f"Ejercicios: {[e.name for e in plan.workout[:3]]}. "
            f"Respondé solo el texto, sin JSON, sin bullet points."
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return _fallback_explanation(profile)


def _fallback_explanation(profile: UserProfile) -> str:
    tid = profile.desired_body_template_id or "recomp"
    days = profile.training_days_per_week
    bio  = profile.current_body_type or "mixto"
    return (
        f"Este plan está diseñado para tu objetivo de {tid.replace('_', ' ')} "
        f"teniendo en cuenta tu biotipo {bio} y tus {days} días disponibles de entrenamiento. "
        f"Los ejercicios y comidas se adaptaron a tu región y estilo alimentario."
    )

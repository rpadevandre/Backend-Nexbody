"""Plan engine con IA — llama a Anthropic Claude si hay API key; si no, devuelve None."""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from app.config import get_settings
from app.diet_regions import country_label_es
from app.forma_models import BODY_TEMPLATES, DailyPlan, ExerciseItem, MealItem, UserProfile, WarmupItem
from app.security.logging_cfg import get_logger

log = get_logger("ai-plan")

_SYSTEM = """\
Eres un entrenador y nutricionista especializado en fitness para LATAM.
Generas planes de entrenamiento y alimentación PERSONALIZADOS y PRÁCTICOS.
Respondés SOLO con JSON válido, sin texto extra, sin markdown, sin explicaciones.
Los planes deben usar ingredientes accesibles en el país indicado.
Usá lenguaje informal pero profesional en español rioplatense/neutral según el país.
"""

_PLAN_SCHEMA = """\
{
  "title": "string — titulo del plan del dia",
  "gym_where": "string — lugar de entreno",
  "gym_tip": "string — consejo breve sobre el lugar",
  "warm_up": [
    {"name": "string", "duration_min": number, "detail": "string"}
  ],
  "workout": [
    {"name": "string", "sets": number, "reps": "string", "rest_sec": number, "notes": "string"}
  ],
  "meals": [
    {"slot": "string — Desayuno|Almuerzo|Merienda|Cena|Snack", "suggestion": "string", "kcal_hint": number}
  ],
  "hydration_note": "string"
}
"""


def _template_desc(tid: str) -> str:
    for t in BODY_TEMPLATES:
        if t.id == tid:
            return f"{t.name}: {t.description}. Enfoque: {t.focus}"
    return "Recomposición general"


def _build_prompt(profile: UserProfile) -> str:
    tid = profile.desired_body_template_id or "recomp"
    country = country_label_es(profile.country_code) if profile.country_code else "LATAM"
    gender_map = {
        "hombre": "masculino", "mujer": "femenino",
        "no_binario": "no binario", "otro": "otro", "prefiero_no_decir": "no especificado",
    }
    gender = gender_map.get(profile.gender, "no especificado")
    gym_map = {
        "gimnasio": "gimnasio comercial con pesas y máquinas",
        "casa": "casa con mancuernas o bandas elásticas",
        "calistenia": "parque o barras de calistenia",
        "mixto": "combinación de casa y gimnasio",
    }
    gym = gym_map.get(profile.gym_type, "gimnasio")

    lines = [
        f"País: {country}",
        f"Género: {gender}",
        f"Edad: {profile.age or '?'} años",
        f"Peso: {profile.weight_kg or '?'} kg, Altura: {profile.height_cm or '?'} cm",
        f"Objetivo corporal: {_template_desc(tid)}",
        f"Biotipo actual: {profile.current_body_type or 'no especificado'}",
        f"Estilo alimentario: {profile.diet_style}",
        f"Alimentos no deseados: {profile.food_dislikes or 'ninguno'}",
        f"Comidas al día: {profile.meals_per_day}",
        f"Lugar de entreno: {gym}",
        f"Ciudad/zona: {profile.city_or_area or 'no indicada'}",
        f"Días de entreno por semana: {profile.training_days_per_week}",
        f"Cómo come hoy: {profile.how_i_eat or 'no indicado'}",
        f"Ejercicios que hace: {profile.exercises_i_do or 'no indicado'}",
        f"Fecha: {date.today().strftime('%A %d/%m/%Y')}",
    ]

    return (
        "Generá un plan completo para HOY con esta información del usuario:\n\n"
        + "\n".join(f"- {l}" for l in lines)
        + f"\n\nRespondé EXACTAMENTE con este esquema JSON (sin texto adicional):\n{_PLAN_SCHEMA}"
    )


def build_ai_plan(profile: UserProfile) -> DailyPlan | None:
    """Genera el plan con Claude. Retorna None si no hay API key o falla."""
    settings = get_settings()
    if not settings.anthropic_api_key.strip():
        return None

    try:
        import anthropic
    except ImportError:
        log.warning("ai_plan.anthropic_not_installed")
        return None

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _build_prompt(profile)}],
        )
        raw = msg.content[0].text.strip()

        # Limpiar posible markdown fence
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data: dict[str, Any] = json.loads(raw)

        warm_up = [WarmupItem(**w) for w in data.get("warm_up", [])]
        workout = [ExerciseItem(**e) for e in data.get("workout", [])]
        meals   = [MealItem(**m)    for m in data.get("meals",   [])]

        plan = DailyPlan(
            plan_date=date.today().isoformat(),
            title=data.get("title", "Tu plan de hoy"),
            gym_where=data.get("gym_where", ""),
            gym_tip=data.get("gym_tip", ""),
            warm_up=warm_up,
            workout=workout,
            meals=meals,
            hydration_note=data.get("hydration_note", "2–3 L agua/día."),
            meta={
                "source": "ai",
                "model": "claude-haiku-4-5",
                "desired_template_id": profile.desired_body_template_id,
            },
        )
        log.info("ai_plan.ok", model="claude-haiku-4-5")
        return plan

    except json.JSONDecodeError as exc:
        log.warning("ai_plan.json_error", error=str(exc))
        return None
    except Exception as exc:
        log.warning("ai_plan.error", error=str(exc))
        return None

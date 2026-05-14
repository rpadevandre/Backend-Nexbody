"""Genera plan diario (calentamiento, rutina, comidas, sugerencia de gym) según perfil."""
from __future__ import annotations

from datetime import date
from typing import Any

from app.diet_regions import country_label_es, meal_hints_for_country
from app.forma_models import (
    BODY_TEMPLATES,
    DailyPlan,
    ExerciseItem,
    MealItem,
    UserProfile,
    WarmupItem,
)


# ── Injury contraindication map ──────────────────────────────────────────────
# Keys are substrings — matched case-insensitively against exercise names.
_CONTRAINDICATIONS: dict[str, list[str]] = {
    "rodilla":      ["sentadilla", "prensa", "zancada", "estocada", "burpee", "salto", "squat"],
    "hombro":       ["press banca", "press militar", "press inclinado", "elevaciones laterales",
                     "dominadas", "fondos", "jalón"],
    "espalda_baja": ["peso muerto", "remo con barra", "remo pendlay", "sentadilla con barra",
                     "sentadilla o variante pesada"],
    "cadera":       ["hip thrust", "abducción de cadera", "sentadilla sumo", "zancada",
                     "estocada", "prensa o sentadilla"],
    "muneca":       ["press banca", "remo pendlay", "dominadas", "curl bíceps",
                     "farmer carry", "fondos"],
    "cuello":       ["peso muerto convencional", "sentadilla con barra", "press sobre cabeza"],
}

_INJURY_REASONS: dict[str, str] = {
    "rodilla":      "Carga compresiva sobre la articulación — evitar impacto y flexión profunda.",
    "hombro":       "Rango de movimiento limitado — evitar empuje y jalón sobre la cabeza.",
    "espalda_baja": "Carga en flexión lumbar — priorizar trabajo en posición neutra.",
    "cadera":       "Estrés articular en el rango completo — usar extensiones guiadas.",
    "muneca":       "Carga axial directa — usar correas o agarre neutro alternativo.",
    "cuello":       "Compresión cervical — evitar carga axial sobre los hombros.",
}

_INJURY_ALTERNATIVES: dict[str, ExerciseItem] = {
    "rodilla":      ExerciseItem(name="Extensión de pierna (ROM controlado)", sets=3, reps="15–20", rest_sec=60,  notes="Solo hasta 90°."),
    "hombro":       ExerciseItem(name="Remo en polea baja agarre neutro",     sets=3, reps="12–15", rest_sec=75),
    "espalda_baja": ExerciseItem(name="Bird-dog + Pallof press",              sets=3, reps="10 c/lado", rest_sec=60, notes="Core neutro."),
    "cadera":       ExerciseItem(name="Extensión de cadera en máquina",        sets=3, reps="15",    rest_sec=60),
    "muneca":       ExerciseItem(name="Curl con correas (grip neutro)",         sets=3, reps="12",    rest_sec=75),
    "cuello":       ExerciseItem(name="Cardio suave en bicicleta estática",    sets=1, reps="20 min Z2", rest_sec=0),
}


def _is_contraindicated(ex_name: str, injury: str) -> bool:
    name_lower = ex_name.lower()
    return any(kw in name_lower for kw in _CONTRAINDICATIONS.get(injury, []))


def _apply_injury_filters(
    workout: list[ExerciseItem],
    injuries: list[str],
) -> tuple[list[ExerciseItem], list[dict]]:
    """Remove contraindicated exercises, replace with safe alternatives.
    Returns filtered workout + list of {name, reason} to show in UI."""
    active_injuries = [i for i in injuries if i != "ninguna"]
    if not active_injuries:
        return workout, []

    filtered: list[ExerciseItem] = []
    avoided: list[dict] = []
    added_alternatives: set[str] = set()

    for ex in workout:
        blocking = [inj for inj in active_injuries if _is_contraindicated(ex.name, inj)]
        if blocking:
            avoided.append({"name": ex.name, "reason": _INJURY_REASONS[blocking[0]]})
            alt = _INJURY_ALTERNATIVES.get(blocking[0])
            if alt and alt.name not in added_alternatives:
                filtered.append(alt)
                added_alternatives.add(alt.name)
        else:
            filtered.append(ex)

    return filtered, avoided


def _template_name(tid: str) -> str:
    for t in BODY_TEMPLATES:
        if t.id == tid:
            return t.name
    return "personalizado"


def build_daily_plan(profile: UserProfile) -> DailyPlan:
    tid = profile.desired_body_template_id or "recomp"
    template_label = _template_name(tid)

    # Calentamiento siempre contextual
    warm = [
        WarmupItem(name="Movilidad articular", duration_min=5, detail="Cuello, hombros, cadera en círculos lentos."),
        WarmupItem(name="Activación cardiovascular", duration_min=5, detail="Bici elíptica, caminata inclinada o saltos suaves sin rebotes bruscos."),
        WarmupItem(name="Especificidad", duration_min=5, detail="2 series ligeras del primer ejercicio principal con 50% del peso de trabajo."),
    ]

    # Gym / lugar
    gym_map = {
        "gimnasio": (
            "Gimnasio comercial o centro con máquinas",
            "Si podés, elegí uno con peso libre y máquinas guiadas; llegá en horario que puedas mantener 45–60 min.",
        ),
        "casa": (
            "Entreno en casa",
            "Invertí en bandas + mancuernas ajustables; ventila el espacio y usa tapete.",
        ),
        "calistenia": (
            "Parque / calistenia",
            "Buscá barras paralelas y lugar seguro; lleva guantes si hace frío.",
        ),
        "mixto": (
            "Combinación casa + gym",
            "Fuerza pesada en gym 2×/sem; en casa movilidad y accesorios.",
        ),
    }
    gtype = profile.gym_type if profile.gym_type in gym_map else "gimnasio"
    gym_where, gym_tip = gym_map[gtype]
    if profile.city_or_area.strip():
        gym_where += f" · zona: {profile.city_or_area.strip()}"

    # Rutina principal según objetivo (plantillas simplificadas)
    workout: list[ExerciseItem] = []

    if tid in ("bulk_hypertrophy",):
        workout = [
            ExerciseItem(name="Sentadilla o prensa", sets=4, reps="8–10", rest_sec=120, notes="Profundidad controlada."),
            ExerciseItem(name="Press banca o mancuernas", sets=4, reps="8–12", rest_sec=90),
            ExerciseItem(name="Remo con barra o máquina", sets=3, reps="10–12", rest_sec=90),
            ExerciseItem(name="Elevaciones laterales", sets=3, reps="12–15", rest_sec=60),
            ExerciseItem(name="Curl bíceps + extensión tríceps", sets=3, reps="12–15", rest_sec=60),
        ]
    elif tid in ("lean_define",):
        workout = [
            ExerciseItem(name="Burpees o air bike intervals", sets=4, reps="30 seg trabajo / 30 descanso", rest_sec=30),
            ExerciseItem(name="Peso muerto rumano o hip thrust", sets=4, reps="10–12", rest_sec=75),
            ExerciseItem(name="Dominadas asistidas o jalón", sets=3, reps="10–12", rest_sec=75),
            ExerciseItem(name="Zancadas caminando", sets=3, reps="12 cada pierna", rest_sec=60),
            ExerciseItem(name="Plancha + hollow hold", sets=3, reps="45–60 seg", rest_sec=45),
        ]
    elif tid in ("strong",):
        workout = [
            ExerciseItem(name="Sentadilla o variante pesada", sets=5, reps="3–5", rest_sec=180),
            ExerciseItem(name="Press banca", sets=5, reps="3–5", rest_sec=180),
            ExerciseItem(name="Peso muerto convencional o sumo", sets=3, reps="3–5", rest_sec=180),
            ExerciseItem(name="Accesorio core liviano", sets=3, reps="12", rest_sec=60),
        ]
    elif tid in ("endurance",):
        workout = [
            ExerciseItem(name="Cardio continuo elegido", sets=1, reps="25–40 min Z2", rest_sec=0, notes="Habla sin ahogarte."),
            ExerciseItem(name="Circuito full body ligero", sets=3, reps="15 reps cada ejercicio", rest_sec=45),
            ExerciseItem(name="Estiramientos dinámicos finales", sets=1, reps="10 min", rest_sec=0),
        ]
    elif tid in ("femboy_silhouette",):
        workout = [
            ExerciseItem(name="Hip thrust o puente de glúteos", sets=4, reps="12–15", rest_sec=75, notes="Apretá glúteo arriba."),
            ExerciseItem(name="Sentadilla con foco en profundidad", sets=4, reps="10–12", rest_sec=90),
            ExerciseItem(name="Zancadas caminando", sets=3, reps="12 cada pierna", rest_sec=75),
            ExerciseItem(name="Elevaciones laterales livianas", sets=3, reps="15–20", rest_sec=45),
            ExerciseItem(name="Abdominales tipo hollow / plank lateral", sets=3, reps="45 seg", rest_sec=45),
        ]
    elif tid in ("trans_fem_silhouette",):
        workout = [
            ExerciseItem(name="Abducción de cadera en máquina o banda", sets=4, reps="15–20", rest_sec=60),
            ExerciseItem(name="Prensa o sentadilla sumo", sets=4, reps="12–15", rest_sec=90),
            ExerciseItem(name="Peso muerto rumano", sets=3, reps="10–12", rest_sec=75),
            ExerciseItem(name="Elevaciones laterales + posteriores", sets=3, reps="12–15", rest_sec=60),
            ExerciseItem(name="Cardio suave caminata inclinada", sets=1, reps="15–20 min", rest_sec=0),
        ]
    elif tid in ("tomboy_silhouette",):
        workout = [
            ExerciseItem(name="Dominadas asistidas o jalón", sets=4, reps="8–12", rest_sec=90),
            ExerciseItem(name="Remo con barra o mancuerna", sets=4, reps="8–12", rest_sec=90),
            ExerciseItem(name="Press militar o hombro con mancuernas", sets=3, reps="8–12", rest_sec=75),
            ExerciseItem(name="Sentadilla o prensa piernas", sets=3, reps="10–12", rest_sec=90),
            ExerciseItem(name="Farmer carry o plancha", sets=3, reps="40–60 seg", rest_sec=60),
        ]
    elif tid in ("trans_masc_silhouette",):
        workout = [
            ExerciseItem(name="Press banca o flexiones inclinadas", sets=4, reps="8–12", rest_sec=90),
            ExerciseItem(name="Press militar", sets=4, reps="8–12", rest_sec=90),
            ExerciseItem(name="Remo pendlay o máquina", sets=3, reps="8–12", rest_sec=90),
            ExerciseItem(name="Fondos en paralelas o tríceps", sets=3, reps="10–15", rest_sec=75),
            ExerciseItem(name="Core anti-extensión (rollout / dead bug)", sets=3, reps="12", rest_sec=60),
        ]
    elif tid in ("trans_nb_silhouette",):
        workout = [
            ExerciseItem(name="Sentadilla goblet", sets=3, reps="12", rest_sec=75),
            ExerciseItem(name="Press inclinado mancuerna", sets=3, reps="10–12", rest_sec=75),
            ExerciseItem(name="Remo sentado", sets=3, reps="10–12", rest_sec=75),
            ExerciseItem(name="Estocadas alternadas", sets=3, reps="10 cada pierna", rest_sec=75),
            ExerciseItem(name="Cardio elegido moderado", sets=1, reps="15 min", rest_sec=0),
        ]
    else:  # recomp y otros
        workout = [
            ExerciseItem(name="Sentadilla goblet o multipower", sets=4, reps="10–12", rest_sec=90),
            ExerciseItem(name="Press inclinado mancuerna", sets=3, reps="10–12", rest_sec=75),
            ExerciseItem(name="Dominadas o remo", sets=3, reps="10–12", rest_sec=75),
            ExerciseItem(name="Bike walk o caminata inclinada", sets=1, reps="15–20 min Z2", rest_sec=0),
        ]

    # Comidas según estilo y texto del usuario
    diet_note = profile.how_i_eat.strip() or "Comidas regulares, priorizar proteína en cada plato."
    if profile.food_dislikes.strip():
        diet_note += f" · Evitar / no te gusta: {profile.food_dislikes.strip()}"
    meals = _meals_for_style(
        profile.diet_style,
        profile.meals_per_day,
        diet_note,
        profile.country_code,
    )

    hydration = "2–3 L agua/día; más si sudás mucho o hace calor."

    title = f"Hoy · {template_label} ({date.today().strftime('%d/%m')})"

    meta_digest: dict[str, Any] = {
        "current_body": profile.current_body_type,
        "diet_style": profile.diet_style,
        "training_days": profile.training_days_per_week,
    }
    if profile.age is not None:
        meta_digest["age"] = profile.age
    if profile.gender:
        meta_digest["gender"] = profile.gender
    if profile.weight_kg is not None and profile.height_cm is not None and profile.height_cm > 0:
        h_m = profile.height_cm / 100.0
        meta_digest["bmi"] = round(profile.weight_kg / (h_m * h_m), 1)
    cc = (profile.country_code or "").strip().upper()
    if cc and cc not in ("XX", "OT"):
        meta_digest["country_code"] = cc
        meta_digest["country_label"] = country_label_es(cc)

    # Apply injury filters
    injuries = list(profile.injuries or [])
    workout, exercises_to_avoid = _apply_injury_filters(workout, injuries)
    if exercises_to_avoid:
        meta_digest["exercises_to_avoid"] = exercises_to_avoid

    if profile.fitness_level == "principiante":
        for ex in workout:
            if ex.sets > 3:
                ex.sets = 3
            ex.rest_sec = max(ex.rest_sec, 90)

    return DailyPlan(
        plan_date=date.today().isoformat(),
        title=title,
        gym_where=gym_where,
        gym_tip=gym_tip,
        warm_up=warm,
        workout=workout,
        meals=meals,
        hydration_note=hydration,
        meta={
            "desired_template_id": tid,
            "profile_digest": meta_digest,
        },
    )


def _meals_for_style(style: str, n_meals: int, user_notes: str, country_code: str) -> list[MealItem]:
    n_meals = max(3, min(n_meals, 6))
    breakfast_hint, merienda_hint, plates = meal_hints_for_country(country_code)
    plate = plates.get(style, plates["otro"])
    note_suffix = f" · Lo que contaste de tu forma de comer: {user_notes}" if user_notes.strip() else ""

    slots_order = ["Desayuno", "Almuerzo", "Merienda", "Cena", "Snack", "Colación"]
    meals: list[MealItem] = []
    kcals = [420, 580, 280, 620, 200, 250][:n_meals]
    while len(kcals) < n_meals:
        kcals.append(450)

    for i in range(n_meals):
        slot = slots_order[i] if i < len(slots_order) else f"Comida {i + 1}"
        if i == 0:
            sug = breakfast_hint + note_suffix
        elif slot == "Merienda":
            sug = merienda_hint
        elif slot in ("Cena",) or i == n_meals - 1:
            sug = f"Cena más liviana: {plate} Reducí carb si dormís pronto."
        else:
            sug = plate + note_suffix

        meals.append(MealItem(slot=slot, suggestion=sug.strip(), kcal_hint=kcals[i]))

    return meals

"""Modelos del producto FormaRuta (perfil, plan diario, plantillas)."""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class BodyTemplate(BaseModel):
    id: str
    name: str
    description: str
    focus: str
    icon: str  # icon name string (e.g. "dumbbell", "flame")
    # Si está definido, la tarjeta solo aplica a esos géneros (perfil).
    # None o lista vacía = visible para todos.
    visible_if_gender_in: list[str] | None = None
    group: str = "fitness"  # fitness | silueta — solo UI


class UserProfile(BaseModel):
    age: int | None = None
    gender: str = ""  # hombre | mujer | no_binario | otro | prefiero_no_decir
    weight_kg: float | None = None
    height_cm: float | None = None
    country_code: str = ""  # ISO 3166-1 alpha-2 (ej. AR); XX u OT = sin país específico
    desired_body_template_id: str = ""
    current_body_type: str = ""  # ectomorph | mesomorph | endomorph | mixto | no_se
    how_i_eat: str = ""  # cómo come hoy (texto libre)
    diet_style: str = "omnivoro"  # omnivoro | vegetariano | vegano | sin_gluten | sin_lactosa | keto | paleo | otro
    food_dislikes: str = ""
    meals_per_day: int = 3
    training_days_per_week: int = 3
    gym_type: str = "gimnasio"  # gimnasio | casa | calistenia | mixto
    exercises_i_do: str = ""  # qué hace hoy
    city_or_area: str = ""  # para sugerir tipo de gimnasio (texto libre)
    onboarding_complete: bool = False
    # Lesiones y nivel (agregados en v2)
    injuries: list[str] = Field(default_factory=list)
    # ninguna | rodilla | hombro | espalda_baja | cadera | muneca | cuello
    fitness_level: str = "intermedio"  # principiante | intermedio | avanzado
    injuries_notes: str = ""

    def merge(self, other: dict[str, Any]) -> UserProfile:
        data = self.model_dump()
        for k, v in other.items():
            if k in data and v is not None:
                data[k] = v
        return UserProfile(**data)


class WarmupItem(BaseModel):
    name: str
    duration_min: float
    detail: str


class ExerciseItem(BaseModel):
    name: str
    sets: int
    reps: str
    rest_sec: int = 90
    notes: str = ""


class MealItem(BaseModel):
    slot: str  # Desayuno, Almuerzo, ...
    suggestion: str
    kcal_hint: int | None = None


class CheckinStatus(BaseModel):
    workout_done:      bool | None = None   # None = no marcado aún
    skipped_exercises: list[str]   = Field(default_factory=list)
    meals_done:        list[bool]  = Field(default_factory=list)
    skipped_meals:     list[str]   = Field(default_factory=list)
    adapted:           bool        = False  # ya se adaptó el plan por este skip


class DailyPlan(BaseModel):
    plan_date: str = Field(default_factory=lambda: date.today().isoformat())
    title: str = ""
    gym_where: str = ""
    gym_tip: str = ""
    warm_up: list[WarmupItem] = Field(default_factory=list)
    workout: list[ExerciseItem] = Field(default_factory=list)
    meals: list[MealItem] = Field(default_factory=list)
    hydration_note: str = ""
    explanation: str = ""   # por qué este plan (generado por IA)
    checkin: CheckinStatus = Field(default_factory=CheckinStatus)
    meta: dict[str, Any] = Field(default_factory=dict)


class WeightEntry(BaseModel):
    date: str   # ISO date
    kg: float


class UserState(BaseModel):
    profile:         UserProfile      = Field(default_factory=UserProfile)
    daily_plan:      DailyPlan | None = None
    plan_overrides:  dict[str, Any]   = Field(default_factory=dict)
    weight_log:      list[WeightEntry] = Field(default_factory=list)
    checkin_history: dict[str, Any]   = Field(default_factory=dict)
    # Clave = fecha ISO (ej. "2026-05-11"), valor = dict con campos de CheckinStatus


BODY_TEMPLATES: list[BodyTemplate] = [
    # Objetivos fitness primero (orden API / UI por defecto)
    BodyTemplate(
        id="lean_define",
        name="Definido · atlético",
        description="Menos grasa, músculo visible, estética tipo beach.",
        focus="Déficit calórico suave + fuerza + cardio HIIT moderado",
        icon="sun",
        group="fitness",
    ),
    BodyTemplate(
        id="bulk_hypertrophy",
        name="Volumen · hipertrofia",
        description="Ganar tamaño muscular máximo.",
        focus="Superávit controlado + volumen de series + descanso",
        icon="dumbbell",
        group="fitness",
    ),
    BodyTemplate(
        id="recomp",
        name="Recomposición",
        description="Perder grasa y ganar/mantener músculo a la vez.",
        focus="Proteína alta + entreno progresivo + NEAT",
        icon="scale",
        group="fitness",
    ),
    BodyTemplate(
        id="strong",
        name="Fuerza · rendimiento",
        description="Levantar más peso, menos foco en el espejo.",
        focus="Series bajas de reps + descansos largos + técnica",
        icon="weight",
        group="fitness",
    ),
    BodyTemplate(
        id="endurance",
        name="Resistencia · salud",
        description="Más energía diaria, cardio y movilidad.",
        focus="Cardio progresivo + full body ligero + movilidad",
        icon="run",
        group="fitness",
    ),
    # Silueta / expresión (andrógina, trans, etc.) al final — filtradas por género en UI
    BodyTemplate(
        id="femboy_silhouette",
        name="Femboy · silueta andrógina",
        description="Piernas y glúteos definidos, cintura trabajada, tren superior más liviano.",
        focus="Hipertrofia inferior + core + hombros con volumen moderado",
        icon="flower",
        visible_if_gender_in=["hombre"],
        group="silueta",
    ),
    BodyTemplate(
        id="trans_fem_silhouette",
        name="Silueta femenina / transfemenina",
        description="Énfasis en cadera, piernas y forma general femenina (sin juicios médicos).",
        focus="Inferior + glúteos + hombros redondeados + cardio suave",
        icon="sparkle",
        visible_if_gender_in=["hombre"],
        group="silueta",
    ),
    BodyTemplate(
        id="tomboy_silhouette",
        name="Tomboy · atlética-andrógina",
        description="Espalda y hombros marcados, piernas fuertes, silueta menos curva.",
        focus="Tirones + hombros + piernas completas",
        icon="cap",
        visible_if_gender_in=["mujer"],
        group="silueta",
    ),
    BodyTemplate(
        id="trans_masc_silhouette",
        name="Afirmación transmasculina · torso",
        description="Pecho, hombros y brazos; línea de cintura más recta.",
        focus="Empuje + espalda + core estable",
        icon="diamond",
        visible_if_gender_in=["mujer"],
        group="silueta",
    ),
    BodyTemplate(
        id="trans_nb_silhouette",
        name="Silueta trans / no binaria",
        description="Plan equilibrado según lo que busques mostrar; podés afinar en tus notas.",
        focus="Full body + flexibilidad en objetivos",
        icon="gender-fluid",
        visible_if_gender_in=["no_binario", "otro", "prefiero_no_decir"],
        group="silueta",
    ),
]

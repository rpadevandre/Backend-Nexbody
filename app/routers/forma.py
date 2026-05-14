"""API FormaRuta: plantillas de cuerpo, onboarding, plan diario editable."""
from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.forma_models import (
    BODY_TEMPLATES,
    CheckinStatus,
    DailyPlan,
    ExerciseItem,
    MealItem,
    UserProfile,
    UserState,
    WarmupItem,
)
from app.forma_store import load_state, save_full, save_profile
from app.plan_engine import build_daily_plan
from app.ai_plan_engine import build_ai_plan
from app.security.logging_cfg import get_logger
from app.security.sanitize import SanitizationError, sanitize_str

# Importamos el limiter ya configurado en main
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
log     = get_logger("forma-router")

router = APIRouter(prefix="/v1/forma", tags=["forma-ruta"])

# ── Helpers ───────────────────────────────────────────────────────────────────

_MAX_FREE_TEXT = 500   # Limite para campos de texto libre del usuario

def _sanitize_profile(profile: UserProfile) -> UserProfile:
    """Aplica sanitizacion a los campos de texto libre del perfil."""
    try:
        data = profile.model_dump()
        for field in ("how_i_eat", "food_dislikes", "exercises_i_do", "city_or_area"):
            if data.get(field):
                data[field] = sanitize_str(data[field], field)[:_MAX_FREE_TEXT]
        # Campos de seleccion — validar contra whitelist
        allowed_gender = {"hombre", "mujer", "no_binario", "otro", "prefiero_no_decir", ""}
        if data.get("gender") not in allowed_gender:
            data["gender"] = ""
        allowed_diet = {"omnivoro", "vegetariano", "vegano", "sin_gluten", "sin_lactosa", "keto", "paleo", "otro"}
        if data.get("diet_style") not in allowed_diet:
            data["diet_style"] = "omnivoro"
        allowed_gym = {"gimnasio", "casa", "calistenia", "mixto"}
        if data.get("gym_type") not in allowed_gym:
            data["gym_type"] = "gimnasio"
        # country_code: solo 2 letras uppercase o vacio
        cc = data.get("country_code", "")
        data["country_code"] = cc[:2].upper() if cc and cc.isalpha() else ""
        # fitness_level
        allowed_level = {"principiante", "intermedio", "avanzado"}
        if data.get("fitness_level") not in allowed_level:
            data["fitness_level"] = "intermedio"
        # injuries whitelist
        allowed_injuries = {"ninguna", "rodilla", "hombro", "espalda_baja", "cadera", "muneca", "cuello"}
        raw_injuries = data.get("injuries") or []
        data["injuries"] = [i for i in raw_injuries if i in allowed_injuries][:6]
        # injuries_notes
        if data.get("injuries_notes"):
            data["injuries_notes"] = sanitize_str(data["injuries_notes"])[:300]
        return UserProfile(**data)
    except SanitizationError as e:
        log.warning("sanitize.rejected", field=str(e))
        raise HTTPException(status_code=422, detail=str(e))


class DailyPlanPatch(BaseModel):
    workout:   list[ExerciseItem] | None = None
    meals:     list[MealItem]     | None = None
    warm_up:   list[WarmupItem]   | None = None
    gym_where: str | None = None
    gym_tip:   str | None = None

    @field_validator("gym_where", "gym_tip", mode="before")
    @classmethod
    def _clean_text(cls, v):
        if v is None:
            return v
        try:
            return sanitize_str(str(v))[:300]
        except SanitizationError as e:
            raise ValueError(str(e))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/body-templates")
@limiter.limit("60/minute")
async def body_templates(request: Request):
    return {"items": [t.model_dump() for t in BODY_TEMPLATES]}


@router.get("/profile")
@limiter.limit("60/minute")
async def get_profile(request: Request):
    return load_state().profile.model_dump()


@router.put("/profile")
@limiter.limit("20/minute")
async def put_profile(request: Request, profile: UserProfile = Body(...)):
    """Guarda el perfil del usuario tras sanitizacion."""
    clean = _sanitize_profile(profile)
    log.info("profile.updated", ip=get_remote_address(request), onboarding=clean.onboarding_complete)
    state = save_profile(clean)
    if clean.onboarding_complete:
        plan = build_ai_plan(clean) or build_daily_plan(clean)
        state.daily_plan = plan
        save_full(state)
    return {
        "profile":    state.profile.model_dump(),
        "daily_plan": state.daily_plan.model_dump() if state.daily_plan else None,
    }


@router.get("/plan/daily")
@limiter.limit("60/minute")
async def get_daily_plan(request: Request, regenerate: bool = False):
    state = load_state()
    if not state.profile.onboarding_complete:
        raise HTTPException(
            status_code=400,
            detail="Completa el cuestionario antes de ver el plan.",
        )
    if regenerate or state.daily_plan is None:
        plan = build_ai_plan(state.profile) or build_daily_plan(state.profile)
        state.daily_plan = plan
        save_full(state)
    return state.daily_plan.model_dump()


@router.patch("/plan/daily")
@limiter.limit("30/minute")
async def patch_daily_plan(request: Request, patch: DailyPlanPatch = Body(...)):
    """Edita el plan diario. Los campos de texto se sanitizan via el validador del modelo."""
    state = load_state()
    if state.daily_plan is None:
        raise HTTPException(status_code=400, detail="No hay plan para editar.")
    data = state.daily_plan.model_dump()
    if patch.workout   is not None: data["workout"]   = [x.model_dump() if isinstance(x, ExerciseItem) else x for x in patch.workout]
    if patch.meals     is not None: data["meals"]     = [x.model_dump() if isinstance(x, MealItem)     else x for x in patch.meals]
    if patch.warm_up   is not None: data["warm_up"]   = [x.model_dump() if isinstance(x, WarmupItem)   else x for x in patch.warm_up]
    if patch.gym_where is not None: data["gym_where"] = patch.gym_where
    if patch.gym_tip   is not None: data["gym_tip"]   = patch.gym_tip
    new_plan = DailyPlan(**data)
    state.daily_plan = new_plan
    save_full(state)
    log.info("plan.patched", ip=get_remote_address(request))
    return new_plan.model_dump()


@router.post("/plan/regenerate")
@limiter.limit("10/hour")
async def regenerate_plan(request: Request):
    """Regenera el plan. Limite estricto — operacion costosa."""
    state = load_state()
    if not state.profile.onboarding_complete:
        raise HTTPException(status_code=400, detail="Perfil incompleto.")
    plan = build_ai_plan(state.profile) or build_daily_plan(state.profile)
    state.daily_plan = plan
    save_full(state)
    log.info("plan.regenerated", ip=get_remote_address(request))
    return plan.model_dump()


class OnboardingStatus(BaseModel):
    profile_complete: bool
    has_plan: bool


@router.get("/status")
@limiter.limit("120/minute")
async def forma_status(request: Request):
    st = load_state()
    return OnboardingStatus(
        profile_complete=st.profile.onboarding_complete,
        has_plan=st.daily_plan is not None,
    )


@router.post("/profile/reset")
@limiter.limit("5/minute")
async def reset_profile(request: Request):
    save_full(UserState())
    log.info("profile.reset", ip=get_remote_address(request))
    return {"ok": True}


# ── Check-in ──────────────────────────────────────────────────────────────────

class CheckinPayload(BaseModel):
    workout_done:      bool | None = None
    skipped_exercises: list[str]   = Field(default_factory=list)
    meals_done:        list[bool]  = Field(default_factory=list)
    skipped_meals:     list[str]   = Field(default_factory=list)


@router.post("/checkin")
@limiter.limit("30/minute")
async def save_checkin(request: Request, payload: CheckinPayload = Body(...)):
    """Guarda el check-in del día y lo almacena en el historial."""
    from datetime import date as _date
    state = load_state()
    today = _date.today().isoformat()

    if state.daily_plan:
        state.daily_plan.checkin.workout_done      = payload.workout_done
        state.daily_plan.checkin.skipped_exercises = payload.skipped_exercises
        state.daily_plan.checkin.meals_done        = payload.meals_done
        state.daily_plan.checkin.skipped_meals     = payload.skipped_meals

    state.checkin_history[today] = {
        "workout_done":      payload.workout_done,
        "skipped_exercises": payload.skipped_exercises,
        "meals_done":        payload.meals_done,
        "skipped_meals":     payload.skipped_meals,
    }
    save_full(state)
    log.info("checkin.saved", ip=get_remote_address(request), date=today)
    return {"ok": True, "adaptation": None}


# ── Calendar log ──────────────────────────────────────────────────────────────

@router.get("/logs/calendar")
@limiter.limit("60/minute")
async def calendar_logs(request: Request, year: int, month: int):
    """Retorna días del mes con datos de check-in para el calendario."""
    state  = load_state()
    prefix = f"{year}-{month:02d}"
    result: dict[str, dict] = {}

    for date_str, ci in state.checkin_history.items():
        if not date_str.startswith(prefix):
            continue
        meals_list  = ci.get("meals_done") or []
        meals_done  = sum(1 for m in meals_list if m)
        total_meals = len(meals_list)
        result[date_str] = {
            "workout_done": ci.get("workout_done"),
            "meals_done":   meals_done,
            "total_meals":  total_meals,
        }

    return {"days": result}

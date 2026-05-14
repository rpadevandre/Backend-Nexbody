"""Tests del plan engine y endpoints de FormaRuta."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.forma_models import UserProfile
from app.plan_engine import build_daily_plan


# ── Tests unitarios del motor de reglas ───────────────────────────────────────

def _profile(**kwargs) -> UserProfile:
    defaults = dict(
        age=28, gender="mujer", weight_kg=65.0, height_cm=165.0,
        country_code="AR", desired_body_template_id="lean_define",
        current_body_type="mixto", diet_style="omnivoro",
        meals_per_day=4, training_days_per_week=3,
        gym_type="gimnasio", onboarding_complete=True,
    )
    defaults.update(kwargs)
    return UserProfile(**defaults)


def test_plan_has_workout():
    plan = build_daily_plan(_profile())
    assert len(plan.workout) > 0


def test_plan_has_meals():
    plan = build_daily_plan(_profile())
    assert len(plan.meals) > 0


def test_plan_meals_count_matches_profile():
    plan = build_daily_plan(_profile(meals_per_day=3))
    assert len(plan.meals) == 3


def test_plan_all_templates():
    templates = [
        "lean_define", "bulk_hypertrophy", "recomp", "strong", "endurance",
        "femboy_silhouette", "trans_fem_silhouette", "tomboy_silhouette",
        "trans_masc_silhouette", "trans_nb_silhouette",
    ]
    for tid in templates:
        plan = build_daily_plan(_profile(desired_body_template_id=tid))
        assert len(plan.workout) > 0, f"Template {tid} sin workout"


def test_plan_has_warmup():
    plan = build_daily_plan(_profile())
    assert len(plan.warm_up) > 0


def test_plan_title_contains_date():
    plan = build_daily_plan(_profile())
    assert "/" in plan.title  # contiene la fecha dd/mm


def test_plan_gym_where_includes_city():
    plan = build_daily_plan(_profile(city_or_area="Palermo"))
    assert "Palermo" in plan.gym_where


# ── Tests de la API HTTP ──────────────────────────────────────────────────────

def test_body_templates_endpoint(client: TestClient):
    r = client.get("/v1/forma/body-templates")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert len(data["items"]) >= 5


def test_profile_put_onboarding(client: TestClient):
    payload = {
        "age": 25, "gender": "mujer", "weight_kg": 60.0, "height_cm": 162.0,
        "country_code": "AR", "desired_body_template_id": "lean_define",
        "current_body_type": "mixto", "diet_style": "omnivoro",
        "meals_per_day": 4, "training_days_per_week": 3,
        "gym_type": "gimnasio", "onboarding_complete": True,
    }
    r = client.put("/v1/forma/profile", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["daily_plan"] is not None
    assert len(data["daily_plan"]["workout"]) > 0


def test_get_daily_plan_after_onboarding(client: TestClient):
    payload = {
        "age": 30, "gender": "hombre", "weight_kg": 80.0, "height_cm": 178.0,
        "country_code": "MX", "desired_body_template_id": "bulk_hypertrophy",
        "current_body_type": "ectomorph", "diet_style": "omnivoro",
        "meals_per_day": 5, "training_days_per_week": 4,
        "gym_type": "gimnasio", "onboarding_complete": True,
    }
    client.put("/v1/forma/profile", json=payload)
    r = client.get("/v1/forma/plan/daily")
    assert r.status_code == 200
    plan = r.json()
    assert "workout" in plan
    assert "meals" in plan


def test_get_plan_without_onboarding(client: TestClient):
    r = client.get("/v1/forma/plan/daily")
    assert r.status_code == 400

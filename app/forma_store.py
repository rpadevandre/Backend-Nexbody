"""Persistencia local JSON para perfil y plan (un usuario por instalación demo)."""
from __future__ import annotations

import json
from pathlib import Path

from app.forma_models import DailyPlan, UserProfile, UserState

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "forma_user.json"


def _ensure_dir() -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_state() -> UserState:
    _ensure_dir()
    if not DATA_PATH.exists():
        return UserState()
    try:
        raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        return UserState.model_validate(raw)
    except Exception:
        return UserState()


def save_state(state: UserState) -> None:
    _ensure_dir()
    DATA_PATH.write_text(
        json.dumps(state.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def save_profile(profile: UserProfile) -> UserState:
    state = load_state()
    state.profile = profile
    save_state(state)
    return state


def save_daily_plan(plan: DailyPlan) -> UserState:
    state = load_state()
    state.daily_plan = plan
    save_state(state)
    return state


def save_full(state: UserState) -> None:
    save_state(state)

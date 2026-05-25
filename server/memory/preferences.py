import json
import os
from pathlib import Path

from pydantic import BaseModel


class UserPreferenceWeights(BaseModel):
    walking_sensitivity: float = 1.0
    crowd_sensitivity: float = 1.0
    transfer_sensitivity: float = 1.0
    recovery_affinity: float = 1.0


def update_weights_from_feedback(
    current: UserPreferenceWeights,
    liked_route: bool,
    reason: str | None = None,
) -> UserPreferenceWeights:
    adjustment = -0.05 if liked_route else 0.08
    recovery_adjustment = 0.06 if liked_route else -0.04
    if reason and "recovery" in reason.lower():
        recovery_adjustment += 0.04 if liked_route else -0.02

    return UserPreferenceWeights(
        walking_sensitivity=_clamp(current.walking_sensitivity + adjustment),
        crowd_sensitivity=_clamp(current.crowd_sensitivity + adjustment),
        transfer_sensitivity=_clamp(current.transfer_sensitivity + adjustment),
        recovery_affinity=_clamp(current.recovery_affinity + recovery_adjustment),
    )


def load_preference_weights() -> UserPreferenceWeights:
    path = _preferences_path()
    if not path.exists():
        return UserPreferenceWeights()

    try:
        return UserPreferenceWeights(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return UserPreferenceWeights()


def save_preference_weights(weights: UserPreferenceWeights) -> None:
    path = _preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(weights.model_dump_json(indent=2), encoding="utf-8")


def record_route_feedback(
    liked_route: bool,
    reason: str | None = None,
) -> UserPreferenceWeights:
    weights = update_weights_from_feedback(
        current=load_preference_weights(),
        liked_route=liked_route,
        reason=reason,
    )
    save_preference_weights(weights)
    return weights


def _preferences_path() -> Path:
    override = os.environ.get("HYS_PREFERENCES_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "preferences.json"


def _clamp(value: float) -> float:
    return round(max(0.2, min(2.0, value)), 2)

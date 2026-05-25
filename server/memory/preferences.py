from pydantic import BaseModel


class UserPreferenceWeights(BaseModel):
    walking_sensitivity: float = 1.0
    crowd_sensitivity: float = 1.0
    transfer_sensitivity: float = 1.0
    recovery_affinity: float = 1.0


def update_weights_from_feedback(
    current: UserPreferenceWeights,
    liked_route: bool,
) -> UserPreferenceWeights:
    adjustment = 0.05 if liked_route else -0.05
    return UserPreferenceWeights(
        walking_sensitivity=max(0.1, current.walking_sensitivity + adjustment),
        crowd_sensitivity=max(0.1, current.crowd_sensitivity + adjustment),
        transfer_sensitivity=max(0.1, current.transfer_sensitivity + adjustment),
        recovery_affinity=max(0.1, current.recovery_affinity + adjustment),
    )


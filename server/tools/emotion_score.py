from api.schemas import Constraints, EmotionCost, EmotionState, RouteCandidate
from memory.preferences import UserPreferenceWeights
from tools.landmark_emotion_prior import get_landmark_emotion_prior


def score_route_for_emotion(
    route: RouteCandidate,
    emotion: EmotionState,
    constraints: Constraints | None = None,
    preference_weights: UserPreferenceWeights | None = None,
) -> EmotionCost:
    weights = preference_weights or UserPreferenceWeights()
    fatigue_cost = _fatigue_cost(route, emotion)
    walking_cost = round(_walking_cost(route, emotion) * weights.walking_sensitivity)
    crowd_cost = round(_crowd_cost(route, emotion) * weights.crowd_sensitivity)
    transfer_cost = round(_transfer_cost(route, emotion) * weights.transfer_sensitivity)
    time_pressure_cost = _time_pressure_cost(route, emotion, constraints)
    familiarity_bonus = _familiarity_bonus(route)
    recovery_bonus = round(_recovery_bonus(route, emotion) * weights.recovery_affinity)

    total = (
        fatigue_cost
        + walking_cost
        + crowd_cost
        + transfer_cost
        + time_pressure_cost
        - familiarity_bonus
        - recovery_bonus
    )
    total = max(0, min(100, total))
    comfort = 100 - total

    return EmotionCost(
        route_id=route.id,
        fatigue_cost=fatigue_cost,
        walking_cost=walking_cost,
        crowd_cost=crowd_cost,
        transfer_cost=transfer_cost,
        time_pressure_cost=time_pressure_cost,
        familiarity_bonus=familiarity_bonus,
        recovery_bonus=recovery_bonus,
        total_emotional_cost=total,
        comfort_score=comfort,
        stress_score=total,
        reasons=_reasons(
            route=route,
            emotion=emotion,
            walking_cost=walking_cost,
            crowd_cost=crowd_cost,
            transfer_cost=transfer_cost,
            recovery_bonus=recovery_bonus,
        ),
    )


def _fatigue_cost(route: RouteCandidate, emotion: EmotionState) -> int:
    if emotion.primary == "tired":
        base = 12
        weight = 0.7
    elif emotion.primary == "anxious":
        base = 7
        weight = 0.5
    else:
        base = 4
        weight = 0.3

    adjustment = _clamp_adjustment(
        sum(prior.fatigue_modifier for prior, _tags in _route_emotion_context(route)),
        low=-6,
        high=8,
    )
    return max(0, base + round(adjustment * weight))


def _walking_cost(route: RouteCandidate, emotion: EmotionState) -> int:
    base_walking = route.walking_minutes
    if route.real_duration_minutes and emotion.primary == "tired":
        base_walking += max(0, route.walking_minutes - 12) // 2

    multiplier = {
        "low": 1.05 if emotion.primary == "tired" else 0.9,
        "medium": 0.65,
        "high": 0.45,
    }.get(emotion.walking_tolerance, 0.65)
    return round(base_walking * multiplier)


def _crowd_cost(route: RouteCandidate, emotion: EmotionState) -> int:
    base = {"low": 1, "medium": 6, "high": 14}.get(route.crowd_level, 6)
    multiplier = {
        "low": 1.4,
        "medium": 0.8,
        "high": 0.5,
    }.get(emotion.crowd_tolerance, 0.8)

    segment_penalty = 0
    for prior, tags in _route_emotion_context(route):
        segment_penalty += prior.crowd_modifier
        segment_penalty += max(0, prior.noise_modifier)
        if "crowded" in prior.emotion_tags or "crowded" in tags:
            segment_penalty += 2
        if "stressful" in prior.emotion_tags or "stressful" in tags:
            segment_penalty += 2
        if "high_noise" in prior.emotion_tags or "high_noise" in tags:
            segment_penalty += 1

    return max(0, round(base * multiplier) + segment_penalty)


def _transfer_cost(route: RouteCandidate, emotion: EmotionState) -> int:
    per_transfer = {
        "low": 10 if emotion.primary in {"tired", "anxious"} else 8,
        "medium": 6 if emotion.primary == "tired" else 5,
        "high": 3,
    }.get(emotion.transfer_tolerance, 5)
    fare_cost = 0
    if route.fare and route.fare >= 2000:
        fare_cost = 2
    return route.transfer_count * per_transfer + fare_cost


def _time_pressure_cost(
    route: RouteCandidate,
    emotion: EmotionState,
    constraints: Constraints | None,
) -> int:
    duration = route.real_duration_minutes or route.estimated_duration_minutes or route.estimated_minutes

    if emotion.time_pressure_tolerance == "high":
        return round(duration * 0.75)

    if constraints and constraints.deadline:
        soft_limit = 60
        return max(0, duration - soft_limit) // 2

    return max(0, duration - 75) // 3


def _familiarity_bonus(route: RouteCandidate) -> int:
    bonus = 0
    for prior, tags in _route_emotion_context(route):
        if "familiar" in prior.emotion_tags or "familiar" in tags:
            bonus += 4
    return min(12, bonus)


def _recovery_bonus(route: RouteCandidate, emotion: EmotionState) -> int:
    bonus = 0
    for prior, tags in _route_emotion_context(route):
        if "recovery" in prior.emotion_tags or "recovery" in tags:
            bonus += prior.recovery_bonus
    for stop in route.stops:
        if stop.category == "recovery" or "recovery" in stop.emotion_tags:
            bonus += 6

    if emotion.recovery_need == "high":
        bonus += 4
    elif emotion.recovery_need == "low":
        bonus = round(bonus * 0.4)

    return min(18, bonus)


def _route_emotion_context(route: RouteCandidate):
    for segment in route.segments:
        yield get_landmark_emotion_prior(segment.landmark_type), segment.emotion_tags
    for stop in route.stops:
        yield get_landmark_emotion_prior(stop.landmark_type), stop.emotion_tags


def _clamp_adjustment(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _reasons(
    route: RouteCandidate,
    emotion: EmotionState,
    walking_cost: int,
    crowd_cost: int,
    transfer_cost: int,
    recovery_bonus: int,
) -> list[str]:
    reasons = []

    if emotion.primary == "tired":
        reasons.append("Fatigue increases the cost of walking and crowded segments.")
    if route.real_duration_minutes:
        reasons.append("Real route duration is included in the emotional cost.")
    if walking_cost <= 18:
        reasons.append("Walking load stays within a tolerable range.")
    else:
        reasons.append("Walking load is high for the current emotion state.")
    if crowd_cost >= 16:
        reasons.append("Crowd exposure is a major stress source on this route.")
    else:
        reasons.append("Crowd exposure is manageable.")
    if transfer_cost <= 5:
        reasons.append("Transfer count stays low.")
    elif route.route_mode == "transit":
        reasons.append("Transit transfers and fare add practical friction.")
    if recovery_bonus > 0:
        reasons.append("Calm or recovery-friendly landmarks reduce emotional cost.")

    return reasons

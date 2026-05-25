from api.schemas import EmotionScore, EmotionState, RouteCandidate


def score_route_for_emotion(
    route: RouteCandidate,
    emotion: EmotionState,
) -> EmotionScore:
    comfort = 82
    reasons = ["Low transfer count", "Keeps the route sequence simple"]

    if emotion.walking_tolerance == "low" and route.walking_minutes > 20:
        comfort -= 12
        reasons.append("Walking time is a little high for a tired day")

    if emotion.crowd_tolerance == "low" and route.crowd_level == "high":
        comfort -= 18
        reasons.append("Crowd level is too high for the current emotion state")
    elif emotion.crowd_tolerance == "low":
        reasons.append("Avoids the most crowded route option")

    if emotion.recovery_need == "high":
        reasons.append("Leaves room for a recovery stop if needed")

    comfort = max(0, min(100, comfort))
    return EmotionScore(
        comfort_score=comfort,
        stress_score=100 - comfort,
        reasons=reasons,
    )


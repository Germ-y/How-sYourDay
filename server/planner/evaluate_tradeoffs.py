from dataclasses import dataclass

from api.schemas import (
    Constraints,
    EmotionCost,
    EmotionState,
    RouteCandidate,
    Tradeoff,
    TradeoffCostDelta,
)


@dataclass(frozen=True)
class TradeoffEvaluation:
    selected_route: RouteCandidate
    selected_score: EmotionCost
    tradeoffs: list[Tradeoff]
    tradeoff_summaries: list[str]
    fallback_used: bool


def evaluate_tradeoffs(
    routes: list[RouteCandidate],
    emotion_scores: list[EmotionCost],
    constraints: Constraints,
    emotion: EmotionState,
) -> TradeoffEvaluation:
    score_by_route = {score.route_id: score for score in emotion_scores}
    feasible_routes = [
        route for route in routes if _meets_deadline(route, constraints)
    ]
    fallback_used = False

    if not feasible_routes:
        fallback_used = True
        feasible_routes = sorted(routes, key=lambda route: route.estimated_minutes)[:1]

    selected_route = min(
        feasible_routes,
        key=lambda route: _planner_objective(route, score_by_route[route.id], emotion),
    )
    selected_score = score_by_route[selected_route.id]
    rejected_route = _representative_rejected_route(
        routes=routes,
        selected_route=selected_route,
        emotion_scores=emotion_scores,
        emotion=emotion,
    )

    tradeoffs = []
    if rejected_route is not None:
        tradeoffs.append(
            _build_tradeoff(
                selected_route=selected_route,
                rejected_route=rejected_route,
                selected_score=selected_score,
                rejected_score=score_by_route[rejected_route.id],
                emotion=emotion,
            )
        )

    summaries = [tradeoff.reason for tradeoff in tradeoffs]
    if fallback_used:
        summaries.append(
            "No route satisfies the deadline, so the least-late route is selected."
        )

    return TradeoffEvaluation(
        selected_route=selected_route,
        selected_score=selected_score,
        tradeoffs=tradeoffs,
        tradeoff_summaries=summaries,
        fallback_used=fallback_used,
    )


def _planner_objective(
    route: RouteCandidate,
    score: EmotionCost,
    emotion: EmotionState,
) -> float:
    if emotion.time_pressure_tolerance == "high":
        return score.total_emotional_cost + route.estimated_minutes * 3.0

    if emotion.primary == "tired":
        return score.total_emotional_cost + route.estimated_minutes * 0.2

    return score.total_emotional_cost + route.estimated_minutes * 0.6


def _meets_deadline(route: RouteCandidate, constraints: Constraints) -> bool:
    if not constraints.deadline or not constraints.must_arrive_before_deadline:
        return True

    minutes_available = _minutes_until_deadline(constraints.deadline)
    if minutes_available is None:
        return True

    return route.estimated_minutes <= minutes_available


def _minutes_until_deadline(deadline: str) -> int | None:
    try:
        hour_text, minute_text = deadline.split(":", maxsplit=1)
        deadline_minutes = int(hour_text) * 60 + int(minute_text)
    except ValueError:
        return None

    start_minutes = 14 * 60
    return max(0, deadline_minutes - start_minutes)


def _representative_rejected_route(
    routes: list[RouteCandidate],
    selected_route: RouteCandidate,
    emotion_scores: list[EmotionCost],
    emotion: EmotionState,
) -> RouteCandidate | None:
    others = [route for route in routes if route.id != selected_route.id]
    if not others:
        return None

    score_by_route = {score.route_id: score for score in emotion_scores}
    if emotion.time_pressure_tolerance == "high":
        return min(others, key=lambda route: score_by_route[route.id].total_emotional_cost)

    return min(others, key=lambda route: route.estimated_minutes)


def _build_tradeoff(
    selected_route: RouteCandidate,
    rejected_route: RouteCandidate,
    selected_score: EmotionCost,
    rejected_score: EmotionCost,
    emotion: EmotionState,
) -> Tradeoff:
    time_delta = selected_route.estimated_minutes - rejected_route.estimated_minutes
    emotional_delta = (
        selected_score.total_emotional_cost - rejected_score.total_emotional_cost
    )

    if emotion.time_pressure_tolerance == "high" and time_delta < 0:
        label = "Faster route over calmer route"
        reason = (
            f"{selected_route.id} saves {abs(time_delta)} minutes, accepting "
            f"{max(0, emotional_delta)} extra emotional cost because time pressure is high."
        )
    elif emotional_delta < 0:
        label = "Calmer route over fastest route"
        reason = (
            f"{selected_route.id} adds {max(0, time_delta)} minutes but lowers "
            f"emotional cost by {abs(emotional_delta)}."
        )
    else:
        label = "Balanced route"
        reason = (
            f"{selected_route.id} is selected because it best balances time and "
            "emotional cost under the current constraints."
        )

    return Tradeoff(
        chosen_option=selected_route.id,
        rejected_option=rejected_route.id,
        reason=reason,
        user_visible_label=label,
        cost_delta=TradeoffCostDelta(
            estimated_minutes=time_delta,
            emotional_cost=emotional_delta,
        ),
    )

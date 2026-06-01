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
        feasible_routes = sorted(routes, key=_route_duration)[:1]

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
            "마감 시간을 완전히 만족하는 route가 없어 가장 덜 늦는 경로를 선택했어요."
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
    duration = _route_duration(route)
    if emotion.time_pressure_tolerance == "high":
        return score.total_emotional_cost * 0.7 + duration * 4.5

    if emotion.primary == "tired":
        return score.total_emotional_cost + duration * 0.2

    return score.total_emotional_cost + duration * 0.6


def _meets_deadline(route: RouteCandidate, constraints: Constraints) -> bool:
    if not constraints.deadline or not constraints.must_arrive_before_deadline:
        return True

    minutes_available = _minutes_until_deadline(constraints.deadline)
    if minutes_available is None:
        return True

    return _route_duration(route) <= minutes_available


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

    return min(others, key=_route_duration)


def _build_tradeoff(
    selected_route: RouteCandidate,
    rejected_route: RouteCandidate,
    selected_score: EmotionCost,
    rejected_score: EmotionCost,
    emotion: EmotionState,
) -> Tradeoff:
    time_delta = _route_duration(selected_route) - _route_duration(rejected_route)
    emotional_delta = (
        selected_score.total_emotional_cost - rejected_score.total_emotional_cost
    )

    if emotion.time_pressure_tolerance == "high" and time_delta < 0:
        label = "편안함보다 도착 시간을 우선했어요"
        reason = (
            f"{_route_name(selected_route)}는 {_route_name(rejected_route)}보다 "
            f"{abs(time_delta)}분 빠릅니다. 시간이 촉박해서 감정 비용 "
            f"{max(0, emotional_delta)}점을 감수하고 빠른 route를 골랐어요."
        )
    elif emotional_delta < 0:
        label = "속도보다 감정 비용을 낮췄어요"
        reason = (
            f"{_route_name(selected_route)}는 {_route_name(rejected_route)}보다 "
            f"{max(0, time_delta)}분 더 걸리지만 감정 비용을 "
            f"{abs(emotional_delta)}점 낮춰요."
        )
    else:
        label = "시간과 컨디션을 균형 있게 맞췄어요"
        reason = (
            f"{_route_name(selected_route)}가 현재 시간 제약과 감정 비용을 "
            "가장 안정적으로 맞춰서 선택됐어요."
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


def _route_duration(route: RouteCandidate) -> int:
    return (
        route.real_duration_minutes
        or route.estimated_duration_minutes
        or route.estimated_minutes
    )


def _route_name(route: RouteCandidate) -> str:
    if route.provider == "tmap-pedestrian":
        return "Tmap 도보 경로"
    if route.provider == "tmap-transit":
        return "Tmap 대중교통 경로"
    if route.provider == "tmap-mixed":
        return "Tmap 혼합 경로"
    return "추정 fallback 경로"

from api.schemas import (
    Coordinate,
    EmotionCost,
    EmotionScore,
    EmotionZone,
    MapBounds,
    MapMarker,
    MapPolyline,
    MapViewModel,
    OrderedStop,
    PlanResponse,
    Recommendation,
    RouteCandidate,
    TimelineItem,
    TradeoffBadge,
)
from planner.evaluate_tradeoffs import TradeoffEvaluation
from tools.extract_intent import ExtractedIntent


def compose_plan(
    intent: ExtractedIntent,
    routes: list[RouteCandidate],
    evaluation: TradeoffEvaluation,
) -> PlanResponse:
    selected_route = evaluation.selected_route
    selected_score = evaluation.selected_score
    ordered_stops = _ordered_stops(selected_route)
    timeline = _timeline(selected_route)
    recommendations = _recommendations(intent, selected_route)
    map_overlays = _map_view_model(routes, selected_route, evaluation)
    explanation = _explanation(evaluation, selected_score)
    task_labels = ", ".join(task.label.lower() for task in intent.tasks)
    route_label = _route_provider_label(selected_route)

    return PlanResponse(
        summary=(
            f"{task_labels} 일정을 {route_label} 기준으로 조율했어요. "
            f"현재 상태는 {intent.emotion.primary}로 해석했습니다."
        ),
        emotion=intent.emotion,
        constraints=intent.constraints,
        tasks=intent.tasks,
        stops=selected_route.stops,
        routes=routes,
        score=EmotionScore(**selected_score.model_dump()),
        tradeoffs=evaluation.tradeoffs,
        tradeoff_summaries=evaluation.tradeoff_summaries,
        ordered_stops=ordered_stops,
        estimated_timeline=timeline,
        selected_route=selected_route,
        emotional_cost=EmotionCost(**selected_score.model_dump()),
        recommendations=recommendations,
        map_overlays=map_overlays,
        explanation=explanation,
    )


def _ordered_stops(route: RouteCandidate) -> list[OrderedStop]:
    stops = []
    current_minutes = 14 * 60
    travel_step = max(8, _route_duration(route) // max(1, len(route.stops) + 1))

    for stop in route.stops:
        current_minutes += travel_step
        arrival = _format_minutes(current_minutes)
        current_minutes += 10
        departure = _format_minutes(current_minutes)
        stops.append(
            OrderedStop(
                stop_id=stop.id,
                task_kind=stop.category,
                arrival_time=arrival,
                departure_time=departure,
                why_here=_why_stop(stop),
            )
        )

    return stops


def _timeline(route: RouteCandidate) -> list[TimelineItem]:
    items = [
        TimelineItem(
            time="14:00",
            label=f"출발지에서 {_route_provider_label(route)} 경로로 이동을 시작해요.",
            type="depart",
        )
    ]
    for stop in _ordered_stops(route):
        items.append(
            TimelineItem(
                time=stop.arrival_time,
                label=stop.why_here,
                type="task",
            )
        )
    items.append(
        TimelineItem(
            time=_format_minutes(14 * 60 + _route_duration(route)),
            label="최종 목적지에 도착합니다.",
            type="arrive",
        )
    )
    return items


def _recommendations(
    intent: ExtractedIntent,
    selected_route: RouteCandidate,
) -> list[Recommendation]:
    recommendations = []
    has_recovery_stop = any(stop.category == "recovery" for stop in selected_route.stops)

    if has_recovery_stop:
        recommendations.append(
            Recommendation(
                kind="recovery",
                label="회복 지점을 단순 경유지가 아니라 의도적인 쉬는 시간으로 사용해보세요.",
            )
        )
    elif intent.emotion.recovery_need == "high":
        recommendations.append(
            Recommendation(
                kind="recovery",
                label="이동이 부담스럽게 느껴지면 짧은 회복 지점을 추가로 고려하세요.",
            )
        )

    if intent.emotion.time_pressure_tolerance == "high":
        recommendations.append(
            Recommendation(
                kind="time",
                label="시간 압박이 크므로 먼저 도착 안정성을 확보하고, 회복은 이후로 미루는 편이 좋아요.",
            )
        )

    return recommendations


def _map_view_model(
    routes: list[RouteCandidate],
    selected_route: RouteCandidate,
    evaluation: TradeoffEvaluation,
) -> MapViewModel:
    points = _all_points(routes)
    center = _center(points)
    bounds = _bounds(points)

    return MapViewModel(
        center=center,
        fit_bounds=bounds,
        selected_route_id=selected_route.id,
        markers=[
            MapMarker(
                id=f"marker-{stop.id}",
                type="stop",
                lat=stop.lat,
                lng=stop.lng,
                label=stop.name,
                badge=str(index + 1),
            )
            for index, stop in enumerate(selected_route.stops)
        ],
        polylines=[
            MapPolyline(
                id=f"polyline-{route.id}",
                route_id=route.id,
                selected=route.id == selected_route.id,
                points=route.polyline,
                emotion_level=_route_emotion_level(route),
            )
            for route in routes
        ],
        emotion_zones=_emotion_zones(routes),
        tradeoff_badges=[
            TradeoffBadge(
                route_id=tradeoff.chosen_option,
                label=tradeoff.user_visible_label,
                description=tradeoff.reason,
            )
            for tradeoff in evaluation.tradeoffs
        ],
    )


def _explanation(evaluation: TradeoffEvaluation, score: EmotionCost) -> str:
    parts = []
    if evaluation.tradeoffs:
        parts.append(evaluation.tradeoffs[0].reason)
    else:
        parts.append("현재 제약을 가장 안정적으로 만족하는 경로를 선택했어요.")

    parts.append(
        f"comfort score는 {score.comfort_score}, 감정 비용은 "
        f"{score.total_emotional_cost}입니다."
    )

    route = evaluation.selected_route
    if route.provider == "tmap-mixed":
        parts.append("일부 짧은 구간은 Tmap 결과가 없어 추정 이동으로 보완했어요.")
    elif route.provider.startswith("tmap"):
        parts.append(f"{_route_provider_label(route)} 실제 경로를 기준으로 계산했어요.")
    elif route.provider == "mock":
        parts.append("Tmap 경로 생성에 실패해 추정 fallback 경로를 사용했어요.")

    if evaluation.fallback_used:
        parts.append("deadline을 완전히 만족하는 경로가 없어 가장 덜 늦는 경로를 선택했어요.")

    return " ".join(parts)


def _why_stop(stop) -> str:
    if stop.category == "recovery":
        return f"{stop.name}에서 잠깐 회복할 수 있어요."
    return f"{stop.name}에서 {stop.category} 일을 처리합니다."


def _format_minutes(total_minutes: int) -> str:
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"


def _route_duration(route: RouteCandidate) -> int:
    return (
        route.real_duration_minutes
        or route.estimated_duration_minutes
        or route.estimated_minutes
    )


def _route_provider_label(route: RouteCandidate) -> str:
    if route.provider == "tmap-pedestrian":
        return "Tmap 도보"
    if route.provider == "tmap-transit":
        return "Tmap 대중교통"
    if route.provider == "tmap-mixed":
        return "Tmap 혼합"
    return "추정 fallback"


def _all_points(routes: list[RouteCandidate]) -> list[Coordinate]:
    points = []
    for route in routes:
        points.extend(route.polyline)
        points.extend(Coordinate(lat=stop.lat, lng=stop.lng) for stop in route.stops)
    return points or [Coordinate(lat=37.5882, lng=126.9936)]


def _center(points: list[Coordinate]) -> Coordinate:
    return Coordinate(
        lat=sum(point.lat for point in points) / len(points),
        lng=sum(point.lng for point in points) / len(points),
    )


def _bounds(points: list[Coordinate]) -> MapBounds:
    return MapBounds(
        south_west=Coordinate(
            lat=min(point.lat for point in points),
            lng=min(point.lng for point in points),
        ),
        north_east=Coordinate(
            lat=max(point.lat for point in points),
            lng=max(point.lng for point in points),
        ),
    )


def _route_emotion_level(route: RouteCandidate) -> str:
    tags = {tag for segment in route.segments for tag in segment.emotion_tags}
    if "stressful" in tags or "crowded" in tags:
        return "stressful"
    if "recovery" in tags or "calm" in tags:
        return "calm"
    return "neutral"


def _emotion_zones(routes: list[RouteCandidate]) -> list[EmotionZone]:
    zones = []
    for route in routes:
        for index, segment in enumerate(route.segments):
            if "crowded" not in segment.emotion_tags and "stressful" not in segment.emotion_tags:
                continue
            point = route.polyline[min(index, len(route.polyline) - 1)]
            zones.append(
                EmotionZone(
                    id=f"zone-{route.id}-{index}",
                    type="hotspot",
                    emotion_tags=segment.emotion_tags,
                    center=point,
                    radius_meters=120,
                )
            )
    return zones

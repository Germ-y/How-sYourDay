from api.schemas import EmotionState, Location, PoiCandidate, Task
from tools.kakao_local import search_kakao_poi_candidates


MOCK_POIS = {
    "print": [
        PoiCandidate(
            id="poi-print-1",
            provider_id="mock-print-1",
            name="Campus Print Lab",
            category="print",
            landmark_type="university",
            emotion_tags=["familiar", "walkable"],
            lat=37.5889,
            lng=126.9942,
            distance_meters=180,
            source_confidence="mock",
        )
    ],
    "clinic": [
        PoiCandidate(
            id="poi-clinic-1",
            provider_id="mock-clinic-1",
            name="Sungkyun Clinic",
            category="clinic",
            landmark_type="medical",
            emotion_tags=["stressful", "walkable"],
            lat=37.5897,
            lng=126.9954,
            distance_meters=420,
            source_confidence="mock",
        )
    ],
    "recovery": [
        PoiCandidate(
            id="poi-cafe-1",
            provider_id="mock-cafe-1",
            name="Quiet Table Cafe",
            category="recovery",
            landmark_type="cafe",
            emotion_tags=["calm", "recovery", "familiar"],
            lat=37.5876,
            lng=126.9926,
            distance_meters=260,
            source_confidence="mock",
        )
    ],
    "errand": [
        PoiCandidate(
            id="poi-errand-1",
            provider_id="mock-daiso-1",
            name="Daiso Errand Stop",
            category="errand",
            landmark_type="commercial",
            emotion_tags=["practical", "errand"],
            lat=37.5884,
            lng=126.9932,
            distance_meters=320,
            source_confidence="mock",
        )
    ],
}


def search_poi_candidates(
    tasks: list[Task],
    origin: Location,
    destination: Location | None = None,
    user_text: str = "",
) -> list[PoiCandidate]:
    candidates: list[PoiCandidate] = []
    for task in tasks:
        kakao_candidates = _search_task_candidates(task, origin, destination, user_text)
        if kakao_candidates:
            candidates.extend(_with_task_metadata(kakao_candidates, task))
            continue
        if destination is not None:
            continue
        candidates.extend(_with_task_metadata(MOCK_POIS.get(task.kind, MOCK_POIS["recovery"]), task))

    return candidates


def _with_task_metadata(
    candidates: list[PoiCandidate],
    task: Task,
) -> list[PoiCandidate]:
    return [
        candidate.model_copy(
            update={
                "category": task.kind,
                "required": task.required,
            }
        )
        for candidate in candidates
    ]


def _search_task_candidates(
    task: Task,
    origin: Location,
    destination: Location | None,
    user_text: str,
) -> list[PoiCandidate]:
    anchors = _task_search_anchors(task, origin, destination, user_text)
    seen: set[str] = set()

    for anchor in anchors:
        key = f"{anchor.label}:{anchor.lat:.6f}:{anchor.lng:.6f}"
        if key in seen:
            continue
        seen.add(key)
        candidates = search_kakao_poi_candidates([task], anchor, user_text=user_text)
        if candidates:
            route_candidates = _route_relevant_candidates(
                task,
                candidates,
                origin,
                destination,
            )
            if route_candidates:
                return _dedupe_poi_candidates(route_candidates)[: _task_candidate_limit(task)]

    return []


def _task_candidate_limit(task: Task) -> int:
    return 3 if task.kind == "recovery" else 1


def _dedupe_poi_candidates(candidates: list[PoiCandidate]) -> list[PoiCandidate]:
    seen: set[str] = set()
    unique: list[PoiCandidate] = []

    for candidate in candidates:
        key = (
            candidate.provider_id
            or f"{candidate.name}:{candidate.lat:.6f}:{candidate.lng:.6f}"
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)

    return unique


def _task_search_anchors(
    task: Task,
    origin: Location,
    destination: Location | None,
    user_text: str,
) -> list[Location]:
    if destination is not None and task.kind == "recovery":
        midpoint = _route_midpoint(origin, destination)
        if _recovery_task_mentions_destination_area(user_text):
            return [destination, midpoint, origin]
        return [midpoint, origin, destination]

    return [origin]


def _route_relevant_candidates(
    task: Task,
    candidates: list[PoiCandidate],
    origin: Location,
    destination: Location | None,
) -> list[PoiCandidate]:
    if destination is None or task.kind != "recovery":
        return candidates

    filtered = [
        candidate
        for candidate in candidates
        if _is_near_route_corridor(candidate, origin, destination)
    ]
    return filtered


def _route_midpoint(origin: Location, destination: Location) -> Location:
    return Location(
        label="경로 중간 지점",
        lat=(origin.lat + destination.lat) / 2,
        lng=(origin.lng + destination.lng) / 2,
    )


def _is_near_route_corridor(
    candidate: PoiCandidate,
    origin: Location,
    destination: Location,
) -> bool:
    direct = _rough_distance_meters(origin, destination)
    via = _rough_distance_meters(origin, candidate) + _rough_distance_meters(
        candidate,
        destination,
    )
    detour = max(0, via - direct)
    corridor_distance = _distance_to_segment_meters(candidate, origin, destination)
    corridor_radius = max(500, direct * 0.35)
    return detour <= 1800 and corridor_distance <= corridor_radius


def _recovery_task_mentions_destination_area(user_text: str) -> bool:
    text = user_text.replace(" ", "")
    recovery_markers = ["카페", "쉬", "휴식", "과제", "작업", "걷"]
    area_markers = ["가서", "간뒤", "갔다가", "하다가", "주변", "근처", "가는길", "들러"]
    return any(marker in text for marker in recovery_markers) and any(
        marker in text for marker in area_markers
    )


def search_optional_recovery_poi(
    emotion: EmotionState,
    origin: Location,
    existing_stops: list[PoiCandidate],
) -> list[PoiCandidate]:
    if any(stop.category == "recovery" for stop in existing_stops):
        return []
    if not _should_offer_recovery_stop(emotion):
        return []

    task = Task(
        kind="recovery",
        label="Optional recovery stop",
        poi_query="quiet cafe",
        priority=99,
        required=False,
    )
    kakao_candidates = search_kakao_poi_candidates([task], origin)
    if kakao_candidates:
        return kakao_candidates[:1]

    return MOCK_POIS["recovery"][:1]


def _should_offer_recovery_stop(emotion: EmotionState) -> bool:
    return (
        emotion.recovery_need == "high"
        or emotion.primary in {"tired", "anxious"}
        or emotion.crowd_tolerance == "low"
    ) and emotion.time_pressure_tolerance != "high"


def _rough_distance_meters(start, end) -> int:
    lat_meters = (end.lat - start.lat) * 111_000
    lng_meters = (end.lng - start.lng) * 88_000
    return round((lat_meters**2 + lng_meters**2) ** 0.5)


def _distance_to_segment_meters(point, start, end) -> float:
    px, py = _to_local_meters(point, start)
    ex, ey = _to_local_meters(end, start)
    length_sq = ex * ex + ey * ey
    if length_sq == 0:
        return (px * px + py * py) ** 0.5

    t = max(0, min(1, (px * ex + py * ey) / length_sq))
    nearest_x = ex * t
    nearest_y = ey * t
    dx = px - nearest_x
    dy = py - nearest_y
    return (dx * dx + dy * dy) ** 0.5


def _to_local_meters(point, origin) -> tuple[float, float]:
    return (
        (point.lng - origin.lng) * 88_000,
        (point.lat - origin.lat) * 111_000,
    )

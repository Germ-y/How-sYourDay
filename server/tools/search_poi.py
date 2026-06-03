from api.schemas import EmotionState, Location, PoiCandidate, Task
from tools.geocode import search_location_candidates
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
    "photo": [
        PoiCandidate(
            id="poi-photo-1",
            provider_id="mock-photo-1",
            name="Life Four Cut",
            category="photo",
            landmark_type="culture",
            emotion_tags=["social", "photo"],
            lat=37.5886,
            lng=126.9938,
            distance_meters=280,
            source_confidence="mock",
        )
    ],
    "place": [
        PoiCandidate(
            id="poi-place-1",
            provider_id="mock-place-1",
            name="Named waypoint",
            category="place",
            landmark_type="side_street",
            emotion_tags=["waypoint"],
            lat=37.5884,
            lng=126.9934,
            distance_meters=300,
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
    task_key = _task_key(task)
    return [
        candidate.model_copy(
            update={
                "category": task.kind,
                "required": task.required,
                "task_key": task_key,
                "task_priority": task.priority,
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
    if _should_search_as_named_place(task):
        named_place_candidates = _search_named_place_candidates(
            task,
            origin,
            destination,
        )
        if named_place_candidates:
            return named_place_candidates

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


def _should_search_as_named_place(task: Task) -> bool:
    if task.kind == "place":
        return bool(task.poi_query.strip())

    if task.kind != "recovery":
        return False

    query = task.poi_query.strip()
    if not query:
        return False

    compact = query.replace(" ", "")
    generic_exact_terms = {"카페", "커피", "공원", "산책", "식당"}
    generic_contained_terms = ["조용", "쉴", "휴식"]
    if compact in generic_exact_terms or any(
        term in compact for term in generic_contained_terms
    ):
        return False

    named_place_markers = [
        "호수",
        "숲",
        "공원",
        "역",
        "몰",
        "학교",
        "대학교",
        "캠퍼스",
        "도서관",
        "시장",
        "광장",
    ]
    return any(marker in compact for marker in named_place_markers) or len(compact) >= 4


def _search_named_place_candidates(
    task: Task,
    origin: Location,
    destination: Location | None,
) -> list[PoiCandidate]:
    anchors = _task_search_anchors(task, origin, destination, "")
    seen: set[str] = set()
    candidates: list[PoiCandidate] = []

    for anchor in anchors:
        for location in search_location_candidates(
            task.poi_query,
            size=5,
            current_location=anchor,
        ):
            if not _is_relevant_named_place(location, task):
                continue
            key = location.provider_id or f"{location.label}:{location.lat:.6f}:{location.lng:.6f}"
            if key in seen:
                continue
            seen.add(key)
            if (
                destination is not None
                and task.kind != "place"
                and not _is_near_route_corridor(
                    location,
                    origin,
                    destination,
                )
            ):
                continue
            candidates.append(_location_candidate_to_poi(location, task))

    return sorted(
        candidates,
        key=lambda candidate: _named_place_score(candidate, task),
        reverse=True,
    )[: _task_candidate_limit(task)]


def _is_relevant_named_place(location, task: Task) -> bool:
    query = _normalize_text(task.poi_query)
    label = _normalize_text(location.label)
    category = _normalize_text(
        " ".join(
            value
            for value in [
                location.category or "",
                location.category_group_name or "",
                location.category_name or "",
            ]
            if value
        )
    )
    combined = f"{label} {category}"

    if query and query not in combined:
        if task.kind != "place" or not _place_query_matches_candidate(task.poi_query, combined):
            return False

    if any(marker in combined for marker in ["축제", "이벤트", "행사"]):
        return False

    if any(
        marker in combined
        for marker in [
            "음식점",
            "카페",
            "도넛",
            "치킨",
            "레스토랑",
            "공연장",
            "연극극장",
            "교차로",
            "도로시설",
        ]
    ):
        return False

    if "호수" in query:
        return any(marker in combined for marker in ["호수", "관광명소", "도보여행"])

    return True


def _named_place_score(candidate: PoiCandidate, task: Task) -> int:
    query = _normalize_text(task.poi_query)
    name = _normalize_text(candidate.name)
    combined = _normalize_text(
        " ".join(
            value
            for value in [
                candidate.name,
                candidate.category_name or "",
                candidate.category_group_name or "",
            ]
            if value
        )
    )
    score = 0

    if query and name == query:
        score += 120
    elif query and name.startswith(query):
        score += 70
    elif query and query in name:
        score += 35

    if task.kind == "place":
        score += 30 * _place_query_match_count(task.poi_query, combined)

    if any(marker in combined for marker in ["호수", "공원", "숲", "관광명소", "도보여행"]):
        score += 50

    distance = candidate.distance_meters or 999_999
    score -= min(30, distance // 100)
    return score


def _location_candidate_to_poi(location, task: Task) -> PoiCandidate:
    landmark_type = _landmark_type_for_location(location)
    return PoiCandidate(
        id=f"poi-location-{task.kind}-{location.provider_id or location.label}",
        provider_id=location.provider_id,
        name=location.label,
        category=task.kind,
        address=location.address,
        category_group_code=location.category_group_code,
        category_group_name=location.category_group_name,
        category_name=location.category_name,
        phone=location.phone,
        place_url=location.place_url,
        landmark_type=landmark_type,
        emotion_tags=_emotion_tags_for_landmark(landmark_type),
        lat=location.lat,
        lng=location.lng,
        distance_meters=location.distance_meters,
        source_confidence=location.source,
        required=task.required,
        task_key=_task_key(task),
        task_priority=task.priority,
    )


def _landmark_type_for_location(location) -> str:
    combined = " ".join(
        value
        for value in [
            location.label,
            location.category or "",
            location.category_group_name or "",
            location.category_name or "",
        ]
        if value
    )
    if any(marker in combined for marker in ["인생네컷", "네컷", "포토부스", "포토이즘", "사진관", "스튜디오"]):
        return "culture"
    if any(marker in combined for marker in ["아파트", "오피스텔", "빌라", "주거시설", "건물", "빌딩"]):
        return "residential"
    if any(marker in combined for marker in ["공원", "숲"]):
        return "park"
    if any(marker in combined for marker in ["호수", "강", "하천"]):
        return "river"
    if any(marker in combined for marker in ["역", "지하철", "교통"]):
        return "transit_hub"
    if any(marker in combined for marker in ["학교", "대학", "교육"]):
        return "university"
    return "side_street"


def _emotion_tags_for_landmark(landmark_type: str) -> list[str]:
    if landmark_type in {"park", "river"}:
        return ["calm", "recovery", "walkable"]
    if landmark_type == "transit_hub":
        return ["crowded", "walkable"]
    if landmark_type == "culture":
        return ["social", "photo", "walkable"]
    if landmark_type == "residential":
        return ["waypoint", "familiar"]
    return ["walkable"]


def _normalize_text(value: str) -> str:
    return value.lower().replace(" ", "")


def _task_candidate_limit(task: Task) -> int:
    return 3


def _task_key(task: Task) -> str:
    query = _normalize_text(task.poi_query or task.label)
    return f"{task.priority}:{task.kind}:{query}"


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
    if destination is not None and task.kind == "place":
        return [_route_midpoint(origin, destination), origin, destination]

    if destination is not None and task.kind == "recovery":
        midpoint = _route_midpoint(origin, destination)
        if _recovery_task_mentions_destination_area(user_text):
            return [destination, midpoint, origin]
        return [midpoint, origin, destination]

    if destination is not None:
        midpoint = _route_midpoint(origin, destination)
        return [midpoint, origin, destination]

    return [origin]


def _route_relevant_candidates(
    task: Task,
    candidates: list[PoiCandidate],
    origin: Location,
    destination: Location | None,
) -> list[PoiCandidate]:
    if destination is None:
        return candidates

    filtered = [
        candidate
        for candidate in candidates
        if _is_near_route_corridor(candidate, origin, destination)
    ]
    return filtered or candidates


def _place_query_matches_candidate(query: str, candidate_combined: str) -> bool:
    return _place_query_match_count(query, candidate_combined) >= 1


def _place_query_match_count(query: str, candidate_combined: str) -> int:
    terms = _place_query_terms(query)
    return sum(1 for term in terms if term in candidate_combined)


def _place_query_terms(query: str) -> list[str]:
    raw_terms = [term for term in query.replace("-", " ").split() if term]
    terms: list[str] = []
    for term in raw_terms:
        normalized = _normalize_text(term)
        without_unit = normalized.rstrip("동호")
        without_digits = "".join(ch for ch in without_unit if not ch.isdigit())
        for candidate in [normalized, without_unit, without_digits]:
            if len(candidate) >= 2 and candidate not in terms:
                terms.append(candidate)
    compact = _normalize_text(query)
    compact_without_digits = "".join(ch for ch in compact if not ch.isdigit()).rstrip("동호")
    if len(compact_without_digits) >= 3 and compact_without_digits not in terms:
        terms.append(compact_without_digits)
    return terms


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

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from api.schemas import Coordinate, Constraints, EmotionState, Location, PoiCandidate
from tools.kakao_local import KAKAO_KEYWORD_SEARCH_URL, _get_env_value
from tools.landmark_emotion_prior import get_landmark_emotion_prior
from tools.llm_waypoint_policy import WaypointPolicy, build_waypoint_policy
from tools.search_poi import MOCK_POIS

CITY_SPEED_METERS_PER_MINUTE = 180
WALKING_SPEED_METERS_PER_MINUTE = 70
DEFAULT_DESTINATION = Location(label="Default destination", lat=37.5826, lng=127.0019)
_WAYPOINT_SEARCH_CACHE: dict[str, list[PoiCandidate]] = {}
_WAYPOINT_SEARCH_CACHE_LIMIT = 120


def find_emotion_waypoints(
    user_text: str,
    emotion: EmotionState,
    constraints: Constraints,
    origin: Location,
    destination: Location | None,
    required_stops: list[PoiCandidate],
) -> list[PoiCandidate]:
    destination_point = destination or DEFAULT_DESTINATION
    if any(stop.category == "recovery" for stop in required_stops):
        return []

    policy = build_waypoint_policy(user_text, emotion, constraints)
    if not policy.allow_optional_waypoints or policy.max_optional_waypoints <= 0:
        return []

    direct_minutes = _rough_minutes(origin, destination_point)
    if _deadline_is_tight(constraints, direct_minutes):
        return []

    candidates = _search_policy_candidates(policy, origin, destination_point)
    filtered = [
        candidate
        for candidate in candidates
        if _within_detour_budget(candidate, origin, destination_point, policy)
    ]
    ranked = sorted(
        filtered,
        key=lambda candidate: _waypoint_score(candidate, origin, destination_point),
        reverse=True,
    )
    return ranked[: policy.max_optional_waypoints]


def _search_policy_candidates(
    policy: WaypointPolicy,
    origin: Location,
    destination: Location,
) -> list[PoiCandidate]:
    api_key = _get_env_value("KAKAO_REST_API_KEY")
    midpoint = _midpoint(origin, destination)
    candidates: list[PoiCandidate] = []

    for query in policy.positive_queries:
        query_candidates = []
        if api_key:
            query_candidates = _search_kakao_waypoints(api_key, query, midpoint)
        if not query_candidates:
            query_candidates = _mock_waypoints(query.landmark_type, midpoint)
        candidates.extend(query_candidates)

    seen = set()
    unique = []
    for candidate in candidates:
        key = candidate.provider_id or candidate.id
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _search_kakao_waypoints(api_key: str, query, midpoint: Coordinate) -> list[PoiCandidate]:
    cache_key = json.dumps(
        {
            "query": query.query,
            "landmark_type": query.landmark_type,
            "lat": round(midpoint.lat, 5),
            "lng": round(midpoint.lng, 5),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    if cache_key in _WAYPOINT_SEARCH_CACHE:
        return _WAYPOINT_SEARCH_CACHE[cache_key]

    request = Request(
        f"{KAKAO_KEYWORD_SEARCH_URL}?{urlencode({
            'query': query.query,
            'x': midpoint.lng,
            'y': midpoint.lat,
            'radius': 1800,
            'sort': 'distance',
            'size': 3,
        })}",
        headers={"Authorization": f"KakaoAK {api_key}"},
    )

    try:
        with urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return []

    documents = payload.get("documents", [])
    if not isinstance(documents, list):
        return []

    prior = get_landmark_emotion_prior(query.landmark_type)
    candidates = [
        PoiCandidate(
            id=f"poi-emotion-{query.landmark_type}-{document.get('id') or index}",
            provider_id=str(document.get("id") or ""),
            name=str(document.get("place_name") or query.query),
            category="recovery",
            landmark_type=query.landmark_type,
            emotion_tags=list(dict.fromkeys([*prior.emotion_tags, "recovery"])),
            lat=_to_float(document.get("y"), midpoint.lat),
            lng=_to_float(document.get("x"), midpoint.lng),
            distance_meters=_to_int_or_none(document.get("distance")),
            source_confidence="kakao",
        )
        for index, document in enumerate(documents)
    ]
    _remember_waypoint_search(cache_key, candidates)
    return candidates


def _remember_waypoint_search(cache_key: str, candidates: list[PoiCandidate]) -> None:
    if len(_WAYPOINT_SEARCH_CACHE) >= _WAYPOINT_SEARCH_CACHE_LIMIT:
        _WAYPOINT_SEARCH_CACHE.pop(next(iter(_WAYPOINT_SEARCH_CACHE)))
    _WAYPOINT_SEARCH_CACHE[cache_key] = candidates


def _mock_waypoints(landmark_type: str, midpoint: Coordinate) -> list[PoiCandidate]:
    if landmark_type == "cafe":
        return MOCK_POIS["recovery"][:1]

    prior = get_landmark_emotion_prior(landmark_type)
    return [
        PoiCandidate(
            id=f"poi-emotion-mock-{landmark_type}",
            provider_id=f"mock-{landmark_type}",
            name=_mock_waypoint_name(landmark_type),
            category="recovery",
            landmark_type=landmark_type,
            emotion_tags=list(dict.fromkeys([*prior.emotion_tags, "recovery"])),
            lat=midpoint.lat + 0.001,
            lng=midpoint.lng - 0.001,
            distance_meters=None,
            source_confidence="mock",
        )
    ]


def _within_detour_budget(
    waypoint: PoiCandidate,
    origin: Coordinate,
    destination: Coordinate,
    policy: WaypointPolicy,
) -> bool:
    direct = _rough_distance_meters(origin, destination)
    via = _rough_distance_meters(origin, waypoint) + _rough_distance_meters(
        waypoint,
        destination,
    )
    detour_meters = max(0, via - direct)
    detour_minutes = detour_meters / CITY_SPEED_METERS_PER_MINUTE
    corridor_distance = _distance_to_segment_meters(waypoint, origin, destination)
    route_radius = max(450, direct * 0.22)
    return (
        detour_minutes <= policy.max_detour_minutes
        and corridor_distance <= route_radius
    )


def _waypoint_score(
    waypoint: PoiCandidate,
    origin: Coordinate,
    destination: Coordinate,
) -> float:
    prior = get_landmark_emotion_prior(waypoint.landmark_type)
    direct = _rough_distance_meters(origin, destination)
    via = _rough_distance_meters(origin, waypoint) + _rough_distance_meters(
        waypoint,
        destination,
    )
    detour = max(0, via - direct)
    calm_bonus = 200 if "calm" in waypoint.emotion_tags else 0
    recovery_bonus = prior.recovery_bonus * 120
    crowd_relief = max(0, -prior.crowd_modifier) * 80
    return recovery_bonus + crowd_relief + calm_bonus - detour


def _deadline_is_tight(constraints: Constraints, direct_minutes: int) -> bool:
    if not constraints.deadline or not constraints.must_arrive_before_deadline:
        return False

    minutes_available = _minutes_until_deadline(constraints.deadline)
    if minutes_available is None:
        return False

    return minutes_available <= direct_minutes + 12


def _minutes_until_deadline(deadline: str) -> int | None:
    try:
        hour_text, minute_text = deadline.split(":", maxsplit=1)
        deadline_minutes = int(hour_text) * 60 + int(minute_text)
    except ValueError:
        return None

    return max(0, deadline_minutes - 14 * 60)


def _rough_minutes(origin: Coordinate, destination: Coordinate) -> int:
    distance = _rough_distance_meters(origin, destination)
    return max(1, round(distance / CITY_SPEED_METERS_PER_MINUTE))


def _rough_distance_meters(start: Coordinate, end: Coordinate) -> int:
    lat_meters = (end.lat - start.lat) * 111_000
    lng_meters = (end.lng - start.lng) * 88_000
    return round((lat_meters**2 + lng_meters**2) ** 0.5)


def _distance_to_segment_meters(
    point: Coordinate,
    start: Coordinate,
    end: Coordinate,
) -> float:
    px, py = _to_local_meters(point, start)
    ex, ey = _to_local_meters(end, start)
    length_sq = ex * ex + ey * ey
    if length_sq == 0:
        return (px * px + py * py) ** 0.5

    t = max(0, min(1, (px * ex + py * ey) / length_sq))
    closest_x = t * ex
    closest_y = t * ey
    return ((px - closest_x) ** 2 + (py - closest_y) ** 2) ** 0.5


def _to_local_meters(point: Coordinate, origin: Coordinate) -> tuple[float, float]:
    return (
        (point.lng - origin.lng) * 88_000,
        (point.lat - origin.lat) * 111_000,
    )


def _midpoint(origin: Coordinate, destination: Coordinate) -> Coordinate:
    return Coordinate(
        lat=(origin.lat + destination.lat) / 2,
        lng=(origin.lng + destination.lng) / 2,
    )


def _mock_waypoint_name(landmark_type: str) -> str:
    return {
        "park": "Calm Pocket Park",
        "library": "Quiet Reading Room",
        "river": "Riverside Walk",
        "side_street": "Quiet Side Street",
        "convenience_store": "Easy Stop Store",
    }.get(landmark_type, "Emotion Friendly Stop")


def _to_float(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _to_int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

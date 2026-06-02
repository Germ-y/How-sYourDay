import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from api.schemas import Coordinate, PoiCandidate, RouteCandidate, RouteSegment
from tools.kakao_local import _get_env_value


DEFAULT_OSRM_BASE_URL = "https://router.project-osrm.org"
DEFAULT_OSRM_PROFILE = "driving"
_GET_JSON_CACHE: dict[str, dict] = {}
_GET_JSON_CACHE_LIMIT = 120


def build_osrm_route_candidates(
    stops: list[PoiCandidate],
    origin: Coordinate,
    destination: Coordinate,
) -> list[RouteCandidate]:
    base_url = _get_osrm_base_url()
    if not base_url:
        return []

    profile = _get_osrm_profile()
    waypoints = [
        Coordinate(lat=origin.lat, lng=origin.lng),
        *[Coordinate(lat=stop.lat, lng=stop.lng) for stop in stops],
        Coordinate(lat=destination.lat, lng=destination.lng),
    ]
    payload = _fetch_osrm_route(base_url, profile, waypoints)
    route = (payload.get("routes") or [{}])[0] if payload else {}
    if not route:
        return []

    duration_minutes = _seconds_to_minutes(_to_float(route.get("duration"), 0))
    distance_meters = round(_to_float(route.get("distance"), 0)) or None
    polyline = _geometry_points(route.get("geometry")) or waypoints
    legs = route.get("legs") or []

    return [
        RouteCandidate(
            id=f"route-osrm-{profile}",
            provider="osrm",
            route_mode=profile,
            stops=stops,
            walking_minutes=_walking_minutes(profile, duration_minutes, distance_meters),
            transfer_count=0,
            crowd_level=_crowd_level(profile),
            estimated_minutes=duration_minutes,
            real_duration_minutes=duration_minutes,
            estimated_duration_minutes=None,
            distance_meters=distance_meters,
            fare=0,
            fallback_reason="OSRM 개발용 경로로 계산했어요.",
            cost_estimate=0,
            polyline=polyline,
            segments=_segments(profile, legs, duration_minutes),
        )
    ]


def _get_osrm_base_url() -> str | None:
    if os.environ.get("HYS_DISABLE_OSRM") == "1":
        return None
    return (_get_env_value("OSRM_BASE_URL") or DEFAULT_OSRM_BASE_URL).rstrip("/")


def _get_osrm_profile() -> str:
    return _get_env_value("OSRM_PROFILE") or DEFAULT_OSRM_PROFILE


def _fetch_osrm_route(
    base_url: str,
    profile: str,
    waypoints: list[Coordinate],
) -> dict | None:
    coordinate_path = ";".join(f"{point.lng:.6f},{point.lat:.6f}" for point in waypoints)
    query = urlencode(
        {
            "overview": "full",
            "geometries": "geojson",
            "steps": "true",
        }
    )
    url = f"{base_url}/route/v1/{quote(profile)}/{coordinate_path}?{query}"
    return _get_json(url)


def _get_json(url: str) -> dict | None:
    if url in _GET_JSON_CACHE:
        return _GET_JSON_CACHE[url]

    request = Request(url, headers={"accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if payload.get("code") != "Ok":
                return None
            _remember_get_json(url, payload)
            return payload
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return None


def _remember_get_json(url: str, payload: dict) -> None:
    if len(_GET_JSON_CACHE) >= _GET_JSON_CACHE_LIMIT:
        _GET_JSON_CACHE.pop(next(iter(_GET_JSON_CACHE)))
    _GET_JSON_CACHE[url] = payload


def _geometry_points(geometry) -> list[Coordinate]:
    if not isinstance(geometry, dict):
        return []
    coordinates = geometry.get("coordinates") or []
    points = []
    for coordinate in coordinates:
        if not isinstance(coordinate, list) or len(coordinate) < 2:
            continue
        points.append(Coordinate(lat=_to_float(coordinate[1], 0), lng=_to_float(coordinate[0], 0)))
    return points


def _segments(profile: str, legs: list[dict], fallback_minutes: int) -> list[RouteSegment]:
    if not legs:
        return [_segment(profile, fallback_minutes)]
    return [
        _segment(profile, _seconds_to_minutes(_to_float(leg.get("duration"), 0)))
        for leg in legs
    ]


def _segment(profile: str, minutes: int) -> RouteSegment:
    if profile in {"foot", "walking", "walk"}:
        return RouteSegment(
            mode="walk",
            minutes=minutes,
            landmark_type="side_street",
            emotion_tags=["walkable"],
        )
    if profile in {"bike", "bicycle", "cycling"}:
        return RouteSegment(
            mode="bike",
            minutes=minutes,
            landmark_type="side_street",
            emotion_tags=["walkable"],
        )
    return RouteSegment(
        mode="drive-dev",
        minutes=minutes,
        landmark_type="main_road",
        emotion_tags=["high_noise"],
    )


def _walking_minutes(profile: str, duration_minutes: int, distance_meters: int | None) -> int:
    if profile in {"foot", "walking", "walk"}:
        return duration_minutes
    if profile in {"bike", "bicycle", "cycling"}:
        return max(2, min(duration_minutes, round((distance_meters or 0) / 180)))
    return max(2, min(12, duration_minutes))


def _crowd_level(profile: str) -> str:
    if profile in {"foot", "walking", "walk", "bike", "bicycle", "cycling"}:
        return "low"
    return "medium"


def _seconds_to_minutes(seconds: float) -> int:
    return max(1, round(seconds / 60))


def _to_float(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback

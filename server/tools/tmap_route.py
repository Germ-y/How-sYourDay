import json
import os
from dataclasses import dataclass
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from api.schemas import Coordinate, PoiCandidate, RouteCandidate, RouteSegment
from tools.kakao_local import _get_env_value


TMAP_PEDESTRIAN_URL = "https://apis.openapi.sk.com/tmap/routes/pedestrian"
TMAP_TRANSIT_URL = "https://apis.openapi.sk.com/transit/routes"


@dataclass(frozen=True)
class TmapLegResult:
    duration_minutes: int
    walking_minutes: int
    transfer_count: int
    distance_meters: int | None
    fare: int | None
    polyline: list[Coordinate]
    segments: list[RouteSegment]


def build_tmap_route_candidates(
    stops: list[PoiCandidate],
    origin: Coordinate,
    destination: Coordinate,
) -> list[RouteCandidate]:
    app_key = _get_tmap_app_key()
    if not app_key:
        return []

    waypoints = [
        Coordinate(lat=origin.lat, lng=origin.lng),
        *[Coordinate(lat=stop.lat, lng=stop.lng) for stop in stops],
        Coordinate(lat=destination.lat, lng=destination.lng),
    ]
    candidates: list[RouteCandidate] = []

    pedestrian_legs = _build_legs(app_key, waypoints, _fetch_pedestrian_leg)
    if pedestrian_legs:
        candidates.append(_compose_route("route-tmap-walk", "tmap-pedestrian", "walk", stops, pedestrian_legs))

    transit_legs = _build_legs(app_key, waypoints, _fetch_transit_leg)
    if transit_legs:
        candidates.append(_compose_route("route-tmap-transit", "tmap-transit", "transit", stops, transit_legs))

    return candidates


def _get_tmap_app_key() -> str | None:
    if os.environ.get("HYS_DISABLE_TMAP") == "1":
        return None
    return _get_env_value("TMAP_APP_KEY")


def _build_legs(app_key: str, waypoints: list[Coordinate], fetcher) -> list[TmapLegResult]:
    legs = []
    for start, end in zip(waypoints, waypoints[1:]):
        leg = fetcher(app_key, start, end)
        if not leg:
            return []
        legs.append(leg)
    return legs


def _fetch_pedestrian_leg(
    app_key: str,
    start: Coordinate,
    end: Coordinate,
) -> TmapLegResult | None:
    body = {
        "startX": start.lng,
        "startY": start.lat,
        "endX": end.lng,
        "endY": end.lat,
        "startName": quote("출발지"),
        "endName": quote("도착지"),
        "reqCoordType": "WGS84GEO",
        "resCoordType": "WGS84GEO",
        "searchOption": "0",
        "sort": "custom",
    }
    payload = _post_json(
        f"{TMAP_PEDESTRIAN_URL}?{urlencode({'version': 1})}",
        app_key,
        body,
    )
    if not payload:
        return None

    features = payload.get("features", [])
    points = _feature_points(features)
    properties = _first_properties(features)
    duration_seconds = _to_int(properties.get("totalTime"), 0) or _sum_feature_property(features, "time")
    distance = _to_int(properties.get("totalDistance"), 0) or _sum_feature_property(features, "distance")

    return TmapLegResult(
        duration_minutes=_seconds_to_minutes(duration_seconds),
        walking_minutes=_seconds_to_minutes(duration_seconds),
        transfer_count=0,
        distance_meters=distance or None,
        fare=0,
        polyline=points or [start, end],
        segments=[
            RouteSegment(
                mode="walk",
                minutes=_seconds_to_minutes(duration_seconds),
                landmark_type="side_street",
                emotion_tags=["walkable"],
            )
        ],
    )


def _fetch_transit_leg(
    app_key: str,
    start: Coordinate,
    end: Coordinate,
) -> TmapLegResult | None:
    payload = _post_json(
        TMAP_TRANSIT_URL,
        app_key,
        {
            "startX": str(start.lng),
            "startY": str(start.lat),
            "endX": str(end.lng),
            "endY": str(end.lat),
            "count": 1,
            "lang": 0,
            "format": "json",
        },
    )
    itineraries = (
        payload.get("metaData", {})
        .get("plan", {})
        .get("itineraries", [])
        if payload
        else []
    )
    if not itineraries:
        return None

    itinerary = itineraries[0]
    legs = itinerary.get("legs", [])
    points = _transit_points(legs)
    duration_seconds = _to_int(itinerary.get("totalTime"), 0)
    walking_seconds = _to_int(itinerary.get("totalWalkTime"), 0)
    transfer_count = _to_int(itinerary.get("transferCount"), 0)
    fare = (
        itinerary.get("fare", {})
        .get("regular", {})
        .get("totalFare")
    )

    return TmapLegResult(
        duration_minutes=_seconds_to_minutes(duration_seconds),
        walking_minutes=_seconds_to_minutes(walking_seconds),
        transfer_count=transfer_count,
        distance_meters=_to_int(itinerary.get("totalDistance"), 0) or None,
        fare=_to_int(fare, 0) or None,
        polyline=points or [start, end],
        segments=_transit_segments(legs),
    )


def _post_json(url: str, app_key: str, body: dict) -> dict | None:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "appKey": app_key,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=4) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return None


def _compose_route(
    route_id: str,
    provider: str,
    route_mode: str,
    stops: list[PoiCandidate],
    legs: list[TmapLegResult],
) -> RouteCandidate:
    duration = sum(leg.duration_minutes for leg in legs)
    walking = sum(leg.walking_minutes for leg in legs)
    transfer_count = sum(leg.transfer_count for leg in legs)
    distance = sum(leg.distance_meters or 0 for leg in legs) or None
    fare = sum(leg.fare or 0 for leg in legs) or None
    polyline = [point for leg in legs for point in leg.polyline]
    segments = [segment for leg in legs for segment in leg.segments]

    return RouteCandidate(
        id=route_id,
        provider=provider,
        route_mode=route_mode,
        stops=stops,
        walking_minutes=walking,
        transfer_count=transfer_count,
        crowd_level="medium" if transfer_count <= 1 else "high",
        estimated_minutes=duration,
        real_duration_minutes=duration,
        estimated_duration_minutes=None,
        distance_meters=distance,
        fare=fare,
        fallback_reason=None,
        cost_estimate=fare,
        polyline=polyline,
        segments=segments,
    )


def _feature_points(features: list[dict]) -> list[Coordinate]:
    points = []
    for feature in features:
        geometry = feature.get("geometry", {})
        coordinates = geometry.get("coordinates", [])
        if geometry.get("type") == "LineString":
            points.extend(_coordinates_to_points(coordinates))
    return points


def _first_properties(features: list[dict]) -> dict:
    for feature in features:
        properties = feature.get("properties")
        if isinstance(properties, dict):
            return properties
    return {}


def _sum_feature_property(features: list[dict], key: str) -> int:
    return sum(_to_int(feature.get("properties", {}).get(key), 0) for feature in features)


def _transit_points(legs: list[dict]) -> list[Coordinate]:
    points = []
    for leg in legs:
        pass_shape = leg.get("passShape", {})
        if isinstance(pass_shape, dict):
            points.extend(_linestring_to_points(pass_shape.get("linestring")))
        for step in leg.get("steps", []) or []:
            points.extend(_linestring_to_points(step.get("linestring")))
    return points


def _transit_segments(legs: list[dict]) -> list[RouteSegment]:
    segments = []
    for leg in legs:
        mode = str(leg.get("mode", "TRANSIT")).lower()
        minutes = _seconds_to_minutes(_to_int(leg.get("sectionTime"), 0))
        if mode == "walk":
            landmark_type = "side_street"
            tags = ["walkable"]
        else:
            landmark_type = "transit_hub"
            tags = ["crowded"]
        segments.append(
            RouteSegment(
                mode=mode,
                minutes=minutes,
                landmark_type=landmark_type,
                emotion_tags=tags,
            )
        )
    return segments or [
        RouteSegment(
            mode="transit",
            minutes=0,
            landmark_type="transit_hub",
            emotion_tags=["crowded"],
        )
    ]


def _linestring_to_points(linestring: str | None) -> list[Coordinate]:
    if not linestring:
        return []
    points = []
    for token in linestring.replace("|", " ").split():
        if "," not in token:
            continue
        lng, lat = token.split(",", 1)
        points.append(Coordinate(lat=_to_float(lat), lng=_to_float(lng)))
    return points


def _coordinates_to_points(coordinates: list) -> list[Coordinate]:
    points = []
    for coordinate in coordinates:
        if not isinstance(coordinate, list) or len(coordinate) < 2:
            continue
        points.append(Coordinate(lat=_to_float(coordinate[1]), lng=_to_float(coordinate[0])))
    return points


def _seconds_to_minutes(seconds: int) -> int:
    return max(1, round(seconds / 60))


def _to_int(value, fallback: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

from api.schemas import Coordinate, PoiCandidate, RouteCandidate, RouteSegment
from tools.tmap_route import build_tmap_route_candidates


DEFAULT_ORIGIN = Coordinate(lat=37.5882, lng=126.9936)
DEFAULT_DESTINATION = Coordinate(lat=37.5826, lng=127.0019)


def build_route_candidates(
    stops: list[PoiCandidate],
    origin: Coordinate | None = None,
    destination: Coordinate | None = None,
) -> list[RouteCandidate]:
    origin_point = origin or DEFAULT_ORIGIN
    destination_point = destination or DEFAULT_DESTINATION
    tmap_routes = build_tmap_route_candidates(
        stops=stops,
        origin=origin_point,
        destination=destination_point,
    )
    polyline = [
        Coordinate(lat=origin_point.lat, lng=origin_point.lng),
        *[Coordinate(lat=stop.lat, lng=stop.lng) for stop in stops],
        Coordinate(lat=destination_point.lat, lng=destination_point.lng),
    ]

    primary = RouteCandidate(
        id="route-low-stress",
        provider="mock",
        route_mode="mock",
        stops=stops,
        walking_minutes=14 + len(stops) * 3,
        transfer_count=1 if len(stops) > 1 else 0,
        crowd_level="medium",
        estimated_minutes=34 + len(stops) * 8,
        real_duration_minutes=None,
        estimated_duration_minutes=34 + len(stops) * 8,
        distance_meters=1200 + len(stops) * 450,
        fare=None,
        fallback_reason="Tmap route provider is not connected for this candidate.",
        cost_estimate=None,
        polyline=polyline,
        segments=[
            RouteSegment(
                mode="walk",
                minutes=8,
                landmark_type="side_street",
                emotion_tags=["calm", "walkable"],
            ),
            RouteSegment(
                mode="transit",
                minutes=24,
                landmark_type="university",
                emotion_tags=["familiar", "walkable"],
            ),
        ],
    )
    faster = RouteCandidate(
        id="route-faster",
        provider="mock",
        route_mode="mock",
        stops=stops,
        walking_minutes=20 + len(stops) * 4,
        transfer_count=2 if len(stops) > 1 else 1,
        crowd_level="high",
        estimated_minutes=26 + len(stops) * 7,
        real_duration_minutes=None,
        estimated_duration_minutes=26 + len(stops) * 7,
        distance_meters=1000 + len(stops) * 380,
        fare=None,
        fallback_reason="Tmap route provider is not connected for this candidate.",
        cost_estimate=None,
        polyline=polyline,
        segments=[
            RouteSegment(
                mode="walk",
                minutes=10,
                landmark_type="main_road",
                emotion_tags=["high_noise", "walkable"],
            ),
            RouteSegment(
                mode="transit",
                minutes=18,
                landmark_type="transit_hub",
                emotion_tags=["crowded", "stressful", "high_noise"],
            ),
        ],
    )
    recovery_friendly = RouteCandidate(
        id="route-recovery-friendly",
        provider="mock",
        route_mode="mock",
        stops=stops,
        walking_minutes=16 + len(stops) * 3,
        transfer_count=1 if len(stops) > 1 else 0,
        crowd_level="low",
        estimated_minutes=42 + len(stops) * 9,
        real_duration_minutes=None,
        estimated_duration_minutes=42 + len(stops) * 9,
        distance_meters=1500 + len(stops) * 520,
        fare=None,
        fallback_reason="Tmap route provider is not connected for this candidate.",
        cost_estimate=None,
        polyline=polyline,
        segments=[
            RouteSegment(
                mode="walk",
                minutes=9,
                landmark_type="park",
                emotion_tags=["calm", "recovery", "walkable"],
            ),
            RouteSegment(
                mode="walk",
                minutes=7,
                landmark_type="side_street",
                emotion_tags=["calm", "walkable"],
            ),
        ],
    )

    return [*tmap_routes, primary, faster, recovery_friendly]

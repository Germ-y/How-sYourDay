from api.schemas import Coordinate, EmotionState, PoiCandidate, RouteCandidate, RouteSegment
from tools.tmap_route import build_tmap_route_candidates


DEFAULT_ORIGIN = Coordinate(lat=37.5882, lng=126.9936)
DEFAULT_DESTINATION = Coordinate(lat=37.5826, lng=127.0019)


def build_route_candidates(
    stops: list[PoiCandidate],
    origin: Coordinate | None = None,
    destination: Coordinate | None = None,
    emotion: EmotionState | None = None,
    optional_stops: list[PoiCandidate] | None = None,
) -> list[RouteCandidate]:
    origin_point = origin or DEFAULT_ORIGIN
    destination_point = destination or DEFAULT_DESTINATION
    variants = _stop_variants(stops, emotion, optional_stops or [])
    tmap_routes = []
    for suffix, variant_stops in variants:
        tmap_routes.extend(
            _tag_variant_routes(
                build_tmap_route_candidates(
                    stops=variant_stops,
                    origin=origin_point,
                    destination=destination_point,
                ),
                suffix,
            )
        )
    if tmap_routes:
        return tmap_routes

    routes = []
    for suffix, variant_stops in variants:
        routes.extend(
            _tag_variant_routes(
                build_mock_route_candidates(
                    stops=variant_stops,
                    origin=origin_point,
                    destination=destination_point,
                ),
                suffix,
            )
        )
    return routes


def _stop_variants(
    required_stops: list[PoiCandidate],
    emotion: EmotionState | None,
    optional_stops: list[PoiCandidate],
) -> list[tuple[str, list[PoiCandidate]]]:
    base_required_stops = [
        stop for stop in required_stops if stop.category != "recovery"
    ]

    if emotion and emotion.time_pressure_tolerance == "high":
        return [("base", base_required_stops)]

    required_recovery_candidates = _unique_stops(
        stop for stop in required_stops if stop.category == "recovery"
    )[:3]

    if required_recovery_candidates:
        return [
            (f"recovery-{index}", [*base_required_stops, recovery_stop])
            for index, recovery_stop in enumerate(required_recovery_candidates, start=1)
        ]

    variants = [("base", base_required_stops)]
    if not emotion:
        return variants

    optional_recovery_candidates = _unique_stops(
        stop for stop in optional_stops if stop.category == "recovery"
    )[:2]
    for index, recovery_stop in enumerate(optional_recovery_candidates, start=1):
        variants.append((f"recovery-{index}", [*base_required_stops, recovery_stop]))
    return variants


def _unique_stops(stops) -> list[PoiCandidate]:
    seen: set[str] = set()
    unique: list[PoiCandidate] = []

    for stop in stops:
        key = stop.provider_id or f"{stop.name}:{stop.lat:.6f}:{stop.lng:.6f}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(stop)

    return unique


def _tag_variant_routes(
    routes: list[RouteCandidate],
    suffix: str,
) -> list[RouteCandidate]:
    if suffix == "base":
        return routes

    return [
        route.model_copy(
            update={
                "id": f"{route.id}-{suffix}",
            }
        )
        for route in routes
    ]


def build_mock_route_candidates(
    stops: list[PoiCandidate],
    origin: Coordinate,
    destination: Coordinate,
) -> list[RouteCandidate]:
    polyline = [
        Coordinate(lat=origin.lat, lng=origin.lng),
        *[Coordinate(lat=stop.lat, lng=stop.lng) for stop in stops],
        Coordinate(lat=destination.lat, lng=destination.lng),
    ]
    fallback_reason = "Tmap 경로를 만들 수 없어 추정 route를 사용했어요."

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
        fallback_reason=fallback_reason,
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
        fallback_reason=fallback_reason,
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
        fallback_reason=fallback_reason,
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

    return [primary, faster, recovery_friendly]

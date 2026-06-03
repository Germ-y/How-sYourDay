from api.schemas import Coordinate, EmotionState, PoiCandidate, RouteCandidate, RouteSegment
from tools.osrm_route import build_osrm_route_candidates
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
    provider_routes = []
    for suffix, variant_stops in variants:
        provider_routes.extend(
            _tag_variant_routes(
                _build_provider_route_candidates(
                    stops=variant_stops,
                    origin=origin_point,
                    destination=destination_point,
                ),
                suffix,
            )
        )
    if provider_routes:
        return provider_routes

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


def _build_provider_route_candidates(
    stops: list[PoiCandidate],
    origin: Coordinate,
    destination: Coordinate,
) -> list[RouteCandidate]:
    provider = _route_provider_preference()
    if provider != "osrm":
        tmap_routes = build_tmap_route_candidates(
            stops=stops,
            origin=origin,
            destination=destination,
        )
        if tmap_routes:
            return tmap_routes

    return build_osrm_route_candidates(
        stops=stops,
        origin=origin,
        destination=destination,
    )


def _route_provider_preference() -> str:
    import os

    return os.environ.get("HYS_ROUTE_PROVIDER", "").strip().lower()


def _stop_variants(
    required_stops: list[PoiCandidate],
    emotion: EmotionState | None,
    optional_stops: list[PoiCandidate],
) -> list[tuple[str, list[PoiCandidate]]]:
    required_groups = _stop_groups(required_stops)
    required_combinations = _group_combinations(required_groups, max_variants=12)
    if not required_combinations:
        required_combinations = [[]]

    variants = [
        (
            _required_variant_suffix(required_groups, required_combinations, index),
            combination,
        )
        for index, combination in enumerate(required_combinations, start=1)
    ]

    if emotion and emotion.time_pressure_tolerance == "high":
        return variants

    if not emotion:
        return variants

    optional_groups = _stop_groups(optional_stops)
    optional_combinations = _group_combinations(optional_groups, max_variants=4)
    if not optional_combinations:
        return variants

    base_variants = list(variants)
    for base_index, (_, base_stops) in enumerate(base_variants, start=1):
        for optional_index, optional_combo in enumerate(optional_combinations, start=1):
            if not optional_combo:
                continue
            variants.append(
                (
                    f"optional-{base_index}-{optional_index}",
                    [*base_stops, *optional_combo],
                )
            )
            if len(variants) >= 12:
                return variants

    return variants


def _stop_groups(stops: list[PoiCandidate]) -> list[list[PoiCandidate]]:
    groups: dict[str, list[PoiCandidate]] = {}
    order: dict[str, int] = {}

    for index, stop in enumerate(stops):
        key = _stop_task_key(stop, index)
        groups.setdefault(key, []).append(stop)
        priority = stop.task_priority if stop.task_priority is not None else index + 1000
        order[key] = min(order.get(key, priority), priority)

    return [
        _unique_stops(groups[key])[:3]
        for key in sorted(groups, key=lambda value: order[value])
    ]


def _required_variant_suffix(
    groups: list[list[PoiCandidate]],
    combinations: list[list[PoiCandidate]],
    index: int,
) -> str:
    if len(combinations) == 1:
        return "base"
    if len(groups) == 1 and groups[0] and groups[0][0].category == "recovery":
        return f"recovery-{index}"
    return f"required-{index}"


def _stop_task_key(stop: PoiCandidate, index: int) -> str:
    if stop.task_key:
        return stop.task_key
    return f"legacy:{stop.category}"


def _group_combinations(
    groups: list[list[PoiCandidate]],
    max_variants: int,
) -> list[list[PoiCandidate]]:
    if not groups:
        return []

    combinations: list[list[PoiCandidate]] = [[]]
    for group in groups:
        if not group:
            continue
        next_combinations: list[list[PoiCandidate]] = []
        for prefix in combinations:
            for stop in group:
                next_combinations.append([*prefix, stop])
                if len(next_combinations) >= max_variants:
                    break
            if len(next_combinations) >= max_variants:
                break
        combinations = next_combinations

    return combinations[:max_variants]


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
    fallback_reason = "현재 조건에 맞춰 예상 이동 경로를 계산했어요."

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

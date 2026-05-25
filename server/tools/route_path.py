from api.schemas import PoiCandidate, RouteCandidate


def build_route_candidates(stops: list[PoiCandidate]) -> list[RouteCandidate]:
    primary = RouteCandidate(
        id="route-low-stress",
        stops=stops,
        walking_minutes=14 + len(stops) * 3,
        transfer_count=1 if len(stops) > 1 else 0,
        crowd_level="medium",
        estimated_minutes=34 + len(stops) * 8,
    )
    faster = RouteCandidate(
        id="route-faster",
        stops=stops,
        walking_minutes=20 + len(stops) * 4,
        transfer_count=2 if len(stops) > 1 else 1,
        crowd_level="high",
        estimated_minutes=26 + len(stops) * 7,
    )

    return [primary, faster]


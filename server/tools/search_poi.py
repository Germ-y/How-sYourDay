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
}


def search_poi_candidates(tasks: list[Task], origin: Location) -> list[PoiCandidate]:
    candidates: list[PoiCandidate] = []
    kakao_candidates = {
        candidate.category: candidate
        for candidate in search_kakao_poi_candidates(tasks, origin)
    }

    for task in tasks:
        kakao_candidate = kakao_candidates.get(task.kind)
        if kakao_candidate:
            candidates.append(kakao_candidate)
            continue
        candidates.extend(MOCK_POIS.get(task.kind, MOCK_POIS["recovery"]))

    return candidates


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

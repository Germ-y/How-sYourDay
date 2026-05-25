from api.schemas import Location, PoiCandidate, Task


MOCK_POIS = {
    "print": [
        PoiCandidate(
            id="poi-print-1",
            name="Campus Print Lab",
            category="print",
            landmark_type="university",
            lat=37.5889,
            lng=126.9942,
        )
    ],
    "clinic": [
        PoiCandidate(
            id="poi-clinic-1",
            name="Sungkyun Clinic",
            category="clinic",
            landmark_type="medical",
            lat=37.5897,
            lng=126.9954,
        )
    ],
    "recovery": [
        PoiCandidate(
            id="poi-cafe-1",
            name="Quiet Table Cafe",
            category="recovery",
            landmark_type="side-street",
            lat=37.5876,
            lng=126.9926,
        )
    ],
}


def search_poi_candidates(tasks: list[Task], origin: Location) -> list[PoiCandidate]:
    del origin

    candidates: list[PoiCandidate] = []
    for task in tasks:
        candidates.extend(MOCK_POIS.get(task.kind, MOCK_POIS["recovery"]))

    return candidates


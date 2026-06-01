import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from api.schemas import Location, PoiCandidate
from tools.kakao_local import KAKAO_KEYWORD_SEARCH_URL, _get_env_value
from tools.landmark_emotion_prior import get_landmark_emotion_prior


PREFERENCE_QUERIES = [
    ("recovery", "카페", "cafe"),
    ("park", "공원", "park"),
    ("bookstore", "서점", "commercial"),
    ("library", "도서관", "university"),
    ("food", "분식", "commercial"),
    ("transit", "지하철역", "transit_hub"),
]


def search_preference_points(
    origin: Location,
    radius_meters: int = 1800,
) -> list[PoiCandidate]:
    api_key = _get_env_value("KAKAO_REST_API_KEY")
    if not api_key:
        return []

    points_by_id: dict[str, PoiCandidate] = {}
    for category, query, fallback_landmark_type in PREFERENCE_QUERIES:
        for document in _fetch_preference_documents(
            api_key,
            query,
            origin,
            radius_meters,
        ):
            provider_id = str(document.get("id") or "")
            if not provider_id or provider_id in points_by_id:
                continue

            points_by_id[provider_id] = _normalize_preference_document(
                document,
                category,
                fallback_landmark_type,
            )

    return list(points_by_id.values())[:18]


def _fetch_preference_documents(
    api_key: str,
    query: str,
    origin: Location,
    radius_meters: int,
) -> list[dict]:
    params = {
        "query": query,
        "x": origin.lng,
        "y": origin.lat,
        "radius": radius_meters,
        "sort": "distance",
        "size": 4,
    }
    url = f"{KAKAO_KEYWORD_SEARCH_URL}?{urlencode(params)}"
    request = Request(url, headers={"Authorization": f"KakaoAK {api_key}"})

    try:
        with urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return []

    documents = payload.get("documents", [])
    return documents if isinstance(documents, list) else []


def _normalize_preference_document(
    document: dict,
    category: str,
    fallback_landmark_type: str,
) -> PoiCandidate:
    landmark_type = _infer_preference_landmark_type(
        document,
        fallback_landmark_type,
    )
    prior = get_landmark_emotion_prior(landmark_type)
    provider_id = str(document.get("id") or "")

    return PoiCandidate(
        id=f"poi-preference-kakao-{provider_id or category}",
        provider_id=provider_id or None,
        name=str(document.get("place_name") or category),
        category=category,
        landmark_type=landmark_type,
        emotion_tags=prior.emotion_tags,
        lat=_to_float(document.get("y"), 37.5882),
        lng=_to_float(document.get("x"), 126.9936),
        distance_meters=_to_int_or_none(document.get("distance")),
        source_confidence="kakao",
    )


def _infer_preference_landmark_type(
    document: dict,
    fallback_landmark_type: str,
) -> str:
    category = str(document.get("category_name") or "")
    name = str(document.get("place_name") or "")
    combined = f"{category} {name}"

    if any(marker in combined for marker in ["카페", "커피"]):
        return "cafe"
    if any(marker in combined for marker in ["공원", "숲"]):
        return "park"
    if any(marker in combined for marker in ["지하철", "역", "버스"]):
        return "transit_hub"
    if any(marker in combined for marker in ["학교", "대학", "도서관"]):
        return "university"
    if any(marker in combined for marker in ["병원", "의료", "약국"]):
        return "medical"
    return fallback_landmark_type


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

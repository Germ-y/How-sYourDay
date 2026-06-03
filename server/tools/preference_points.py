import json
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from api.schemas import Location, PoiCandidate
from tools.kakao_local import KAKAO_KEYWORD_SEARCH_URL, _get_env_value
from tools.landmark_emotion_prior import get_landmark_emotion_prior


PREFERENCE_QUERIES = [
    ("recovery", "카페", "cafe"),
    ("park", "공원", "park"),
    ("walk", "산책로", "park"),
    ("bookstore", "서점", "commercial"),
    ("library", "도서관", "university"),
    ("bakery", "베이커리", "commercial"),
    ("food", "분식", "commercial"),
    ("culture", "문화시설", "commercial"),
    ("transit", "지하철역", "transit_hub"),
]
_PREFERENCE_DOCUMENT_CACHE: dict[str, list[dict]] = {}
_PREFERENCE_DOCUMENT_CACHE_LIMIT = 180


def search_preference_points(
    origin: Location,
    radius_meters: int = 1800,
) -> list[PoiCandidate]:
    api_key = _get_env_value("KAKAO_REST_API_KEY")
    if not api_key:
        return []

    points_by_id: dict[str, PoiCandidate] = {}
    with ThreadPoolExecutor(max_workers=min(6, len(PREFERENCE_QUERIES))) as executor:
        results = executor.map(
            lambda item: (
                item[0],
                item[2],
                _fetch_preference_documents(api_key, item[1], origin, radius_meters),
            ),
            PREFERENCE_QUERIES,
        )

        for category, fallback_landmark_type, documents in results:
            for document in documents:
                provider_id = str(document.get("id") or "")
                if not provider_id or provider_id in points_by_id:
                    continue

                points_by_id[provider_id] = _normalize_preference_document(
                    document,
                    category,
                    fallback_landmark_type,
                )

    return list(points_by_id.values())[:_result_limit(radius_meters)]


def _remember_preference_documents(cache_key: str, documents: list[dict]) -> None:
    if len(_PREFERENCE_DOCUMENT_CACHE) >= _PREFERENCE_DOCUMENT_CACHE_LIMIT:
        _PREFERENCE_DOCUMENT_CACHE.pop(next(iter(_PREFERENCE_DOCUMENT_CACHE)))
    _PREFERENCE_DOCUMENT_CACHE[cache_key] = documents


def _preference_cache_key(query: str, origin: Location, radius_meters: int) -> str:
    return json.dumps(
        {
            "query": query,
            "lat": round(origin.lat, 4),
            "lng": round(origin.lng, 4),
            "radius": radius_meters,
            "size": _query_size(radius_meters),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _fetch_preference_documents(
    api_key: str,
    query: str,
    origin: Location,
    radius_meters: int,
) -> list[dict]:
    cache_key = _preference_cache_key(query, origin, radius_meters)
    if cache_key in _PREFERENCE_DOCUMENT_CACHE:
        return _PREFERENCE_DOCUMENT_CACHE[cache_key]

    params = {
        "query": query,
        "x": origin.lng,
        "y": origin.lat,
        "radius": radius_meters,
        "sort": "distance",
        "size": _query_size(radius_meters),
    }
    url = f"{KAKAO_KEYWORD_SEARCH_URL}?{urlencode(params)}"
    request = Request(url, headers={"Authorization": f"KakaoAK {api_key}"})

    try:
        with urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return []

    documents = payload.get("documents", [])
    if not isinstance(documents, list):
        return []

    _remember_preference_documents(cache_key, documents)
    return documents


def _query_size(radius_meters: int) -> int:
    if radius_meters >= 4200:
        return 12
    if radius_meters >= 3000:
        return 9
    return 6


def _result_limit(radius_meters: int) -> int:
    if radius_meters >= 4200:
        return 60
    if radius_meters >= 3000:
        return 45
    return 30


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
        address=str(
            document.get("road_address_name")
            or document.get("address_name")
            or ""
        )
        or None,
        category_group_code=str(document.get("category_group_code") or "") or None,
        category_group_name=str(document.get("category_group_name") or "") or None,
        category_name=str(document.get("category_name") or "") or None,
        phone=str(document.get("phone") or "") or None,
        place_url=str(document.get("place_url") or "") or None,
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

import json
from math import cos, radians, sqrt
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from api.schemas import Coordinate, Location, LocationCandidate
from tools.kakao_local import KAKAO_KEYWORD_SEARCH_URL, _get_env_value

KAKAO_ADDRESS_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/address.json"
_GEOCODE_CACHE: dict[str, tuple[Location, str]] = {}
_GET_JSON_CACHE: dict[str, dict] = {}
_CACHE_LIMIT = 120
SEMANTIC_ALIASES = {
    "소극장": ["극장", "씨어터", "공연", "연극", "아트홀", "문화시설"],
    "극장": ["소극장", "씨어터", "공연", "연극", "아트홀", "문화시설"],
}

KNOWN_LOCATIONS = {
    "집": Location(label="집", lat=37.5826, lng=127.0019),
    "home": Location(label="집", lat=37.5826, lng=127.0019),
    "학교": Location(label="학교", lat=37.5882, lng=126.9936),
    "school": Location(label="학교", lat=37.5882, lng=126.9936),
    "회사": Location(label="회사", lat=37.5665, lng=126.978),
    "office": Location(label="회사", lat=37.5665, lng=126.978),
}


def geocode_location(query: str) -> tuple[Location, str] | None:
    text = query.strip()
    if not text:
        return None

    cache_key = _normalize(text)
    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]

    known = KNOWN_LOCATIONS.get(_normalize(text))
    if known:
        result = (known, "known")
        _remember_geocode(cache_key, result)
        return result

    api_key = _get_env_value("KAKAO_REST_API_KEY")
    if not api_key:
        return None

    address_result = _search_kakao_address(api_key, text)
    if address_result:
        result = (address_result, "kakao-address")
        _remember_geocode(cache_key, result)
        return result

    keyword_result = _search_kakao_keyword(api_key, text)
    if keyword_result:
        result = (keyword_result, "kakao-keyword")
        _remember_geocode(cache_key, result)
        return result

    return None


def search_location_candidates(
    query: str,
    size: int = 5,
    current_location: Coordinate | None = None,
) -> list[LocationCandidate]:
    text = query.strip()
    if not text:
        return []

    normalized = _normalize(text)
    candidates: list[LocationCandidate] = []
    known = KNOWN_LOCATIONS.get(normalized)
    if known:
        candidates.append(
            LocationCandidate(
                label=known.label,
                address=None,
                lat=known.lat,
                lng=known.lng,
                source="known",
                category="저장 키워드",
            )
        )

    api_key = _get_env_value("KAKAO_REST_API_KEY")
    if api_key:
        candidates.extend(
            _search_kakao_address_candidates(
                api_key,
                text,
                size,
                current_location=current_location,
            )
        )
        candidates.extend(
            _search_kakao_keyword_candidates(
                api_key,
                text,
                size,
                current_location=current_location,
            )
        )

    candidates = _dedupe_candidates(candidates)
    protected_candidates = [
        candidate
        for candidate in candidates
        if candidate.source in {"known", "kakao-address"}
    ]
    semantic_candidates = [
        candidate
        for candidate in candidates
        if candidate.source not in {"known", "kakao-address"}
        and _candidate_matches_query(text, candidate)
    ]
    if protected_candidates or semantic_candidates:
        candidates = [*protected_candidates, *semantic_candidates]
    if current_location:
        candidates = sorted(
            candidates,
            key=lambda candidate: (
                0 if candidate.source in {"known", "kakao-address"} else 1,
                candidate.distance_meters
                if candidate.distance_meters is not None
                else _rough_distance_meters(current_location, candidate),
            ),
        )
    return candidates[:size]


def _search_kakao_address(api_key: str, query: str) -> Location | None:
    payload = _get_json(
        KAKAO_ADDRESS_SEARCH_URL,
        api_key,
        {
            "query": query,
            "size": 1,
        },
    )
    documents = payload.get("documents", []) if payload else []
    if not documents:
        return None

    document = documents[0]
    label = str(document.get("address_name") or query)
    return Location(
        label=label,
        lat=_to_float(document.get("y"), 0),
        lng=_to_float(document.get("x"), 0),
    )


def _search_kakao_address_candidates(
    api_key: str,
    query: str,
    size: int,
    current_location: Coordinate | None = None,
) -> list[LocationCandidate]:
    payload = _get_json(
        KAKAO_ADDRESS_SEARCH_URL,
        api_key,
        {
            "query": query,
            "size": size,
        },
    )
    documents = payload.get("documents", []) if payload else []
    candidates: list[LocationCandidate] = []

    for document in documents:
        label = str(document.get("address_name") or query)
        candidate = LocationCandidate(
            label=label,
            address=_address_label(document),
            lat=_to_float(document.get("y"), 0),
            lng=_to_float(document.get("x"), 0),
            source="kakao-address",
            category="주소",
        )
        if current_location:
            candidate.distance_meters = _rough_distance_meters(current_location, candidate)
        candidates.append(candidate)

    return candidates


def _search_kakao_keyword(api_key: str, query: str) -> Location | None:
    payload = _get_json(
        KAKAO_KEYWORD_SEARCH_URL,
        api_key,
        {
            "query": query,
            "size": 1,
        },
    )
    documents = payload.get("documents", []) if payload else []
    if not documents:
        return None

    document = documents[0]
    label = str(document.get("place_name") or document.get("address_name") or query)
    return Location(
        label=label,
        lat=_to_float(document.get("y"), 0),
        lng=_to_float(document.get("x"), 0),
    )


def _search_kakao_keyword_candidates(
    api_key: str,
    query: str,
    size: int,
    current_location: Coordinate | None = None,
) -> list[LocationCandidate]:
    params = {
        "query": query,
        "size": size,
    }
    if current_location:
        params.update(
            {
                "x": current_location.lng,
                "y": current_location.lat,
                "sort": "distance",
            }
        )
    payload = _get_json(
        KAKAO_KEYWORD_SEARCH_URL,
        api_key,
        params,
    )
    documents = payload.get("documents", []) if payload else []
    candidates: list[LocationCandidate] = []

    for document in documents:
        label = str(document.get("place_name") or document.get("address_name") or query)
        candidates.append(
            LocationCandidate(
                label=label,
                address=str(
                    document.get("road_address_name")
                    or document.get("address_name")
                    or ""
                )
                or None,
                lat=_to_float(document.get("y"), 0),
                lng=_to_float(document.get("x"), 0),
                source="kakao-keyword",
                category=str(document.get("category_group_name") or document.get("category_name") or "")
                or None,
                distance_meters=_to_int(document.get("distance")),
            )
        )

    return candidates


def _address_label(document: dict) -> str | None:
    road_address = document.get("road_address")
    if isinstance(road_address, dict) and road_address.get("address_name"):
        return str(road_address["address_name"])

    address = document.get("address")
    if isinstance(address, dict) and address.get("address_name"):
        return str(address["address_name"])

    label = document.get("address_name")
    return str(label) if label else None


def _dedupe_candidates(candidates: list[LocationCandidate]) -> list[LocationCandidate]:
    seen: set[str] = set()
    unique: list[LocationCandidate] = []

    for candidate in candidates:
        key = f"{_normalize(candidate.label)}:{candidate.lat:.6f}:{candidate.lng:.6f}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)

    return unique


def _candidate_matches_query(query: str, candidate: LocationCandidate) -> bool:
    normalized_terms = _semantic_terms(query)
    if not normalized_terms:
        return True

    candidate_text = _normalize(
        " ".join(
            value
            for value in [candidate.label, candidate.address, candidate.category]
            if value
        )
    )
    if len(normalized_terms) >= 2:
        return all(_term_matches_candidate(term, candidate_text) for term in normalized_terms)
    return _term_matches_candidate(normalized_terms[0], candidate_text)


def _term_matches_candidate(term: str, candidate_text: str) -> bool:
    return any(
        alias in candidate_text
        for alias in [term, *SEMANTIC_ALIASES.get(term, [])]
    )


def _semantic_terms(query: str) -> list[str]:
    raw_terms = [
        _normalize(term)
        for term in query.split()
        if len(_normalize(term)) >= 2
    ]
    if not raw_terms:
        raw_terms = [_normalize(query)] if len(_normalize(query)) >= 2 else []

    non_region_terms = [
        term
        for term in raw_terms
        if term not in {"서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종"}
    ]
    return non_region_terms or raw_terms


def _get_json(url: str, api_key: str, params: dict) -> dict | None:
    cache_key = f"{url}:{json.dumps(params, sort_keys=True, ensure_ascii=False)}"
    if cache_key in _GET_JSON_CACHE:
        return _GET_JSON_CACHE[cache_key]

    request = Request(
        f"{url}?{urlencode(params)}",
        headers={"Authorization": f"KakaoAK {api_key}"},
    )

    try:
        with urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
            _remember_json(cache_key, payload)
            return payload
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return None


def _remember_geocode(cache_key: str, result: tuple[Location, str]) -> None:
    if len(_GEOCODE_CACHE) >= _CACHE_LIMIT:
        _GEOCODE_CACHE.pop(next(iter(_GEOCODE_CACHE)))
    _GEOCODE_CACHE[cache_key] = result


def _remember_json(cache_key: str, payload: dict) -> None:
    if len(_GET_JSON_CACHE) >= _CACHE_LIMIT:
        _GET_JSON_CACHE.pop(next(iter(_GET_JSON_CACHE)))
    _GET_JSON_CACHE[cache_key] = payload


def _normalize(value: str) -> str:
    return value.lower().replace(" ", "")


def _to_float(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _rough_distance_meters(start: Coordinate, end: Coordinate) -> int:
    lat_meters = (end.lat - start.lat) * 111_000
    lng_meters = (end.lng - start.lng) * 111_000 * cos(radians(start.lat))
    return round(sqrt(lat_meters * lat_meters + lng_meters * lng_meters))

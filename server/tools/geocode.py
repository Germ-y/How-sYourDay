import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from api.schemas import Location
from tools.kakao_local import KAKAO_KEYWORD_SEARCH_URL, _get_env_value

KAKAO_ADDRESS_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/address.json"
_GEOCODE_CACHE: dict[str, tuple[Location, str]] = {}
_GET_JSON_CACHE: dict[str, dict] = {}
_CACHE_LIMIT = 120

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

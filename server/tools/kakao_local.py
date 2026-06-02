import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from api.schemas import Location, PoiCandidate, Task
from tools.landmark_emotion_prior import get_landmark_emotion_prior
from tools.poi_candidate_validation import document_matches_task


KAKAO_KEYWORD_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
_KAKAO_DOCUMENT_CACHE: dict[str, list[dict]] = {}
_KAKAO_DOCUMENT_CACHE_LIMIT = 160
TASK_QUERY_OVERRIDES = {
    "print": "인쇄소",
    "clinic": "병원",
}


def search_kakao_poi_candidates(
    tasks: list[Task],
    origin: Location,
    user_text: str = "",
) -> list[PoiCandidate]:
    api_key = _get_env_value("KAKAO_REST_API_KEY")
    if not api_key:
        return []

    candidates: list[PoiCandidate] = []
    for task in tasks:
        documents = _fetch_kakao_documents(api_key, task, origin)
        if not documents:
            continue
        documents = [
            document
            for document in documents
            if document_matches_task(document, task, user_text)
        ]
        if not documents:
            continue
        candidates.extend(
            _normalize_document(document, task)
            for document in documents[: _candidate_limit(task)]
        )

    return candidates


def _candidate_limit(task: Task) -> int:
    return 3 if task.kind == "recovery" else 1


def _fetch_kakao_documents(
    api_key: str,
    task: Task,
    origin: Location,
) -> list[dict]:
    params = {
        "query": TASK_QUERY_OVERRIDES.get(task.kind, task.poi_query),
        "x": origin.lng,
        "y": origin.lat,
        "radius": 2000,
        "sort": "distance",
        "size": 3,
    }
    cache_key = json.dumps(params, sort_keys=True, ensure_ascii=False)
    if cache_key in _KAKAO_DOCUMENT_CACHE:
        return _KAKAO_DOCUMENT_CACHE[cache_key]

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

    _remember_kakao_documents(cache_key, documents)
    return documents


def _remember_kakao_documents(cache_key: str, documents: list[dict]) -> None:
    if len(_KAKAO_DOCUMENT_CACHE) >= _KAKAO_DOCUMENT_CACHE_LIMIT:
        _KAKAO_DOCUMENT_CACHE.pop(next(iter(_KAKAO_DOCUMENT_CACHE)))
    _KAKAO_DOCUMENT_CACHE[cache_key] = documents


def _normalize_document(document: dict, task: Task) -> PoiCandidate:
    landmark_type = _infer_landmark_type(document, task)
    prior = get_landmark_emotion_prior(landmark_type)
    emotion_tags = list(dict.fromkeys([*prior.emotion_tags, *_task_emotion_tags(task)]))
    provider_id = str(document.get("id") or "")

    return PoiCandidate(
        id=f"poi-kakao-{task.kind}-{provider_id or 'unknown'}",
        provider_id=provider_id or None,
        name=str(document.get("place_name") or task.label),
        category=task.kind,
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
        emotion_tags=emotion_tags,
        lat=_to_float(document.get("y"), 37.5882),
        lng=_to_float(document.get("x"), 126.9936),
        distance_meters=_to_int_or_none(document.get("distance")),
        source_confidence="kakao",
    )


def _infer_landmark_type(document: dict, task: Task) -> str:
    category = str(document.get("category_name") or "")
    name = str(document.get("place_name") or "")
    combined = f"{category} {name}"

    if task.kind == "clinic" or any(marker in combined for marker in ["병원", "의료", "약국"]):
        return "medical"
    if task.kind == "errand" or any(marker in combined for marker in ["다이소", "생활용품", "마트", "편의점", "상점"]):
        return "commercial"
    if any(marker in combined for marker in ["지하철", "역", "버스", "교통"]):
        return "transit_hub"
    if any(marker in combined for marker in ["대학", "학교", "교육"]):
        return "university"
    if any(marker in combined for marker in ["공원", "숲"]):
        return "park"
    if any(marker in combined for marker in ["강", "한강", "하천"]):
        return "river"
    if any(marker in combined for marker in ["만화카페", "만화방", "북카페", "서점", "도서"]):
        return "cafe"
    if task.kind == "recovery":
        return "cafe"
    return "commercial"


def _task_emotion_tags(task: Task) -> list[str]:
    if task.kind == "recovery":
        return ["calm", "recovery"]
    if task.kind == "clinic":
        return ["stressful"]
    if task.kind == "errand":
        return ["practical", "errand"]
    return []


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


def _get_env_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        if key.strip().lstrip("\ufeff") == name:
            cleaned = raw_value.strip().strip('"').strip("'")
            return cleaned or None

    return None

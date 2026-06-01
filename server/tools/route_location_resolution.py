import json
import os
import re
from dataclasses import dataclass

from api.schemas import LocationCandidate
from tools.extract_route_locations import extract_route_locations
from tools.geocode import search_location_candidates
from tools.kakao_local import _get_env_value
from tools.llm_intent import (
    DEFAULT_INTENT_MODEL,
    _post_openai,
    _response_text,
)
from tools.prompt_loader import kst_runtime_context, load_prompt


LOCATION_SELECTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["origin_index", "destination_index"],
    "properties": {
        "origin_index": {
            "anyOf": [
                {"type": "integer", "minimum": 0, "maximum": 9},
                {"type": "null"},
            ]
        },
        "destination_index": {
            "anyOf": [
                {"type": "integer", "minimum": 0, "maximum": 9},
                {"type": "null"},
            ]
        },
    },
}


@dataclass(frozen=True)
class RouteLocationResolution:
    origin_text: str | None
    destination_text: str | None
    origin: LocationCandidate | None
    destination: LocationCandidate | None
    origin_candidates: list[LocationCandidate]
    destination_candidates: list[LocationCandidate]
    source: str
    selection_source: str


def resolve_route_locations(user_text: str, size: int = 5) -> RouteLocationResolution:
    hints = extract_route_locations(user_text)
    origin_text = _origin_hint_from_text(user_text) or hints.origin_text
    destination_text = _specific_destination_hint_from_text(user_text) or hints.destination_text
    origin_queries = _origin_queries_from_text(user_text, origin_text)
    destination_queries = _destination_queries_from_text(user_text, destination_text)
    origin_candidates = _candidate_search_many(
        origin_queries,
        size,
    )
    destination_candidates = _candidate_search_many(
        destination_queries,
        size,
    )
    selection = _select_locations_with_llm(
        user_text,
        origin_text,
        destination_text,
        origin_candidates,
        destination_candidates,
    )

    if selection is not None:
        origin = _candidate_at(origin_candidates, selection.get("origin_index"))
        destination = _candidate_at(
            destination_candidates, selection.get("destination_index")
        )
        selection_source = "llm"
    else:
        origin = _select_best_across_queries(origin_queries, origin_candidates)
        destination = _select_best_across_queries(
            destination_queries, destination_candidates
        )
        selection_source = "score" if origin or destination else "none"

    if (
        origin
        and destination
        and _same_candidate(origin, destination)
        and _normalize(origin_text or "") != _normalize(destination_text or "")
    ):
        destination = _select_distinct_candidate_by_score(
            destination_text,
            destination_candidates,
            origin,
        )
        if destination:
            selection_source = f"{selection_source}-deduped"

    return RouteLocationResolution(
        origin_text=origin_text,
        destination_text=destination_text,
        origin=origin,
        destination=destination,
        origin_candidates=origin_candidates,
        destination_candidates=destination_candidates,
        source=hints.source,
        selection_source=selection_source,
    )


def _candidate_search(query: str | None, size: int) -> list[LocationCandidate]:
    if not query:
        return []
    return search_location_candidates(query, size=size)


def _candidate_search_many(queries: list[str], size: int) -> list[LocationCandidate]:
    candidates: list[LocationCandidate] = []
    seen: set[str] = set()

    for query in queries:
        for candidate in _candidate_search(query, size):
            key = f"{_normalize(candidate.label)}:{candidate.lat:.6f}:{candidate.lng:.6f}"
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)

    return candidates[: max(size, 10)]


def _select_locations_with_llm(
    user_text: str,
    origin_text: str | None,
    destination_text: str | None,
    origin_candidates: list[LocationCandidate],
    destination_candidates: list[LocationCandidate],
) -> dict | None:
    if (os.environ.get("HYS_DISABLE_LLM") or _get_env_value("HYS_DISABLE_LLM")) == "1":
        return None

    api_key = _get_env_value("OPENAI_API_KEY")
    if not api_key:
        return None

    if not origin_candidates and not destination_candidates:
        return None

    model = (
        os.environ.get("OPENAI_INTENT_MODEL")
        or _get_env_value("OPENAI_INTENT_MODEL")
        or DEFAULT_INTENT_MODEL
    )
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": load_prompt("route_location_selection"),
            },
            {
                "role": "system",
                "content": kst_runtime_context(),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_text": user_text,
                        "origin_text": origin_text,
                        "destination_text": destination_text,
                        "origin_candidates": _candidate_payload(origin_candidates),
                        "destination_candidates": _candidate_payload(
                            destination_candidates
                        ),
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "route_location_selection",
                "strict": True,
                "schema": LOCATION_SELECTION_SCHEMA,
            }
        },
        "max_output_tokens": 120,
    }

    raw = _post_openai(api_key, payload)
    if raw is None:
        return None

    text = _response_text(raw)
    if not text:
        return None

    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None

    return {
        "origin_index": _valid_index(data.get("origin_index"), origin_candidates),
        "destination_index": _valid_index(
            data.get("destination_index"), destination_candidates
        ),
    }


def _candidate_payload(candidates: list[LocationCandidate]) -> list[dict]:
    return [
        {
            "index": index,
            "label": candidate.label,
            "address": candidate.address,
            "category": candidate.category,
            "source": candidate.source,
        }
        for index, candidate in enumerate(candidates)
    ]


def _valid_index(value, candidates: list[LocationCandidate]) -> int | None:
    if not isinstance(value, int):
        return None
    if value < 0 or value >= len(candidates):
        return None
    return value


def _candidate_at(
    candidates: list[LocationCandidate], index: int | None
) -> LocationCandidate | None:
    if index is None:
        return None
    return candidates[index]


def _select_candidate_by_score(
    query: str | None, candidates: list[LocationCandidate]
) -> LocationCandidate | None:
    if not query or not candidates:
        return None

    query_normalized = _normalize(query)
    terms = _terms(query)
    school_query = any(keyword in query for keyword in ["대학교", "대학", "캠퍼스"])
    station_query = "역" in query
    best: tuple[int, int, LocationCandidate] | None = None

    for index, candidate in enumerate(candidates):
        label = _normalize(candidate.label)
        address = _normalize(candidate.address or "")
        category = _normalize(candidate.category or "")
        score = 0

        if label == query_normalized:
            score += 80
        if query_normalized and query_normalized in label:
            score += 42
        if label and label in query_normalized:
            score += 34

        for term in terms:
            if term in label:
                score += 12
            if term in address:
                score += 8
            if term in category:
                score += 3

        if school_query:
            if "학교" in (candidate.category or ""):
                score += 45
            else:
                score -= 10
            if "캠퍼스" in candidate.label:
                score += 14
            if "점" in candidate.label or "우편취급국" in candidate.label:
                score -= 12
        if station_query and "역" in candidate.label:
            score += 10
            if "기차역" in (candidate.category or ""):
                score += 12
        if candidate.source == "kakao-address":
            score += 3
        if candidate.source == "kakao-keyword":
            score += 2

        ranked = (score, -index, candidate)
        if best is None or ranked[:2] > best[:2]:
            best = ranked

    if best is None or best[0] <= 0:
        return None
    return best[2]


def _select_distinct_candidate_by_score(
    query: str | None,
    candidates: list[LocationCandidate],
    disallowed: LocationCandidate,
) -> LocationCandidate | None:
    return _select_candidate_by_score(
        query,
        [candidate for candidate in candidates if not _same_candidate(candidate, disallowed)],
    )


def _select_best_across_queries(
    queries: list[str],
    candidates: list[LocationCandidate],
) -> LocationCandidate | None:
    for query in queries:
        selected = _select_candidate_by_score(query, candidates)
        if selected:
            return selected
    return None


def _same_candidate(a: LocationCandidate, b: LocationCandidate) -> bool:
    return (
        _normalize(a.label) == _normalize(b.label)
        or (round(a.lat, 6) == round(b.lat, 6) and round(a.lng, 6) == round(b.lng, 6))
    )


def _origin_queries_from_text(user_text: str, origin_text: str | None) -> list[str]:
    queries = [origin_text]
    matches = re.findall(r"([^,.;\n]+?)(?:에서|부터)", user_text)
    if matches:
        queries.append(_clean_query(matches[0]))
    return _unique_queries(queries)


def _destination_queries_from_text(
    user_text: str, destination_text: str | None
) -> list[str]:
    queries = [
        _specific_destination_hint_from_text(user_text),
        destination_text,
        _destination_before_origin_hint_from_text(user_text),
    ]
    for match in re.findall(r"([^,.;\n]+?)(?:까지|으로|로)\s*(?:갈|가고|가야|도착|이동|$)", user_text):
        queries.append(_clean_query(match))
    for match in re.findall(r"(?:가서|하다가|그리고)\s*([^,.;\n]+?)(?:에서|까지|으로|로)", user_text):
        queries.append(_clean_query(match))
    return _unique_queries(queries)


def _origin_hint_from_text(user_text: str) -> str | None:
    matches = re.findall(r"([^,.;\n]+?)(?:에서|부터)", user_text)
    if not matches:
        return None
    return _clean_query(matches[0])


def _specific_destination_hint_from_text(user_text: str) -> str | None:
    patterns = [
        r"(?:\d{1,2}시(?:\s*\d{1,2}분)?(?:에)?\s*)?([가-힣A-Za-z0-9\s]+?(?:식당|카페|역|학교|병원|도서관|공원|장소|곳))에서\s*(?:\d{1,2}시|친구|약속|보기|만나|예약)",
        r"([가-힣A-Za-z0-9\s]+?)(?:이라는|라는)\s*(?:식당|카페|장소|곳)?에서\s*(?:\d{1,2}시|친구|약속|보기|만나)",
        r"([가-힣A-Za-z0-9\s]+?(?:식당|카페|역|학교|병원|도서관|공원))에서\s*(?:\d{1,2}시|친구|약속|보기|만나)",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, user_text, flags=re.IGNORECASE)
        for value in reversed(matches):
            candidate = re.split(r"(?:하다가|가서|그리고|,|\.|;)", value)[-1]
            cleaned = _clean_query(candidate)
            if cleaned:
                return cleaned
    return None


def _destination_before_origin_hint_from_text(user_text: str) -> str | None:
    match = re.search(
        r"(.+?)(?:까지|으로|로)\s*(?:가고\s*싶|가야|갈|가기|가려고|도착|이동)",
        user_text,
        flags=re.IGNORECASE,
    )
    return _clean_query(match.group(1) if match else None)


def _clean_query(value: str | None) -> str | None:
    if not value:
        return None

    cleaned = value.strip()
    cleaned = re.sub(r"^\d{1,2}시(?:\s*\d{1,2}분)?(?:에)?\s*", "", cleaned)
    cleaned = re.sub(r"^.*(?:가고\s*싶어|가고싶어|싶어)\s+", "", cleaned)
    cleaned = re.sub(
        r"^.*(?:에서|부터)\s*(?:출발해서|출발하고|출발|시작해서|시작)?\s*",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"^(오늘|내일|지금|일단|그리고|나는|나|제가|저는|i)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s*(?:이라는|라는)\s*(?:식당|카페|장소|곳)$", "", cleaned)
    cleaned = re.sub(r"\s*(가야|갈|가기|가려고|도착|출발|시작).*$", "", cleaned)
    cleaned = re.sub(r"\s*(에서|부터|으로|로|까지|에)$", "", cleaned)
    cleaned = cleaned.strip()
    return cleaned if len(cleaned) >= 2 else None


def _unique_queries(values: list[str | None]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = _clean_query(value)
        if not cleaned:
            continue
        key = _normalize(cleaned)
        if key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)

    return unique


def _terms(value: str) -> list[str]:
    return [
        term
        for term in re.split(r"[\s,./·()]+", value)
        if len(_normalize(term)) >= 2
    ]


def _normalize(value: str) -> str:
    return value.lower().replace(" ", "")

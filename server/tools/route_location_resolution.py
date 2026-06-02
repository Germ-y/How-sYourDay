import json
import os
import re
from dataclasses import dataclass
from math import cos, radians, sqrt

from api.schemas import Coordinate, LocationCandidate
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

MAJOR_REGION_TOKENS = [
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "경기",
    "강원",
    "충북",
    "충청북도",
    "충남",
    "충청남도",
    "전북",
    "전라북도",
    "전남",
    "전라남도",
    "경북",
    "경상북도",
    "경남",
    "경상남도",
    "제주",
]

SEOUL_AREA_REGION_HINTS = {
    "대학로": ["서울", "종로", "혜화", "동숭", "명륜", "이화동"],
    "혜화": ["서울", "종로", "혜화", "동숭", "명륜"],
    "홍대": ["서울", "마포", "서교", "상수", "합정", "홍대입구"],
    "성수": ["서울", "성동", "성수"],
    "서울숲": ["서울", "성동", "서울숲"],
    "신촌": ["서울", "서대문", "마포", "신촌"],
    "이대": ["서울", "서대문", "대현", "이화여대"],
    "강남": ["서울", "강남", "역삼"],
    "건대": ["서울", "광진", "화양", "건대입구"],
    "여의도": ["서울", "영등포", "여의도"],
    "오목교": ["서울", "양천", "오목"],
}

SEMANTIC_ALIASES = {
    "소극장": ["극장", "씨어터", "공연", "연극", "아트홀", "문화시설"],
    "극장": ["소극장", "씨어터", "공연", "연극", "아트홀", "문화시설"],
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


def resolve_route_locations(
    user_text: str,
    size: int = 5,
    current_location: Coordinate | None = None,
) -> RouteLocationResolution:
    hints = extract_route_locations(user_text)
    origin_text = _origin_hint_from_text(user_text) or hints.origin_text
    destination_text = (
        _specific_destination_hint_from_text(user_text)
        or _destination_hint_after_origin_from_text(user_text)
        or hints.destination_text
    )
    origin_queries = _origin_queries_from_text(user_text, origin_text)
    destination_queries = _destination_queries_from_text(user_text, destination_text)
    origin_candidates = _candidate_search_many(
        origin_queries,
        size,
        current_location=current_location,
    )
    destination_candidates = _candidate_search_many(
        destination_queries,
        size,
        current_location=current_location,
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
        scored_origin = _select_best_across_queries(
            origin_queries,
            origin_candidates,
            current_location=current_location,
        )
        origin_context = _candidate_region_context(origin or scored_origin)
        scored_destination = _select_best_across_queries(
            destination_queries,
            destination_candidates,
            origin_context,
            current_location=current_location,
        )
        adjusted_origin = _prefer_score_adjusted_candidate(
            origin_text, None, current_location, origin, scored_origin
        )
        adjusted_destination = _prefer_score_adjusted_candidate(
            destination_text,
            origin_context,
            current_location,
            destination,
            scored_destination,
        )
        selection_source = (
            "llm-score-adjusted"
            if adjusted_origin is not origin or adjusted_destination is not destination
            else "llm"
        )
        origin = adjusted_origin
        destination = adjusted_destination
    else:
        origin = _select_best_across_queries(
            origin_queries,
            origin_candidates,
            current_location=current_location,
        )
        origin_context = _candidate_region_context(origin)
        destination = _select_best_across_queries(
            destination_queries,
            destination_candidates,
            origin_context,
            current_location=current_location,
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
            _candidate_region_context(origin),
            current_location,
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


def _candidate_search(
    query: str | None,
    size: int,
    current_location: Coordinate | None = None,
) -> list[LocationCandidate]:
    if not query:
        return []
    return search_location_candidates(
        query,
        size=size,
        current_location=current_location,
    )


def _candidate_search_many(
    queries: list[str],
    size: int,
    context_text: str | None = None,
    current_location: Coordinate | None = None,
) -> list[LocationCandidate]:
    candidates: list[LocationCandidate] = []
    seen: set[str] = set()

    for query in queries:
        for search_query in _regionalized_queries(query, context_text):
            for candidate in _candidate_search(
                search_query,
                size,
                current_location=current_location,
            ):
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
    query: str | None,
    candidates: list[LocationCandidate],
    context_text: str | None = None,
    current_location: Coordinate | None = None,
) -> LocationCandidate | None:
    if not query or not candidates:
        return None

    best: tuple[int, int, LocationCandidate] | None = None

    for index, candidate in enumerate(candidates):
        score = _candidate_score(query, candidate, context_text, current_location)
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
    context_text: str | None = None,
    current_location: Coordinate | None = None,
) -> LocationCandidate | None:
    return _select_candidate_by_score(
        query,
        [candidate for candidate in candidates if not _same_candidate(candidate, disallowed)],
        context_text,
        current_location,
    )


def _select_best_across_queries(
    queries: list[str],
    candidates: list[LocationCandidate],
    context_text: str | None = None,
    current_location: Coordinate | None = None,
) -> LocationCandidate | None:
    for query in queries:
        selected = _select_candidate_by_score(
            query,
            candidates,
            context_text,
            current_location,
        )
        if selected:
            return selected
    return None


def _prefer_score_adjusted_candidate(
    query: str | None,
    context_text: str | None,
    current_location: Coordinate | None,
    selected: LocationCandidate | None,
    scored: LocationCandidate | None,
) -> LocationCandidate | None:
    if not scored:
        return selected
    if not selected:
        return scored
    if _same_candidate(selected, scored):
        return selected

    selected_score = _candidate_score(query, selected, context_text, current_location)
    scored_score = _candidate_score(query, scored, context_text, current_location)
    if scored_score >= selected_score + 35:
        return scored
    return selected


def _candidate_score(
    query: str | None,
    candidate: LocationCandidate,
    context_text: str | None = None,
    current_location: Coordinate | None = None,
) -> int:
    if not query:
        return 0

    query_normalized = _normalize(query)
    terms = _terms(query)
    school_query = any(keyword in query for keyword in ["대학교", "대학", "캠퍼스"])
    station_query = "역" in query
    label = _normalize(candidate.label)
    address = _normalize(candidate.address or "")
    category = _normalize(candidate.category or "")
    score = 0
    semantic_score = 0
    matched_terms = 0

    if label == query_normalized:
        score += 80
        semantic_score += 80
    if query_normalized and query_normalized in label:
        score += 42
        semantic_score += 42
    if label and label in query_normalized:
        score += 34
        semantic_score += 34

    for term in terms:
        term_matched = False
        if _term_matches_candidate(term, label):
            score += 12
            semantic_score += 12
            term_matched = True
        if _term_matches_candidate(term, address):
            score += 10
            semantic_score += 10
            term_matched = True
        if _term_matches_candidate(term, category):
            score += 3
            semantic_score += 3
            term_matched = True
        if term_matched:
            matched_terms += 1

    if len(terms) >= 2:
        score += matched_terms * 20
        semantic_score += matched_terms * 20
        if matched_terms < len(terms):
            score -= 45 * (len(terms) - matched_terms)
            semantic_score -= 45 * (len(terms) - matched_terms)

    if semantic_score <= 0:
        return -100

    score += _region_match_score(query, context_text, candidate)
    score += _distance_match_score(candidate, current_location)

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
        if "지하철역" in (candidate.category or ""):
            score += 18
        if "기차역" in (candidate.category or ""):
            score += 12
        if "역무실" in candidate.label or "관리,운영" in (candidate.category or ""):
            score -= 28
    if candidate.source == "kakao-address":
        score += 3
    if candidate.source == "kakao-keyword":
        score += 2

    return score


def _term_matches_candidate(term: str, candidate_text: str) -> bool:
    return any(
        alias in candidate_text
        for alias in [term, *SEMANTIC_ALIASES.get(term, [])]
    )


def _distance_match_score(
    candidate: LocationCandidate,
    current_location: Coordinate | None,
) -> int:
    if not current_location:
        return 0

    distance = candidate.distance_meters
    if distance is None:
        distance = _rough_distance_meters(current_location, candidate)

    if distance <= 700:
        return 30
    if distance <= 1500:
        return 22
    if distance <= 3000:
        return 14
    if distance <= 7000:
        return 6
    if distance >= 30_000:
        return -25
    return 0


def _region_match_score(
    query: str,
    context_text: str | None,
    candidate: LocationCandidate,
) -> int:
    hints = _region_hints(query, context_text)
    if not hints:
        return 0

    label = _normalize(candidate.label)
    address = _normalize(candidate.address or "")
    candidate_text = f"{label} {address}"
    normalized_hints = [_normalize(hint) for hint in hints]
    score = 0

    if any(hint and hint in address for hint in normalized_hints):
        score += 45
    elif any(hint and hint in candidate_text for hint in normalized_hints):
        score += 20

    allowed_major_regions = {
        region
        for region in MAJOR_REGION_TOKENS
        if _normalize(region) in normalized_hints
    }
    if allowed_major_regions and _major_region_conflicts(address, allowed_major_regions):
        score -= 150

    return score


def _region_hints(query: str, context_text: str | None = None) -> list[str]:
    explicit_query_regions = _major_regions_in_text(query)
    if explicit_query_regions:
        return explicit_query_regions

    context_regions = _region_tokens_from_context(context_text)
    if context_regions:
        return context_regions

    for area, hints in SEOUL_AREA_REGION_HINTS.items():
        if _normalize(area) in _normalize(query):
            return hints
    return []


def _major_regions_in_text(text: str | None) -> list[str]:
    normalized = _normalize(text or "")
    return [
        region for region in MAJOR_REGION_TOKENS if _normalize(region) in normalized
    ]


def _region_tokens_from_context(context_text: str | None) -> list[str]:
    if not context_text:
        return []

    tokens: list[str | None] = [*_major_regions_in_text(context_text)]
    for match in re.findall(r"([가-힣]{2,6})(?:시|군|구)", context_text):
        tokens.append(match)
    for match in re.findall(r"([가-힣]{2,8})(?:읍|면|동)", context_text):
        tokens.append(match)
    return _unique_region_tokens(tokens)


def _unique_region_tokens(values: list[str | None]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        cleaned = value.strip()
        if len(cleaned) < 2:
            continue
        key = _normalize(cleaned)
        if key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)
    return unique


def _major_region_conflicts(address: str, allowed_major_regions: set[str]) -> bool:
    if not address:
        return False
    normalized_allowed = {_normalize(region) for region in allowed_major_regions}
    for region in MAJOR_REGION_TOKENS:
        normalized_region = _normalize(region)
        if normalized_region in address and normalized_region not in normalized_allowed:
            return True
    return False


def _candidate_region_context(candidate: LocationCandidate | None) -> str | None:
    if not candidate:
        return None
    return " ".join(
        value
        for value in [candidate.label, candidate.address, candidate.category]
        if value
    )


def _regionalized_queries(query: str, context_text: str | None = None) -> list[str]:
    hints = _region_hints(query, context_text)
    variants: list[str | None] = []
    compact = _normalize(query)
    for prefix in _search_region_prefixes(hints):
        if _normalize(prefix) not in compact:
            variants.append(f"{prefix} {query}")
    variants.append(query)
    return _unique_queries(variants)


def _search_region_prefixes(hints: list[str]) -> list[str]:
    if "서울" in hints:
        return [prefix for prefix in ["서울", "종로" if "종로" in hints else None] if prefix]
    if "부산" in hints:
        return ["부산"]
    return []


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
    context_areas = _destination_context_areas_from_text(user_text)
    specific_destination = _specific_destination_hint_from_text(user_text)
    queries = [
        *_contextual_destination_queries(specific_destination, context_areas),
        *_contextual_destination_queries(destination_text, context_areas),
        specific_destination,
        destination_text,
        _destination_before_origin_hint_from_text(user_text),
    ]
    for match in re.findall(r"([^,.;\n]+?)(?:까지|으로|로)\s*(?:갈|가고|가야|도착|이동|$)", user_text):
        queries.append(_clean_query(match))
    for match in re.findall(r"(?:가서|하다가|그리고)\s*([^,.;\n]+?)(?:에서|까지|으로|로)", user_text):
        queries.append(_clean_query(match))
    return _unique_queries(queries)


def _destination_context_areas_from_text(user_text: str) -> list[str]:
    areas: list[str | None] = []

    for match in re.findall(
        r"(?:에서|부터)\s*([^,.;\n]+?)(?:까지|으로|로)\s*(?:가서|가고|갈|가야|가려고|이동|도착)",
        user_text,
    ):
        areas.append(match)

    for match in re.findall(
        r"([^,.;\n]+?)(?:까지|으로|로)\s*(?:가서|가고|갈|가야|가려고|이동|도착)",
        user_text,
    ):
        areas.append(match)

    for match in re.findall(r"([^,.;\n]+?)\s*가서", user_text):
        areas.append(match)

    return _unique_queries(areas)


def _contextual_destination_queries(
    destination: str | None,
    context_areas: list[str],
) -> list[str]:
    destination = _clean_query(destination)
    if not destination:
        return []

    queries: list[str | None] = []
    normalized_destination = _normalize(destination)
    for area in context_areas:
        cleaned_area = _clean_query(area)
        if not cleaned_area:
            continue
        normalized_area = _normalize(cleaned_area)
        if normalized_area in normalized_destination:
            continue
        aliases = [*_area_aliases(cleaned_area), cleaned_area]
        for alias in aliases:
            queries.append(f"{alias} {destination}")
            queries.append(f"{destination} {alias}")

    return _unique_queries(queries)


def _area_aliases(area: str) -> list[str]:
    aliases: list[str | None] = []
    compact = re.sub(r"\s+", "", area)
    aliases.append(re.sub(r"(입구)?역(?:\d+호선)?$", "", compact))
    aliases.append(re.sub(r"\d+호선$", "", compact))
    aliases.append(re.sub(r"(대학교|대학|캠퍼스)$", "", compact))
    return [alias for alias in _unique_queries(aliases) if _normalize(alias) != _normalize(area)]


def _origin_hint_from_text(user_text: str) -> str | None:
    matches = re.findall(r"([^,.;\n]+?)(?:에서|부터)", user_text)
    if not matches:
        return None
    return _clean_query(matches[0])


def _destination_hint_after_origin_from_text(user_text: str) -> str | None:
    patterns = [
        r"(?:에서|부터)\s*([^,.;\n]+?)(?:까지|으로|로(?=\s*(?:가고\s*싶|가야|갈|가기|가려고|도착|이동|$)))\s*(?:가고\s*싶|가야|갈|가기|가려고|도착|이동|$)",
        r"(?:에서|부터)\s*([^,.;\n]+?)(?:까지|으로)",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, user_text, flags=re.IGNORECASE)
        for value in matches:
            cleaned = _clean_query(value)
            if cleaned:
                return cleaned
    return None


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
        r"(.+?)(?:까지|으로|로(?=\s*(?:가고\s*싶|가야|갈|가기|가려고|도착|이동)))\s*(?:가고\s*싶|가야|갈|가기|가려고|도착|이동)",
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


def _rough_distance_meters(start: Coordinate, end: Coordinate) -> int:
    lat_meters = (end.lat - start.lat) * 111_000
    lng_meters = (end.lng - start.lng) * 111_000 * cos(radians(start.lat))
    return round(sqrt(lat_meters * lat_meters + lng_meters * lng_meters))


def _normalize(value: str) -> str:
    return value.lower().replace(" ", "")

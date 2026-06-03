import json
import os
import re

from api.schemas import Location, Task
from tools.kakao_local import _get_env_value
from tools.llm_intent import DEFAULT_INTENT_MODEL, _post_openai, _response_text
from tools.prompt_loader import kst_runtime_context, load_prompt


MANUAL_WAYPOINT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["waypoints"],
    "properties": {
        "waypoints": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "kind",
                    "label",
                    "poi_query",
                    "priority",
                    "required",
                    "reason",
                ],
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["print", "clinic", "recovery", "errand", "photo"],
                    },
                    "label": {"type": "string"},
                    "poi_query": {"type": "string"},
                    "priority": {"type": "integer", "minimum": 1, "maximum": 10},
                    "required": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
            },
        }
    },
}

_NORMALIZATION_CACHE: dict[str, list[Task]] = {}
_NORMALIZATION_CACHE_LIMIT = 80
REQUIRED_HINT_PREFIX = "필수 경유:"
OPTIONAL_HINT_PREFIX = "참고 경유:"
WAYPOINT_CATEGORY_KINDS = {
    "카페": "recovery",
    "산책": "recovery",
    "쉼": "recovery",
    "볼일": "errand",
    "식사": "recovery",
    "사진": "photo",
}


def normalize_manual_waypoints(
    waypoint_hints: list[str],
    user_text: str,
    origin: Location,
    destination: Location | None,
) -> list[Task]:
    hints = _clean_hints(waypoint_hints)
    if not hints:
        return []

    fallback = _normalize_with_rules(hints, user_text)
    llm_tasks = _normalize_with_llm(hints, user_text, origin, destination)
    tasks = llm_tasks or fallback
    return _dedupe_tasks(tasks)


def _normalize_with_llm(
    hints: list[str],
    user_text: str,
    origin: Location,
    destination: Location | None,
) -> list[Task] | None:
    if (os.environ.get("HYS_DISABLE_LLM") or _get_env_value("HYS_DISABLE_LLM")) == "1":
        return None

    api_key = _get_env_value("OPENAI_API_KEY")
    if not api_key:
        return None

    model = (
        os.environ.get("OPENAI_INTENT_MODEL")
        or _get_env_value("OPENAI_INTENT_MODEL")
        or DEFAULT_INTENT_MODEL
    )
    runtime_context = kst_runtime_context()
    cache_key = _cache_key(model, runtime_context, hints, user_text, origin, destination)
    if cache_key in _NORMALIZATION_CACHE:
        return _NORMALIZATION_CACHE[cache_key]

    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": load_prompt("manual_waypoint_normalization"),
            },
            {
                "role": "system",
                "content": runtime_context,
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_text": user_text,
                        "origin": _location_payload(origin),
                        "destination": _location_payload(destination),
                        "waypoint_hints": hints,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "manual_waypoint_normalization",
                "strict": True,
                "schema": MANUAL_WAYPOINT_SCHEMA,
            }
        },
        "max_output_tokens": 650,
    }

    raw = _post_openai(api_key, payload)
    if raw is None:
        return None

    text = _response_text(raw)
    if not text:
        return None

    try:
        data = json.loads(text)
        tasks = [
            _task_from_llm_item(item)
            for item in data.get("waypoints", [])
            if _clean_text(item.get("poi_query")) or _clean_text(item.get("label"))
        ]
    except (KeyError, TypeError, ValueError):
        return None

    if not tasks:
        return None

    _remember(cache_key, tasks)
    return tasks


def _normalize_with_rules(hints: list[str], user_text: str) -> list[Task]:
    tasks: list[Task] = []
    context = user_text.lower()
    for hint in hints:
        category = _hint_category(hint)
        clean_hint = _strip_hint_metadata(hint)
        lowered = clean_hint.lower()
        inferred_kind = _infer_kind(lowered, context)
        kind = inferred_kind if inferred_kind == "photo" else WAYPOINT_CATEGORY_KINDS.get(category or "", inferred_kind)
        query = _query_for_hint(clean_hint, kind)
        if not query:
            continue
        tasks.append(
            Task(
                kind=kind,
                label=_label_for_hint(clean_hint, kind),
                poi_query=query,
                priority=len(tasks) + 1,
                required=(
                    False
                    if _is_weak_hint(hint)
                    else _is_strong_hint(hint) or _is_required_hint(lowered, context)
                ),
            )
        )
    return tasks


def _task_from_llm_item(item: dict) -> Task:
    raw_label = _strip_hint_metadata(_clean_text(item.get("label")))
    raw_query = _strip_hint_metadata(
        _clean_text(item.get("poi_query")) or raw_label
    )
    kind = _clean_text(item.get("kind")) or _infer_kind(raw_query.lower(), "")
    inferred_kind = _infer_kind(f"{raw_label} {raw_query}".lower(), "")
    if inferred_kind == "photo":
        kind = "photo"
    query = _query_for_hint(raw_query, kind)
    label = raw_label or query
    return Task(
        kind=kind,
        label=label,
        poi_query=query,
        priority=int(item["priority"]),
        required=bool(item["required"]),
    )


def _infer_kind(hint: str, context: str) -> str:
    if any(marker in hint for marker in ["인생네컷", "네컷", "포토부스", "포토이즘", "사진관", "사진"]):
        return "photo"
    if any(marker in hint for marker in ["프린트", "프린터", "인쇄", "출력", "복사", "스캔"]):
        return "print"
    if any(marker in hint for marker in ["병원", "의원", "치과", "한의원", "진료"]):
        return "clinic"
    if any(
        marker in hint
        for marker in [
            "다이소",
            "편의점",
            "마트",
            "약국",
            "올리브영",
            "문구",
            "인생네컷",
            "네컷",
            "포토부스",
            "사야",
            "구매",
            "찾아야",
            "택배",
        ]
    ):
        return "errand"
    if "카페" in hint and any(
        marker in context for marker in ["프린트", "프린터", "인쇄", "출력", "복사", "스캔"]
    ):
        return "print"
    return "recovery"


def _query_for_hint(hint: str, kind: str) -> str:
    hint = _strip_route_suffix(hint)
    compact = hint.replace(" ", "")
    brand_keywords = [
        "스타벅스",
        "투썸",
        "이디야",
        "커피빈",
        "메가커피",
        "컴포즈",
        "다이소",
        "올리브영",
        "콩툰",
        "인생네컷",
        "포토부스",
        "포토이즘",
    ]
    for keyword in brand_keywords:
        if keyword.lower() in hint.lower() or keyword in compact:
            return keyword

    if kind == "photo":
        if "인생네컷" in compact or "네컷" in compact:
            return "인생네컷"
        if "포토이즘" in compact:
            return "포토이즘"
        if "포토부스" in compact:
            return "포토부스"
        return hint if len(hint) >= 2 else "인생네컷"
    if kind == "print" and any(marker in compact for marker in ["프린트카페", "프린터카페"]):
        return "프린트카페"
    if kind == "print":
        return hint if len(hint) >= 2 else "인쇄소"
    if "산책" in compact:
        return "공원"
    if "공원" in compact:
        return "공원"
    if "조용" in compact and any(marker in compact for marker in ["카페", "커피"]):
        return "조용한 카페"
    if any(marker in compact for marker in ["카페", "커피"]):
        return "카페"
    if "약국" in compact:
        return "약국"
    if "편의점" in compact:
        return "편의점"
    if "마트" in compact:
        return "마트"
    return hint


def _strip_route_suffix(hint: str) -> str:
    cleaned = re.sub(r"\s*(?:주변|근처|일대)$", "", hint).strip()
    return cleaned or hint


def _label_for_hint(hint: str, kind: str) -> str:
    if kind == "photo":
        return "사진 찍기"
    if kind == "print":
        return hint if hint else "출력하기"
    if kind == "clinic":
        return hint if hint else "진료 보기"
    if kind == "errand":
        return hint if hint else "심부름"
    return hint if hint else "쉴 곳"


def _is_required_hint(hint: str, context: str) -> bool:
    combined = f"{context} {hint}"
    if any(marker in combined for marker in ["있으면", "들러도", "괜찮으면", "후보", "추천"]):
        return False
    return True


def _dedupe_tasks(tasks: list[Task]) -> list[Task]:
    unique: list[Task] = []
    seen: set[str] = set()
    for task in tasks:
        query = _clean_text(task.poi_query)
        if not query:
            continue
        key = f"{task.kind}:{query.replace(' ', '').lower()}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(
            Task(
                kind=task.kind,
                label=_clean_text(task.label) or query,
                poi_query=query,
                priority=len(unique) + 1,
                required=task.required,
            )
        )
    return unique[:5]


def _clean_hints(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value)
        if not text:
            continue
        key = text.replace(" ", "").lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned[:5]


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _is_strong_hint(value: str) -> bool:
    return value.strip().startswith(REQUIRED_HINT_PREFIX)


def _is_weak_hint(value: str) -> bool:
    return value.strip().startswith(OPTIONAL_HINT_PREFIX)


def _strip_hint_strength(value: str) -> str:
    text = value.strip()
    if text.startswith(REQUIRED_HINT_PREFIX):
        text = text[len(REQUIRED_HINT_PREFIX) :].strip()
    if text.startswith(OPTIONAL_HINT_PREFIX):
        text = text[len(OPTIONAL_HINT_PREFIX) :].strip()
    return text


def _hint_category(value: str) -> str | None:
    text = _strip_hint_strength(value)
    match = re.match(r"^\[([^\]]+)\]\s*", text)
    if not match:
        return None
    return match.group(1).strip() or None


def _strip_hint_metadata(value: str) -> str:
    text = _strip_hint_strength(value)
    return re.sub(r"^\[[^\]]+\]\s*", "", text).strip()


def _location_payload(location: Location | None) -> dict | None:
    if location is None:
        return None
    return {
        "label": location.label,
        "lat": location.lat,
        "lng": location.lng,
    }


def _cache_key(
    model: str,
    runtime_context: str,
    hints: list[str],
    user_text: str,
    origin: Location,
    destination: Location | None,
) -> str:
    return json.dumps(
        {
            "model": model,
            "runtime_context": runtime_context,
            "hints": hints,
            "user_text": user_text,
            "origin": _location_payload(origin),
            "destination": _location_payload(destination),
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _remember(cache_key: str, tasks: list[Task]) -> None:
    if len(_NORMALIZATION_CACHE) >= _NORMALIZATION_CACHE_LIMIT:
        _NORMALIZATION_CACHE.pop(next(iter(_NORMALIZATION_CACHE)))
    _NORMALIZATION_CACHE[cache_key] = tasks

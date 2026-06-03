import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from api.schemas import Task
from tools.prompt_loader import load_prompt


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_INTENT_MODEL = "gpt-5-nano"
POI_VALIDATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["accepted", "reason"],
    "properties": {
        "accepted": {"type": "boolean"},
        "reason": {"type": "string"},
    },
}

PRINT_MARKERS = ["인쇄", "출력", "프린트", "프린터", "복사", "제본", "스캔"]
CAFE_MARKERS = ["카페", "커피", "coffee", "cafe"]
RESTFUL_PLACE_MARKERS = ["만화카페", "만화방", "북카페", "서점", "도서"]
SPECIAL_CAFE_MARKERS = [
    "보드게임",
    "보드게임카페",
    "만화카페",
    "만화방",
    "북카페",
    "스터디카페",
    "룸카페",
    "키즈카페",
    "애견카페",
    "고양이카페",
    "타로카페",
    "낚시카페",
    "멀티방",
    "파티룸",
    "vr",
]
GENERIC_CAFE_REQUEST_MARKERS = [
    "카페",
    "커피",
    "커피숍",
    "coffee",
    "cafe",
    "카공",
    "노트북",
    "과제",
    "공부",
    "작업",
    "조용",
    "커피한잔",
]
SCENIC_PLACE_MARKERS = ["공원", "숲", "산책", "호수", "관광명소", "명소", "여행"]
EVENT_MARKERS = ["축제", "이벤트", "행사"]
CLINIC_MARKERS = ["병원", "의료", "의원", "내과", "외과", "약국"]
ERRAND_MARKERS = [
    "다이소",
    "생활용품",
    "마트",
    "편의점",
    "상점",
    "스토어",
    "올리브영",
    "약국",
]
PHOTO_MARKERS = ["인생네컷", "네컷", "포토부스", "포토이즘", "사진관", "스튜디오"]

_VALIDATION_CACHE: dict[str, bool] = {}
_VALIDATION_CACHE_LIMIT = 160


def document_matches_task(document: dict, task: Task, user_text: str = "") -> bool:
    rule_result = _rule_match(document, task, user_text)
    if rule_result is not None:
        return rule_result

    llm_result = _llm_match(document, task, user_text)
    if llm_result is not None:
        return llm_result

    return True


def _rule_match(document: dict, task: Task, user_text: str) -> bool | None:
    name = str(document.get("place_name") or "")
    category = str(document.get("category_name") or "")
    category_group = str(document.get("category_group_name") or "")
    address = str(document.get("road_address_name") or document.get("address_name") or "")
    combined = _normalize(
        " ".join([name, category_group, category, address, task.label, task.poi_query])
    )
    candidate_combined = _normalize(f"{name} {category_group} {category} {address}")

    if task.kind == "recovery":
        query = _normalize(task.poi_query)
        if _has_any(candidate_combined, EVENT_MARKERS) and not _has_any(
            query, EVENT_MARKERS
        ):
            return False
        if _has_any(candidate_combined, PRINT_MARKERS):
            return False
        if _has_any(candidate_combined, ["병원", "약국", "의료"]):
            return False
        if _has_any(candidate_combined, ["다이소", "마트", "편의점", "생활용품"]):
            return False
        if _is_special_cafe_request(task, user_text):
            if _has_any(candidate_combined, SPECIAL_CAFE_MARKERS):
                return True
            if _has_any(candidate_combined, CAFE_MARKERS):
                return False
        if _is_generic_cafe_request(task, user_text):
            if _has_any(candidate_combined, SPECIAL_CAFE_MARKERS):
                return False
            if _has_any(candidate_combined, CAFE_MARKERS):
                return True
        if _has_any(
            candidate_combined,
            CAFE_MARKERS + RESTFUL_PLACE_MARKERS + SPECIAL_CAFE_MARKERS,
        ):
            return True
        if _has_any(candidate_combined, SCENIC_PLACE_MARKERS) and (
            _has_any(_normalize(user_text), ["산책", "걷", "예쁜길", "지나서", "거쳐"])
            or (query and query in candidate_combined)
        ):
            return True
        return None

    if task.kind == "print":
        if _has_any(candidate_combined, PRINT_MARKERS):
            return True
        if _has_any(candidate_combined, CAFE_MARKERS) and not _has_any(
            candidate_combined, PRINT_MARKERS
        ):
            return False
        return None

    if task.kind == "clinic":
        if _has_any(candidate_combined, CLINIC_MARKERS):
            return True
        if _has_any(candidate_combined, CAFE_MARKERS):
            return False
        return None

    if task.kind == "errand":
        if _has_any(candidate_combined, ERRAND_MARKERS):
            return True
        if _has_any(candidate_combined, CAFE_MARKERS) and not _has_any(
            combined, CAFE_MARKERS
        ):
            return False
        return None

    if task.kind == "photo":
        if _has_any(candidate_combined, PHOTO_MARKERS):
            return True
        if _has_any(candidate_combined, CAFE_MARKERS + ERRAND_MARKERS + CLINIC_MARKERS):
            return False
        return None

    if task.kind == "place":
        query = _normalize(task.poi_query)
        if query and query in candidate_combined:
            return True
        return None

    return None


def _is_special_cafe_request(task: Task, user_text: str) -> bool:
    text = _normalize(" ".join([task.label, task.poi_query, user_text]))
    return _has_any(text, SPECIAL_CAFE_MARKERS)


def _is_generic_cafe_request(task: Task, user_text: str) -> bool:
    text = _normalize(" ".join([task.label, task.poi_query, user_text]))
    if not _has_any(text, GENERIC_CAFE_REQUEST_MARKERS):
        return False
    return not _has_any(text, SPECIAL_CAFE_MARKERS + PRINT_MARKERS)


def _llm_match(document: dict, task: Task, user_text: str) -> bool | None:
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
    cache_key = json.dumps(
        {
            "model": model,
            "task": task.model_dump(),
            "document": {
                "place_name": document.get("place_name"),
                "category_name": document.get("category_name"),
                "category_group_code": document.get("category_group_code"),
                "category_group_name": document.get("category_group_name"),
                "address_name": document.get("address_name"),
                "road_address_name": document.get("road_address_name"),
                "phone": document.get("phone"),
                "place_url": document.get("place_url"),
                "distance": document.get("distance"),
            },
            "user_text": user_text,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    if cache_key in _VALIDATION_CACHE:
        return _VALIDATION_CACHE[cache_key]

    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": load_prompt("poi_candidate_validation")},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_text": user_text,
                        "task": task.model_dump(),
                        "candidate": {
                            "place_name": document.get("place_name"),
                            "category_name": document.get("category_name"),
                            "category_group_code": document.get("category_group_code"),
                            "category_group_name": document.get("category_group_name"),
                            "address_name": document.get("address_name"),
                            "road_address_name": document.get("road_address_name"),
                            "phone": document.get("phone"),
                            "place_url": document.get("place_url"),
                            "distance": document.get("distance"),
                        },
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "poi_candidate_validation",
                "strict": True,
                "schema": POI_VALIDATION_SCHEMA,
            }
        },
        "reasoning": {"effort": "minimal"},
        "max_output_tokens": 400,
    }

    raw = _post_openai(api_key, payload)
    if raw is None:
        return None

    text = _response_text(raw)
    if not text:
        return None

    try:
        accepted = bool(json.loads(text)["accepted"])
    except (KeyError, TypeError, ValueError):
        return None

    _remember_validation(cache_key, accepted)
    return accepted


def _post_openai(api_key: str, payload: dict) -> dict | None:
    request = Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return None


def _response_text(payload: dict) -> str | None:
    direct = payload.get("output_text")
    if isinstance(direct, str):
        return direct

    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if isinstance(text, str):
                return text
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


def _remember_validation(cache_key: str, accepted: bool) -> None:
    if len(_VALIDATION_CACHE) >= _VALIDATION_CACHE_LIMIT:
        _VALIDATION_CACHE.pop(next(iter(_VALIDATION_CACHE)))
    _VALIDATION_CACHE[cache_key] = accepted


def _has_any(text: str, markers: list[str]) -> bool:
    return any(_normalize(marker) in text for marker in markers)


def _normalize(value: str) -> str:
    return value.lower().replace(" ", "")

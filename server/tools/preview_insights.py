import json
import os
import re

from pydantic import ValidationError

from api.schemas import PreviewInsight
from tools.extract_intent import extract_intent
from tools.extract_route_locations import extract_route_locations
from tools.kakao_local import _get_env_value
from tools.llm_intent import DEFAULT_INTENT_MODEL, _post_openai, _response_text
from tools.prompt_loader import kst_runtime_context, load_prompt


PREVIEW_INSIGHTS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["insights"],
    "properties": {
        "insights": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "value", "kind", "strength"],
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": ["route", "time", "stop", "task", "mood"],
                    },
                    "strength": {
                        "type": "string",
                        "enum": ["strong", "weak", "none"],
                    },
                },
            },
        }
    },
}

OPTIONAL_SIGNAL_MARKERS = [
    "있으면",
    "괜찮으면",
    "들러도돼",
    "들러도괜찮",
    "후보",
    "추천",
    "가능하면",
    "되면",
]
REQUIRED_SIGNAL_MARKERS = [
    "들러야",
    "가야",
    "갈거야",
    "갈꺼야",
    "갈래",
    "찍을래",
    "찍기로",
    "사야",
    "살거",
    "찾아야",
    "해야",
    "지나서",
    "거쳐서",
    "들러서",
    "약속",
    "예약",
]


def build_preview_insights(
    user_text: str,
    origin_text: str | None,
    destination_text: str | None,
    active_mood: str | None,
) -> tuple[list[PreviewInsight], str, list[str]]:
    text = user_text.strip()
    route_hints = extract_route_locations(text) if _needs_route_hints(
        text,
        origin_text,
        destination_text,
    ) else None
    intent = extract_intent(text) if text else None

    origin = _first_present(route_hints.origin_text if route_hints else None, origin_text)
    destination = _first_present(
        route_hints.destination_text if route_hints else None,
        destination_text,
        intent.constraints.destination if intent else None,
    )
    llm_insights = _preview_insights_with_llm(
        text=text,
        origin=origin,
        destination=destination,
        active_mood=active_mood,
        intent=intent,
    )
    if llm_insights:
        mood_candidates = intent.mood_candidates if intent else _default_mood_candidates()
        return llm_insights, "llm", mood_candidates[:4]

    insights: list[PreviewInsight] = []
    if origin or destination:
        insights.append(
            PreviewInsight(
                label="이동",
                value=f"{origin or '출발지'} → {destination or '도착지'}",
                kind="route",
                strength="none",
            )
        )

    if intent and intent.constraints.deadline:
        insights.append(
            PreviewInsight(
                label="시간",
                value=f"{intent.constraints.deadline} 전 도착 우선",
                kind="time",
                strength="none",
            )
        )
    elif _has_time_hint(text):
        insights.append(
            PreviewInsight(label="시간", value="시간 조건 감지", kind="time", strength="none")
        )
    else:
        insights.append(
            PreviewInsight(
                label="시간",
                value="감지된 시간 조건 없음",
                kind="time",
                strength="none",
            )
        )

    stop_points = _stop_insights(text, destination)
    insights.extend(stop_points)

    if intent:
        existing_keys = {_insight_identity(insight) for insight in insights}
        for task_point in _task_insights(intent.tasks):
            key = _insight_identity(task_point)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            insights.append(task_point)

        emotion_point = _emotion_insight(intent.emotion.primary)
        if emotion_point:
            insights.append(emotion_point)

    mood_candidates = intent.mood_candidates if intent and text else []
    mood_label = (
        _first_mood_label(active_mood, mood_candidates)
        if _has_condition_signal(text, mood_candidates, active_mood)
        else None
    )
    _ensure_mood_insight(insights, mood_label)

    source = "llm" if route_hints and route_hints.source == "llm" else "rules"
    return _limit_insights(insights), source, mood_candidates[:4]


def _needs_route_hints(
    text: str,
    origin_text: str | None,
    destination_text: str | None,
) -> bool:
    if not text:
        return False
    generic_labels = {"집", "학교", "회사"}
    return (
        not origin_text
        or not destination_text
        or origin_text in generic_labels
        or destination_text in generic_labels
    )


def _preview_insights_with_llm(
    text: str,
    origin: str | None,
    destination: str | None,
    active_mood: str | None,
    intent,
) -> list[PreviewInsight] | None:
    if not text:
        return None
    if (os.environ.get("HYS_DISABLE_LLM") or _get_env_value("HYS_DISABLE_LLM")) == "1":
        return None

    api_key = _get_env_value("OPENAI_API_KEY")
    if not api_key:
        return None
    if not _preview_llm_enabled():
        return None

    model = (
        os.environ.get("OPENAI_PREVIEW_MODEL")
        or _get_env_value("OPENAI_PREVIEW_MODEL")
        or os.environ.get("OPENAI_INTENT_MODEL")
        or _get_env_value("OPENAI_INTENT_MODEL")
        or DEFAULT_INTENT_MODEL
    )
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": load_prompt("preview_insights"),
            },
            {
                "role": "system",
                "content": kst_runtime_context(),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_text": text,
                        "origin_text": origin,
                        "destination_text": destination,
                        "active_mood": active_mood,
                        "deadline": intent.constraints.deadline if intent else None,
                        "emotion_primary": intent.emotion.primary if intent else None,
                        "tasks": [
                            {
                                "kind": task.kind,
                                "label": task.label,
                                "poi_query": task.poi_query,
                                "required": task.required,
                            }
                            for task in (intent.tasks if intent else [])
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "preview_insights",
                "strict": True,
                "schema": PREVIEW_INSIGHTS_SCHEMA,
            }
        },
        "reasoning": {"effort": "minimal"},
        "max_output_tokens": 1000,
    }

    raw = _post_openai_with_timeout(api_key, payload, 5)
    if raw is None:
        return None

    text_output = _response_text(raw)
    if not text_output:
        return None

    try:
        data = json.loads(text_output)
        insights = [
            PreviewInsight(**insight) for insight in data.get("insights", [])
        ]
    except (TypeError, ValueError, ValidationError):
        return None

    return _repair_preview_insights(insights, origin, destination, intent, active_mood, text)


def _post_openai_with_timeout(api_key: str, payload: dict, timeout: int):
    try:
        return _post_openai(api_key, payload, timeout)
    except TypeError:
        return _post_openai(api_key, payload)


def _preview_llm_enabled() -> bool:
    value = os.environ.get("HYS_ENABLE_PREVIEW_LLM") or _get_env_value(
        "HYS_ENABLE_PREVIEW_LLM"
    )
    return value == "1"


def _repair_preview_insights(
    insights: list[PreviewInsight],
    origin: str | None,
    destination: str | None,
    intent,
    active_mood: str | None,
    text: str,
) -> list[PreviewInsight] | None:
    if not insights:
        return None

    repaired = [_clean_preview_insight(insight, text) for insight in insights]
    route_value = f"{origin or '출발지'} → {destination or '도착지'}"
    if repaired[0].kind != "route":
        repaired.insert(
            0,
            PreviewInsight(
                label="경로",
                value=route_value,
                kind="route",
                strength="none",
            ),
        )
    elif origin or destination:
        repaired[0] = PreviewInsight(
            label=repaired[0].label,
            value=route_value,
            kind="route",
            strength=repaired[0].strength or "none",
        )

    repaired_time_value = (
        f"{intent.constraints.deadline} 전 도착 우선"
        if intent and intent.constraints.deadline
        else None
    )
    if repaired_time_value:
        repaired = [
            PreviewInsight(
                label=insight.label,
                value=repaired_time_value,
                kind=insight.kind,
                strength=insight.strength or "none",
            )
            if insight.kind == "time"
            else insight
            for insight in repaired
        ]

    if not any(insight.kind == "time" for insight in repaired):
        time_value = (
            repaired_time_value if repaired_time_value else "감지된 시간 조건 없음"
        )
        repaired.insert(
            1,
            PreviewInsight(
                label="시간",
                value=time_value,
                kind="time",
                strength="none",
            ),
        )

    mood_label = (
        _first_mood_label(active_mood, intent.mood_candidates if intent else [])
        if _has_condition_signal(
            " ".join(insight.value for insight in repaired),
            intent.mood_candidates if intent else [],
            active_mood,
        )
        else None
    )
    _ensure_mood_insight(repaired, mood_label)

    existing_keys = {_insight_identity(insight) for insight in repaired}
    for stop_insight in _stop_insights(text, destination):
        key = _insight_identity(stop_insight)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        repaired.append(stop_insight)

    unique: list[PreviewInsight] = []
    seen: set[str] = set()
    for insight in repaired:
        key = _insight_identity(insight)
        if key in seen:
            continue
        seen.add(key)
        unique.append(insight)

    return _limit_insights(unique)


def _task_insights(tasks) -> list[PreviewInsight]:
    insights: list[PreviewInsight] = []
    for task in tasks or []:
        insight = _task_insight([task])
        if insight:
            insights.append(insight)
    return insights


def _task_insight(tasks) -> PreviewInsight | None:
    if not tasks:
        return None

    primary = tasks[0]
    if primary.kind == "recovery":
        return PreviewInsight(
            label="쉴 곳",
            value="잠깐 쉬어갈 장소",
            kind="stop",
            strength="weak" if not primary.required else "strong",
        )
    if primary.kind == "print":
        return PreviewInsight(
            label="할 일",
            value="인쇄 가능한 지점 반영",
            kind="task",
            strength="strong" if primary.required else "weak",
        )
    if primary.kind == "clinic":
        return PreviewInsight(
            label="할 일",
            value="병원 방문 동선 반영",
            kind="task",
            strength="strong" if primary.required else "weak",
        )
    if primary.kind == "errand":
        return PreviewInsight(
            label="들를 곳",
            value=primary.label,
            kind="task",
            strength="strong" if primary.required else "weak",
        )
    if primary.kind == "photo":
        return PreviewInsight(
            label="사진 찍기",
            value=primary.poi_query or primary.label,
            kind="task",
            strength="strong" if primary.required else "weak",
        )
    return PreviewInsight(
        label="할 일",
        value=primary.label,
        kind="task",
        strength="strong" if primary.required else "weak",
    )


def _stop_insights(text: str, destination: str | None = None) -> list[PreviewInsight]:
    insights: list[PreviewInsight] = []
    waypoints = _waypoint_hints(text, destination)
    waypoint = waypoints[0] if waypoints else None
    area = waypoint or _area_hint(text)

    for waypoint in waypoints:
        if _is_service_waypoint(waypoint):
            continue
        insights.append(
            PreviewInsight(
                label="거쳐 갈 곳",
                value=f"{waypoint} 주변",
                kind="stop",
                strength="strong",
            )
        )

    if (
        any(marker in text for marker in ["걷", "산책", "돌아다니", "주변", "근처", "선선"])
        and not _has_walking_avoidance(text)
    ):
        value = f"{area} 주변 산책" if area else "가볍게 걸을 곳"
        insights.append(
            PreviewInsight(label="산책 후보", value=value, kind="stop", strength="weak")
        )

    if any(marker in text for marker in ["카페", "커피", "과제", "공부", "작업"]):
        value = f"{area} 근처" if area else "카페에서 과제"
        keyword = _first_matching_keyword(text, ["카페", "커피", "과제", "공부", "작업"], "카페")
        insights.append(
            PreviewInsight(
                label="작업할 카페",
                value=value,
                kind="stop",
                strength=_strength_for_keyword(text, keyword, default="strong"),
            )
        )

    if any(marker in text for marker in ["쉬", "휴식", "조용"]):
        value = f"{area} 근처 조용한 곳" if area else "잠깐 쉬어갈 곳"
        keyword = _first_matching_keyword(text, ["쉬", "휴식", "조용"], "쉬")
        insights.append(
            PreviewInsight(
                label="쉴 곳",
                value=value,
                kind="stop",
                strength=_strength_for_keyword(text, keyword, default="strong"),
            )
        )

    if any(
        marker in text
        for marker in [
            "다이소",
            "살거",
            "살 것",
            "사야",
            "구매",
            "장보기",
            "마트",
            "편의점",
            "약국",
            "올리브영",
            "픽업",
            "찾으러",
        ]
    ):
        value = _errand_value(text)
        keyword = _errand_keyword(value, text)
        insights.append(
            PreviewInsight(
                label="들를 곳",
                value=value,
                kind="task",
                strength=_strength_for_keyword(text, keyword, default="strong"),
            )
        )

    if any(marker in text for marker in ["인생네컷", "네컷", "포토부스", "포토이즘", "사진관"]):
        value = _photo_value(text)
        insights.append(
            PreviewInsight(
                label="사진 찍기",
                value=value,
                kind="task",
                strength=_strength_for_keyword(text, value, default="strong"),
            )
        )

    unique: list[PreviewInsight] = []
    seen: set[str] = set()
    for insight in insights:
        if insight.value in seen:
            continue
        seen.add(insight.value)
        unique.append(insight)
    return unique


def _errand_value(text: str) -> str:
    for keyword in ["다이소", "올리브영", "약국", "편의점", "마트"]:
        if keyword in text:
            return f"{keyword} 들르기"
    if "픽업" in text or "찾으러" in text:
        return "물건 픽업"
    if "장보기" in text:
        return "장보기"
    return "살 것 사기"


def _errand_keyword(value: str, text: str) -> str:
    for keyword in ["다이소", "올리브영", "약국", "편의점", "마트"]:
        if keyword in value or keyword in text:
            return keyword
    if "픽업" in value or "픽업" in text or "찾으러" in text:
        return "픽업"
    return "살 것"


def _photo_value(text: str) -> str:
    for keyword in ["인생네컷", "포토이즘", "포토부스", "사진관"]:
        if keyword in text:
            return keyword
    if "네컷" in text:
        return "인생네컷"
    return "사진 찍기"


def _first_matching_keyword(
    text: str,
    keywords: list[str],
    fallback: str,
) -> str:
    for keyword in keywords:
        if keyword in text:
            return keyword
    return fallback


def _emotion_insight(primary: str) -> PreviewInsight | None:
    if primary == "tired":
        return PreviewInsight(label="상태", value="피로 낮은 길 우선", kind="mood", strength="none")
    if primary == "hurried":
        return PreviewInsight(label="상태", value="우회보다 도착 시간 우선", kind="time", strength="none")
    if primary == "anxious":
        return PreviewInsight(label="상태", value="혼잡 낮은 길 우선", kind="mood", strength="none")
    return None


def _empty_insight(index: int) -> PreviewInsight:
    defaults = [
        PreviewInsight(label="이동", value="출발지와 도착지 확인", kind="route", strength="none"),
        PreviewInsight(label="시간", value="감지된 시간 조건 없음", kind="time", strength="none"),
        PreviewInsight(label="컨디션", value="컨디션 조건 없음", kind="mood", strength="none"),
    ]
    return defaults[index % len(defaults)]


def _limit_insights(insights: list[PreviewInsight]) -> list[PreviewInsight]:
    return insights[:12]


def _clean_preview_insight(
    insight: PreviewInsight,
    context_text: str = "",
) -> PreviewInsight:
    if insight.kind not in {"stop", "task"}:
        return insight
    cleaned_value = _clean_waypoint_display_value(insight.value)
    return PreviewInsight(
        label=insight.label,
        value=cleaned_value,
        kind=insight.kind,
        strength=_semantic_waypoint_strength(
            context_text,
            insight.label,
            cleaned_value,
            insight.strength or "none",
        ),
    )


def _insight_identity(insight: PreviewInsight) -> str:
    if insight.kind in {"stop", "task"}:
        return f"waypoint:{_normalize(_waypoint_identity_value(insight.value))}"
    return f"{insight.kind}:{_normalize(insight.label)}:{_normalize(insight.value)}"


def _waypoint_identity_value(value: str) -> str:
    cleaned = _clean_waypoint_display_value(value)
    compact = cleaned.replace(" ", "")
    for keyword in ["다이소", "인생네컷", "스타벅스", "약국", "편의점", "올리브영"]:
        if keyword in compact:
            return keyword
    cleaned = re.sub(r"\s*주변(?:\s*산책)?$", "", cleaned)
    cleaned = re.sub(r"\s*(?:들르기|들리기|들를 곳|가기|구매|방문|후보|확인)$", "", cleaned)
    return cleaned.strip()


def _clean_waypoint_display_value(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(
        r"^(?:아\s*)?(?:친구\s*)?(?:가기\s*전에|전에|만나서|만난\s*뒤|만나고)\s*",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _default_mood_candidates() -> list[str]:
    return ["피곤", "바쁨", "여유", "휴식"]


def _has_condition_signal(
    text: str,
    mood_candidates: list[str],
    active_mood: str | None,
) -> bool:
    if active_mood and active_mood.strip():
        return True
    if not text.strip():
        return False
    if not mood_candidates:
        return False
    if mood_candidates[:4] == _default_mood_candidates():
        return False
    return True


def _first_mood_label(active_mood: str | None, mood_candidates: list[str]) -> str | None:
    if active_mood and active_mood.strip():
        return active_mood.strip()
    for label in mood_candidates:
        if label and label.strip():
            return label.strip()
    return None


def _ensure_mood_insight(insights: list[PreviewInsight], mood_label: str | None) -> None:
    if any(insight.kind == "mood" for insight in insights):
        return

    if len(insights) < 4:
        value = (
            f"{mood_label} 기준으로 경로 비교"
            if mood_label
            else "컨디션 조건 없음"
        )
        insights.append(
            PreviewInsight(
                label="컨디션",
                value=value,
                kind="mood",
                strength="none",
            )
        )


def _first_present(*values: str | None) -> str | None:
    for value in values:
        if value and value.strip():
            return value.strip()
    return None


def _has_time_hint(text: str) -> bool:
    return bool(
        re.search(r"\d+\s*(?:시|분)\s*(?:까지|전|안에)?", text)
        or re.search(r"(?:오전|오후)\s*\d+", text)
        or re.search(r"\d+\s*시간\s*안", text)
        or re.search(r"\d+\s*시간\s*(?:반|\d+\s*분)?\s*남", text)
        or any(marker in text for marker in ["deadline", "마감", "늦지", "촉박"])
    )


def _has_optional_signal(text: str) -> bool:
    compact = text.replace(" ", "")
    return any(marker in compact for marker in OPTIONAL_SIGNAL_MARKERS)


def _semantic_waypoint_strength(
    text: str,
    label: str,
    value: str,
    current: str,
) -> str:
    keyword = _strength_keyword(label, value, text)
    if not keyword:
        return current if current in {"strong", "weak"} else "none"
    return _strength_for_keyword(
        text,
        keyword,
        default=current if current in {"strong", "weak"} else "strong",
    )


def _strength_keyword(label: str, value: str, text: str) -> str | None:
    combined = f"{label} {value}"
    for keyword in [
        "인생네컷",
        "포토이즘",
        "포토부스",
        "사진관",
        "다이소",
        "올리브영",
        "약국",
        "편의점",
        "마트",
        "상도 건영 106동",
        "상도건영",
        "카페",
        "커피",
    ]:
        if keyword in combined:
            return keyword
    if "네컷" in combined:
        return "네컷"
    if "사진" in combined:
        for keyword in ["인생네컷", "포토이즘", "포토부스", "사진관", "네컷"]:
            if keyword in text:
                return keyword
    return None


def _strength_for_keyword(
    text: str,
    keyword: str,
    default: str = "strong",
) -> str:
    segment = _context_segment(text, keyword)
    if not segment:
        return default
    compact = segment.replace(" ", "")
    has_optional = any(marker in compact for marker in OPTIONAL_SIGNAL_MARKERS)
    has_required = any(marker in compact for marker in REQUIRED_SIGNAL_MARKERS)

    if has_optional and not _has_hard_required_signal(compact):
        return "weak"
    if has_required:
        return "strong"
    return default


def _context_segment(text: str, keyword: str, radius: int = 28) -> str:
    aliases = _keyword_aliases(keyword)
    positions = [text.find(alias) for alias in aliases if alias and text.find(alias) >= 0]
    if not positions:
        return ""
    index = min(positions)
    start = max(0, index - radius)
    end = min(len(text), index + len(keyword) + radius)
    return text[start:end]


def _keyword_aliases(keyword: str) -> list[str]:
    aliases = [keyword]
    if keyword == "인생네컷":
        aliases.extend(["네컷"])
    if keyword == "네컷":
        aliases.extend(["인생네컷"])
    if keyword == "상도 건영 106동":
        aliases.extend(["상도건영", "상도 건영"])
    if keyword == "상도건영":
        aliases.extend(["상도 건영 106동", "상도 건영"])
    return aliases


def _has_hard_required_signal(compact: str) -> bool:
    return any(marker in compact for marker in ["꼭", "반드시", "무조건", "필수"])


def _has_walking_avoidance(text: str) -> bool:
    compact = text.replace(" ", "")
    return any(
        marker in compact
        for marker in [
            "걷기싫",
            "걷는건최대한줄",
            "걷는건줄",
            "걷는것은줄",
            "걷는건최소",
            "걷는거최소",
            "걷는건최대한피",
            "걷고싶지",
            "걷는건싫",
        ]
    )


def _is_service_waypoint(value: str) -> bool:
    normalized = _normalize(value)
    return any(
        _normalize(keyword) in normalized
        for keyword in ["다이소", "올리브영", "약국", "편의점", "마트", "인생네컷", "포토부스", "포토이즘", "사진관"]
    )


def _waypoint_hint(text: str, destination: str | None = None) -> str | None:
    hints = _waypoint_hints(text, destination)
    return hints[0] if hints else None


def _waypoint_hints(text: str, destination: str | None = None) -> list[str]:
    patterns = [
        r"(?:에서|부터)\s*([가-힣A-Za-z0-9\s]+?)\s*(?:지나서|지나|거쳐서|거쳐|들러서|들러|경유)\s*[가-힣A-Za-z0-9\s]+?(?:까지|으로|로|에)",
        r"([가-힣A-Za-z0-9\s]+?)\s*(?:지나서|지나|거쳐서|거쳐|들러서|들러|경유)\s*[가-힣A-Za-z0-9\s]+?(?:까지|으로|로|에)",
        r"(?:에서|부터)\s*([가-힣A-Za-z0-9\s]+?)(?:까지|으로|로|에)\s*(?:가서|간\s*뒤|갔다가|들러|들렀다가|경유)",
        r"([가-힣A-Za-z0-9\s]+?)(?:까지|으로|로|에)\s*(?:가서|간\s*뒤|갔다가|들러|들렀다가|경유)",
        r"(?:가기\s*전에|전에)\s*([가-힣A-Za-z0-9\s]+?)(?:에)?\s*(?:들러야|들러|갔다가|가야)",
        r"(?:만나서|만난\s*뒤|만나고)\s*([가-힣A-Za-z0-9\s]+?)(?:도)?\s*(?:갈거야|갈\s*거야|가야|들러|찍)",
    ]
    hints: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for value in matches:
            cleaned = _clean_hint(value)
            if not cleaned or _normalize(cleaned) == _normalize(destination or ""):
                continue
            key = _normalize(cleaned)
            if key in seen:
                continue
            seen.add(key)
            hints.append(cleaned)

    for keyword in ["다이소", "올리브영", "약국", "편의점", "마트", "인생네컷", "포토부스"]:
        if keyword in text and _normalize(keyword) not in seen:
            seen.add(_normalize(keyword))
            hints.append(keyword)
    if "네컷" in text and _normalize("인생네컷") not in seen:
        seen.add(_normalize("인생네컷"))
        hints.append("인생네컷")

    return hints


def _area_hint(text: str) -> str | None:
    direct = re.search(r"([가-힣A-Za-z0-9]+)\s*(?:주변|근처)", text)
    if direct:
        return direct.group(1)

    destination = re.search(
        r"([가-힣A-Za-z0-9]+)\s*(?:까지|으로|로)\s*(?:갈|가고|가야|도착|이동)",
        text,
    )
    if destination:
        return destination.group(1)

    return None


def _clean_hint(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.split(r"(?:하다가|그리고|,|\.|;)", value)[-1]
    cleaned = re.sub(
        r"^.*(?:에서|부터)\s*(?:출발해서|출발하고|출발|시작해서|시작)?\s*",
        "",
        cleaned.strip(),
    )
    cleaned = re.sub(r"^(?:가기\s*전에|전에|만나서|만난\s*뒤|만나고)\s*", "", cleaned)
    cleaned = re.sub(r"\s*(에서|부터|으로|로|까지|에)$", "", cleaned).strip()
    return cleaned if len(cleaned) >= 2 else None


def _normalize(value: str) -> str:
    return value.lower().replace(" ", "")

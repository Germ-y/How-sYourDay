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
                "required": ["label", "value", "kind"],
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": ["route", "time", "stop", "task", "mood"],
                    },
                },
            },
        }
    },
}


def build_preview_insights(
    user_text: str,
    origin_text: str | None,
    destination_text: str | None,
    active_mood: str | None,
) -> tuple[list[PreviewInsight], str, list[str]]:
    text = user_text.strip()
    route_hints = extract_route_locations(text) if text else None
    intent = extract_intent(text) if text else None

    origin = _first_present(route_hints.origin_text if route_hints else None, origin_text)
    destination = _first_present(
        route_hints.destination_text if route_hints else None,
        intent.constraints.destination if intent else None,
        destination_text,
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
            )
        )

    if intent and intent.constraints.deadline:
        insights.append(
            PreviewInsight(
                label="시간",
                value=f"{intent.constraints.deadline} 전 도착 우선",
                kind="time",
            )
        )
    elif _has_time_hint(text):
        insights.append(
            PreviewInsight(label="시간", value="시간 조건 감지", kind="time")
        )
    else:
        insights.append(
            PreviewInsight(label="시간", value="감지된 시간 조건 없음", kind="time")
        )

    stop_points = _stop_insights(text, destination)
    insights.extend(stop_points)

    if intent:
        task_point = None if stop_points else _task_insight(intent.tasks)
        if task_point:
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
        "max_output_tokens": 600,
    }

    raw = _post_openai(api_key, payload)
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

    return _repair_preview_insights(insights, origin, destination, intent)


def _repair_preview_insights(
    insights: list[PreviewInsight],
    origin: str | None,
    destination: str | None,
    intent,
) -> list[PreviewInsight] | None:
    if not insights:
        return None

    repaired = list(insights)
    route_value = f"{origin or '출발지'} → {destination or '도착지'}"
    if repaired[0].kind != "route":
        repaired.insert(0, PreviewInsight(label="경로", value=route_value, kind="route"))
    elif origin or destination:
        repaired[0] = PreviewInsight(label=repaired[0].label, value=route_value, kind="route")

    if not any(insight.kind == "time" for insight in repaired):
        time_value = (
            f"{intent.constraints.deadline} 전 도착 우선"
            if intent and intent.constraints.deadline
            else "감지된 시간 조건 없음"
        )
        repaired.insert(1, PreviewInsight(label="시간", value=time_value, kind="time"))

    unique: list[PreviewInsight] = []
    seen: set[str] = set()
    for insight in repaired:
        key = f"{insight.kind}:{insight.label}:{insight.value}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(insight)

    return _limit_insights(unique)


def _task_insight(tasks) -> PreviewInsight | None:
    if not tasks:
        return None

    primary = tasks[0]
    if primary.kind == "recovery":
        return PreviewInsight(label="쉴 곳", value="잠깐 쉬어갈 장소", kind="stop")
    if primary.kind == "print":
        return PreviewInsight(label="할 일", value="인쇄 가능한 지점 반영", kind="task")
    if primary.kind == "clinic":
        return PreviewInsight(label="할 일", value="병원 방문 동선 반영", kind="task")
    if primary.kind == "errand":
        return PreviewInsight(label="들를 곳", value=primary.label, kind="task")
    return PreviewInsight(label="할 일", value=primary.label, kind="task")


def _stop_insights(text: str, destination: str | None = None) -> list[PreviewInsight]:
    insights: list[PreviewInsight] = []
    waypoint = _waypoint_hint(text, destination)
    area = waypoint or _area_hint(text)

    if waypoint:
        insights.append(
            PreviewInsight(
                label="거쳐 갈 곳",
                value=f"{waypoint} 주변",
                kind="stop",
            )
        )

    if any(marker in text for marker in ["걷", "산책", "돌아다니", "주변", "근처", "선선"]):
        value = f"{area} 주변 산책" if area else "가볍게 걸을 곳"
        insights.append(PreviewInsight(label="산책 후보", value=value, kind="stop"))

    if any(marker in text for marker in ["카페", "커피", "과제", "공부", "작업"]):
        value = f"{area} 근처" if area else "카페에서 과제"
        insights.append(PreviewInsight(label="작업할 카페", value=value, kind="stop"))

    if any(marker in text for marker in ["쉬", "휴식", "조용"]):
        value = f"{area} 근처 조용한 곳" if area else "잠깐 쉬어갈 곳"
        insights.append(PreviewInsight(label="쉴 곳", value=value, kind="stop"))

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
        insights.append(PreviewInsight(label="들를 곳", value=value, kind="task"))

    unique: list[PreviewInsight] = []
    seen: set[str] = set()
    for insight in insights:
        if insight.value in seen:
            continue
        seen.add(insight.value)
        unique.append(insight)
    return unique[:5]


def _errand_value(text: str) -> str:
    for keyword in ["다이소", "올리브영", "약국", "편의점", "마트"]:
        if keyword in text:
            return f"{keyword} 들르기"
    if "픽업" in text or "찾으러" in text:
        return "물건 픽업"
    if "장보기" in text:
        return "장보기"
    return "살 것 사기"


def _emotion_insight(primary: str) -> PreviewInsight | None:
    if primary == "tired":
        return PreviewInsight(label="상태", value="피로 낮은 길 우선", kind="mood")
    if primary == "hurried":
        return PreviewInsight(label="상태", value="우회보다 도착 시간 우선", kind="time")
    if primary == "anxious":
        return PreviewInsight(label="상태", value="혼잡 낮은 길 우선", kind="mood")
    return None


def _empty_insight(index: int) -> PreviewInsight:
    defaults = [
        PreviewInsight(label="이동", value="출발지와 도착지 확인", kind="route"),
        PreviewInsight(label="들를 곳", value="선호 장소를 후보로 확인", kind="stop"),
        PreviewInsight(label="상태", value="컨디션 기준으로 경로 비교", kind="mood"),
        PreviewInsight(label="취향", value="선호 지도 반영", kind="stop"),
    ]
    return defaults[index]


def _limit_insights(insights: list[PreviewInsight]) -> list[PreviewInsight]:
    return insights[:8]


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
    if not mood_label or any(insight.kind == "mood" for insight in insights):
        return

    if len(insights) < 4:
        insights.append(
            PreviewInsight(
                label="컨디션",
                value=f"{mood_label} 기준으로 경로 비교",
                kind="mood",
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
        or any(marker in text for marker in ["deadline", "마감", "늦지", "촉박"])
    )


def _waypoint_hint(text: str, destination: str | None = None) -> str | None:
    patterns = [
        r"(?:에서|부터)\s*([가-힣A-Za-z0-9\s]+?)(?:까지|으로|로|에)\s*(?:가서|간\s*뒤|갔다가|들러|들렀다가|경유)",
        r"([가-힣A-Za-z0-9\s]+?)(?:까지|으로|로|에)\s*(?:가서|간\s*뒤|갔다가|들러|들렀다가|경유)",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for value in reversed(matches):
            cleaned = _clean_hint(value)
            if cleaned and _normalize(cleaned) != _normalize(destination or ""):
                return cleaned
    return None


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
    cleaned = re.sub(r"\s*(에서|부터|으로|로|까지|에)$", "", cleaned).strip()
    return cleaned if len(cleaned) >= 2 else None


def _normalize(value: str) -> str:
    return value.lower().replace(" ", "")

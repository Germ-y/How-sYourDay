from api.schemas import PreviewInsight
from tools.extract_intent import extract_intent
from tools.extract_route_locations import extract_route_locations


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

    stop_points = _stop_insights(text)
    insights.extend(stop_points)

    if intent:
        task_point = None if stop_points else _task_insight(intent.tasks)
        if task_point:
            insights.append(task_point)

        emotion_point = _emotion_insight(intent.emotion.primary)
        if emotion_point:
            insights.append(emotion_point)

    if active_mood and len(insights) < 4:
        insights.append(
            PreviewInsight(
                label="컨디션",
                value=f"{active_mood} 기준으로 경로 비교",
                kind="mood",
            )
        )

    while len(insights) < 4:
        insights.append(_empty_insight(len(insights)))

    source = "llm" if route_hints and route_hints.source == "llm" else "rules"
    mood_candidates = intent.mood_candidates if intent else _default_mood_candidates()
    return insights[:4], source, mood_candidates[:4]


def _task_insight(tasks) -> PreviewInsight | None:
    if not tasks:
        return None

    primary = tasks[0]
    if primary.kind == "recovery":
        return PreviewInsight(label="경유", value="쉴 만한 장소 후보 확인", kind="stop")
    if primary.kind == "print":
        return PreviewInsight(label="할 일", value="인쇄 가능한 지점 반영", kind="task")
    if primary.kind == "clinic":
        return PreviewInsight(label="할 일", value="병원 방문 동선 반영", kind="task")
    return PreviewInsight(label="할 일", value=primary.label, kind="task")


def _stop_insights(text: str) -> list[PreviewInsight]:
    insights: list[PreviewInsight] = []
    area = _area_hint(text)

    if any(marker in text for marker in ["걷", "산책", "돌아다니", "주변", "근처", "선선"]):
        value = f"{area} 주변 산책" if area else "주변 산책 후보"
        insights.append(PreviewInsight(label="경유 후보", value=value, kind="stop"))

    if any(marker in text for marker in ["카페", "커피", "과제", "공부", "작업"]):
        value = f"{area} 카페 작업" if area else "카페 작업 후보"
        insights.append(PreviewInsight(label="경유 후보", value=value, kind="stop"))

    if any(marker in text for marker in ["쉬", "휴식", "조용"]):
        value = f"{area} 휴식 장소" if area else "쉴 만한 장소 후보"
        insights.append(PreviewInsight(label="경유 후보", value=value, kind="stop"))

    unique: list[PreviewInsight] = []
    seen: set[str] = set()
    for insight in insights:
        if insight.value in seen:
            continue
        seen.add(insight.value)
        unique.append(insight)
    return unique[:3]


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
        PreviewInsight(label="경유 후보", value="선호 장소 후보 확인", kind="stop"),
        PreviewInsight(label="상태", value="컨디션 기준으로 경로 비교", kind="mood"),
        PreviewInsight(label="취향", value="선호 지도 반영", kind="stop"),
    ]
    return defaults[index]


def _default_mood_candidates() -> list[str]:
    return ["피곤", "바쁨", "여유", "휴식"]


def _first_present(*values: str | None) -> str | None:
    for value in values:
        if value and value.strip():
            return value.strip()
    return None


def _has_time_hint(text: str) -> bool:
    return any(marker in text for marker in ["시", "분", "까지", "전", "deadline"])


def _area_hint(text: str) -> str | None:
    import re

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

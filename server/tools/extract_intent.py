import re
from dataclasses import dataclass

from api.schemas import Constraints, EmotionState, Task


@dataclass(frozen=True)
class ExtractedIntent:
    tasks: list[Task]
    constraints: Constraints
    emotion: EmotionState
    mood_candidates: list[str]


TASK_RULES = {
    "print": ("print", "Print document", "print shop"),
    "clinic": ("clinic", "Visit clinic", "clinic"),
    "hospital": ("clinic", "Visit clinic", "clinic"),
    "rest": ("recovery", "Take a short recovery break", "quiet cafe"),
    "recover": ("recovery", "Take a short recovery break", "quiet cafe"),
    "coffee": ("recovery", "Take a short recovery break", "quiet cafe"),
    "cafe": ("recovery", "Take a short recovery break", "quiet cafe"),
    "카페": ("recovery", "Take a short recovery break", "quiet cafe"),
    "커피": ("recovery", "Take a short recovery break", "quiet cafe"),
    "과제": ("recovery", "Find a comfortable place to work", "quiet cafe"),
    "작업": ("recovery", "Find a comfortable place to work", "quiet cafe"),
    "공부": ("recovery", "Find a comfortable place to study", "quiet cafe"),
    "조용": ("recovery", "Find a quiet place", "quiet cafe"),
    "쉬": ("recovery", "Take a short recovery break", "quiet cafe"),
    "다이소": ("errand", "다이소 들르기", "다이소"),
    "살거": ("errand", "살 것 사기", "다이소"),
    "살 것": ("errand", "살 것 사기", "다이소"),
    "사야": ("errand", "살 것 사기", "생활용품점"),
    "구매": ("errand", "살 것 사기", "생활용품점"),
    "장보기": ("errand", "장보기", "마트"),
}


def extract_intent(user_text: str) -> ExtractedIntent:
    fallback = _extract_intent_with_rules(user_text)

    from tools.llm_intent import extract_intent_with_llm

    llm_intent = extract_intent_with_llm(user_text)
    if llm_intent is None:
        return fallback

    if not llm_intent.tasks:
        return ExtractedIntent(
            tasks=fallback.tasks,
            constraints=llm_intent.constraints,
            emotion=llm_intent.emotion,
            mood_candidates=llm_intent.mood_candidates or fallback.mood_candidates,
        )

    return llm_intent


def _extract_intent_with_rules(user_text: str) -> ExtractedIntent:
    lowered = user_text.lower()
    tasks: list[Task] = []

    for keyword, (kind, label, poi_query) in TASK_RULES.items():
        if keyword in lowered and all(task.kind != kind for task in tasks):
            tasks.append(
                Task(
                    kind=kind,
                    label=label,
                    poi_query=poi_query,
                    priority=len(tasks) + 1,
                )
            )

    constraints = Constraints(
        deadline=_extract_deadline(lowered),
        destination="home" if "home" in lowered else None,
        max_walking_minutes=20 if any(marker in lowered for marker in ["tired", "피곤", "지쳐"]) else None,
        must_arrive_before_deadline=True,
    )

    return ExtractedIntent(
        tasks=tasks,
        constraints=constraints,
        emotion=_analyze_emotion(lowered),
        mood_candidates=_infer_mood_candidates(lowered),
    )


def _extract_deadline(text: str) -> str | None:
    if "5" in text or "five" in text:
        return "17:00"
    if "6" in text or "six" in text:
        return "18:00"
    return None


def _analyze_emotion(text: str) -> EmotionState:
    tired_markers = ["tired", "exhausted", "drained", "지쳐", "피곤"]
    anxious_markers = ["anxious", "nervous", "불안"]
    hurry_markers = ["hurry", "urgent", "rush", "late", "급해", "촉박"]

    if any(marker in text for marker in tired_markers):
        return EmotionState(
            primary="tired",
            walking_tolerance="low",
            crowd_tolerance="low",
            transfer_tolerance="medium",
            time_pressure_tolerance="medium",
            recovery_need="high",
        )

    if any(marker in text for marker in hurry_markers):
        return EmotionState(
            primary="hurried",
            walking_tolerance="medium",
            crowd_tolerance="medium",
            transfer_tolerance="medium",
            time_pressure_tolerance="high",
            recovery_need="low",
        )

    if any(marker in text for marker in anxious_markers):
        return EmotionState(
            primary="anxious",
            walking_tolerance="medium",
            crowd_tolerance="low",
            transfer_tolerance="low",
            time_pressure_tolerance="low",
            recovery_need="medium",
        )

    return EmotionState(
        primary="steady",
        walking_tolerance="medium",
        crowd_tolerance="medium",
        transfer_tolerance="medium",
        time_pressure_tolerance="medium",
        recovery_need="low",
    )


def _infer_mood_candidates(text: str) -> list[str]:
    rules = [
        ("바쁨", ["바쁨", "급", "빨리", "늦", "촉박", "약속", "보기로", "만나", "도착해야", "hurry", "urgent"]),
        ("급함", ["급", "빨리", "늦", "촉박", "hurry", "urgent"]),
        ("여유", ["여유", "천천", "둘러", "괜찮", "slow"]),
        ("산책", ["산책", "걸", "걷", "돌아다니", "선선", "walk"]),
        ("휴식", ["휴식", "쉬", "카페", "커피", "편한", "rest", "cafe", "coffee"]),
        ("회복", ["회복", "충전", "리셋", "쉬", "rest", "recover"]),
        ("집중", ["집중", "공부", "과제", "작업", "시험", "회의", "업무", "study", "work", "focus"]),
        ("몰입", ["몰입", "과제", "작업", "공부", "집중", "focus"]),
        ("피곤", ["피곤", "지침", "지쳐", "힘들", "무리", "tired", "exhausted"]),
        ("불안", ["불안", "긴장", "복잡", "사람", "혼잡", "무서", "anxious", "nervous"]),
        ("혼잡", ["혼잡", "사람", "붐비", "복잡", "crowd"]),
        ("조용", ["조용", "소음", "시끄", "quiet", "noise"]),
        ("쾌적", ["쾌적", "선선", "상쾌", "좋아", "pleasant"]),
        ("익숙", ["익숙", "아는", "편한 길", "familiar"]),
        ("편안", ["편안", "편한", "부담", "무리", "comfortable"]),
        ("안정", ["안정", "괜찮", "차분", "steady", "fine"]),
    ]
    scored: list[tuple[int, int, str]] = []
    for index, (label, keywords) in enumerate(rules):
        score = sum(1 for keyword in keywords if keyword in text)
        if label == "바쁨" and _has_time_pressure_hint(text):
            score += 2
        if score:
            scored.append((-score, index, label))

    labels = [label for _, _, label in sorted(scored)]
    for fallback in ["피곤", "바쁨", "여유", "휴식"]:
        if fallback not in labels:
            labels.append(fallback)
    return labels[:4]


def _has_time_pressure_hint(text: str) -> bool:
    return bool(
        re.search(r"\d+\s*(?:시|분)\s*(?:까지|전|안에)?", text)
        or re.search(r"(?:오전|오후)\s*\d+", text)
        or re.search(r"\d+\s*시간\s*안", text)
        or any(marker in text for marker in ["마감", "늦지", "촉박"])
    )

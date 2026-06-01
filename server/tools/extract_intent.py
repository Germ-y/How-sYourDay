from dataclasses import dataclass

from api.schemas import Constraints, EmotionState, Task


@dataclass(frozen=True)
class ExtractedIntent:
    tasks: list[Task]
    constraints: Constraints
    emotion: EmotionState


TASK_RULES = {
    "print": ("print", "Print document", "print shop"),
    "clinic": ("clinic", "Visit clinic", "clinic"),
    "hospital": ("clinic", "Visit clinic", "clinic"),
    "rest": ("recovery", "Take a short recovery break", "quiet cafe"),
    "recover": ("recovery", "Take a short recovery break", "quiet cafe"),
    "coffee": ("recovery", "Take a short recovery break", "quiet cafe"),
    "cafe": ("recovery", "Take a short recovery break", "quiet cafe"),
    "쉬": ("recovery", "Take a short recovery break", "quiet cafe"),
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

    if not tasks:
        tasks.append(
            Task(
                kind="recovery",
                label="Find a comfortable place to reset",
                poi_query="quiet cafe",
                priority=1,
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

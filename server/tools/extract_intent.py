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
    "coffee": ("recovery", "Take a short recovery break", "quiet cafe"),
    "cafe": ("recovery", "Take a short recovery break", "quiet cafe"),
}


def extract_intent(user_text: str) -> ExtractedIntent:
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

    if any(marker in text for marker in tired_markers):
        return EmotionState(
            primary="tired",
            walking_tolerance="low",
            crowd_tolerance="low",
            transfer_tolerance="medium",
            recovery_need="high",
        )

    if any(marker in text for marker in anxious_markers):
        return EmotionState(
            primary="anxious",
            walking_tolerance="medium",
            crowd_tolerance="low",
            transfer_tolerance="low",
            recovery_need="medium",
        )

    return EmotionState(
        primary="steady",
        walking_tolerance="medium",
        crowd_tolerance="medium",
        transfer_tolerance="medium",
        recovery_need="low",
    )


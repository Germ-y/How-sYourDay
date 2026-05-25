from api.schemas import EmotionScore, PlanResponse, RouteCandidate
from tools.extract_intent import ExtractedIntent


def compose_plan(
    intent: ExtractedIntent,
    routes: list[RouteCandidate],
    selected_route: RouteCandidate,
    score: EmotionScore,
) -> PlanResponse:
    task_labels = ", ".join(task.label.lower() for task in intent.tasks)
    summary = (
        f"A lower-stress plan for today: {task_labels}, then keep the route "
        "simple enough for your current energy."
    )

    return PlanResponse(
        summary=summary,
        emotion=intent.emotion,
        constraints=intent.constraints,
        tasks=intent.tasks,
        stops=selected_route.stops,
        routes=routes,
        score=score,
        tradeoffs=[
            "Chooses comfort over the absolute shortest travel time.",
            "Uses landmark and place-type heuristics until personal feedback exists.",
        ],
    )


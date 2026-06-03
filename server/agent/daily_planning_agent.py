from dataclasses import replace

from api.schemas import PlanRequest, PlanResponse
from memory.preferences import UserPreferenceWeights, load_preference_weights
from planner.compose_plan import compose_plan
from planner.evaluate_tradeoffs import evaluate_tradeoffs
from tools.emotion_score import score_route_for_emotion
from tools.emotion_waypoints import find_emotion_waypoints
from tools.extract_intent import extract_intent
from tools.manual_waypoints import normalize_manual_waypoints
from tools.route_path import build_route_candidates
from tools.search_poi import search_poi_candidates


class DailyPlanningAgent:
    """Coordinates deterministic tools before real LLM/map providers are added."""

    def run(
        self,
        request: PlanRequest,
        preference_weights: UserPreferenceWeights | None = None,
    ) -> PlanResponse:
        intent = extract_intent(request.user_text)
        manual_tasks = normalize_manual_waypoints(
            request.waypoint_hints,
            request.user_text,
            request.origin,
            request.destination,
        )
        tasks = _merge_tasks(intent.tasks, manual_tasks)
        intent = replace(intent, tasks=tasks)
        required_tasks = [task for task in tasks if task.required]
        optional_tasks = [task for task in tasks if not task.required]
        poi_candidates = search_poi_candidates(
            required_tasks,
            request.origin,
            request.destination,
            request.user_text,
        )
        optional_poi_candidates = search_poi_candidates(
            optional_tasks,
            request.origin,
            request.destination,
            request.user_text,
        )
        optional_stops = find_emotion_waypoints(
            request.user_text,
            intent.emotion,
            intent.constraints,
            request.origin,
            request.destination,
            poi_candidates,
        )
        optional_stops = _merge_optional_stops(optional_poi_candidates, optional_stops)
        routes = build_route_candidates(
            stops=poi_candidates,
            origin=request.origin,
            destination=request.destination,
            emotion=intent.emotion,
            optional_stops=optional_stops,
        )
        preference_weights = preference_weights or load_preference_weights()
        scores = [
            score_route_for_emotion(
                route,
                intent.emotion,
                intent.constraints,
                preference_weights,
            )
            for route in routes
        ]
        evaluation = evaluate_tradeoffs(
            routes=routes,
            emotion_scores=scores,
            constraints=intent.constraints,
            emotion=intent.emotion,
        )

        return compose_plan(
            intent=intent,
            routes=routes,
            evaluation=evaluation,
        )


def _merge_tasks(base_tasks, manual_tasks):
    merged = []
    seen = set()
    for task in [*base_tasks, *manual_tasks]:
        key = f"{task.kind}:{task.poi_query.replace(' ', '').lower()}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(
            task.model_copy(update={"priority": len(merged) + 1})
        )
    return merged


def _merge_optional_stops(*groups):
    merged = []
    seen = set()
    for group in groups:
        for stop in group:
            key = stop.provider_id or f"{stop.name}:{stop.lat:.6f}:{stop.lng:.6f}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                stop.model_copy(
                    update={"required": False if stop.required is None else stop.required}
                )
            )
    return merged

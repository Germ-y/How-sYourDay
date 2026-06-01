from api.schemas import PlanRequest, PlanResponse
from memory.preferences import load_preference_weights
from planner.compose_plan import compose_plan
from planner.evaluate_tradeoffs import evaluate_tradeoffs
from tools.emotion_score import score_route_for_emotion
from tools.emotion_waypoints import find_emotion_waypoints
from tools.extract_intent import extract_intent
from tools.route_path import build_route_candidates
from tools.search_poi import search_poi_candidates


class DailyPlanningAgent:
    """Coordinates deterministic tools before real LLM/map providers are added."""

    def run(self, request: PlanRequest) -> PlanResponse:
        intent = extract_intent(request.user_text)
        poi_candidates = search_poi_candidates(intent.tasks, request.origin)
        optional_stops = find_emotion_waypoints(
            request.user_text,
            intent.emotion,
            intent.constraints,
            request.origin,
            request.destination,
            poi_candidates,
        )
        routes = build_route_candidates(
            stops=poi_candidates,
            origin=request.origin,
            destination=request.destination,
            emotion=intent.emotion,
            optional_stops=optional_stops,
        )
        preference_weights = load_preference_weights()
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

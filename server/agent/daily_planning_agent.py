from api.schemas import PlanRequest, PlanResponse
from planner.compose_plan import compose_plan
from planner.evaluate_tradeoffs import evaluate_tradeoffs
from tools.emotion_score import score_route_for_emotion
from tools.extract_intent import extract_intent
from tools.route_path import build_route_candidates
from tools.search_poi import search_poi_candidates


class DailyPlanningAgent:
    """Coordinates deterministic tools before real LLM/map providers are added."""

    def run(self, request: PlanRequest) -> PlanResponse:
        intent = extract_intent(request.user_text)
        poi_candidates = search_poi_candidates(intent.tasks, request.origin)
        routes = build_route_candidates(poi_candidates)
        scores = [
            score_route_for_emotion(route, intent.emotion, intent.constraints)
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

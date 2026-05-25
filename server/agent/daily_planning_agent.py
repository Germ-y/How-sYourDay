from api.schemas import PlanRequest, PlanResponse
from planner.compose_plan import compose_plan
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
        best_route = routes[0]
        score = score_route_for_emotion(best_route, intent.emotion)

        return compose_plan(
            intent=intent,
            routes=routes,
            selected_route=best_route,
            score=score,
        )


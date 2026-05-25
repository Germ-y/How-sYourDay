from agent.daily_planning_agent import DailyPlanningAgent
from api.schemas import Constraints, EmotionState, Location, PlanRequest
from planner.evaluate_tradeoffs import evaluate_tradeoffs
from tools.emotion_score import score_route_for_emotion
from tools.landmark_emotion_prior import LANDMARK_PRIORS
from tools.route_path import build_route_candidates
from tools.search_poi import search_poi_candidates
from tools.extract_intent import extract_intent


def test_tired_user_gets_lower_stress_route() -> None:
    plan = _run("I need to print and visit a clinic before 5. I am tired.")

    assert plan.emotion.primary == "tired"
    assert plan.selected_route.id != "route-faster"
    assert plan.emotional_cost.route_id == plan.selected_route.id
    assert plan.map_overlays.selected_route_id == plan.selected_route.id
    assert plan.score.comfort_score + plan.score.stress_score == 100


def test_hurried_user_can_get_faster_route() -> None:
    plan = _run("I am in a hurry and need to get home by 5.")

    assert plan.emotion.primary == "hurried"
    assert plan.selected_route.id == "route-faster"
    assert any("time pressure" in summary for summary in plan.tradeoff_summaries)


def test_recovery_request_adds_recovery_poi_and_recommendation() -> None:
    plan = _run("I need to rest before going home.")

    assert any(stop.category == "recovery" for stop in plan.stops)
    assert any(item.kind == "recovery" for item in plan.recommendations)


def test_kakao_poi_is_normalized_when_provider_returns_result(monkeypatch) -> None:
    from tools import kakao_local

    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr(
        kakao_local,
        "_fetch_kakao_documents",
        lambda api_key, task, origin: [
            {
                "id": "123",
                "place_name": "혜화 인쇄소",
                "category_name": "서비스,산업 > 전문대행 > 인쇄",
                "x": "126.9945",
                "y": "37.5891",
                "distance": "110",
            }
        ],
    )

    candidates = search_poi_candidates(
        [
            extract_intent("I need to print my report.").tasks[0],
        ],
        Location(label="Current location", lat=37.5882, lng=126.9936),
    )

    assert candidates[0].source_confidence == "kakao"
    assert candidates[0].provider_id == "123"
    assert candidates[0].category == "print"
    assert candidates[0].distance_meters == 110


def test_kakao_poi_falls_back_to_mock_when_provider_has_no_result(monkeypatch) -> None:
    from tools import kakao_local

    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr(
        kakao_local,
        "_fetch_kakao_documents",
        lambda api_key, task, origin: [],
    )

    candidates = search_poi_candidates(
        [
            extract_intent("I need to print my report.").tasks[0],
        ],
        Location(label="Current location", lat=37.5882, lng=126.9936),
    )

    assert candidates[0].source_confidence == "mock"


def test_landmark_priors_only_use_allowed_tags() -> None:
    allowed_tags = {
        "calm",
        "recovery",
        "crowded",
        "familiar",
        "high_noise",
        "walkable",
        "stressful",
    }

    for prior in LANDMARK_PRIORS.values():
        assert set(prior.emotion_tags).issubset(allowed_tags)


def test_emotion_score_penalizes_high_crowd_for_tired_user() -> None:
    intent = extract_intent("I need to print and visit a clinic before 5. I am tired.")
    pois = search_poi_candidates(
        intent.tasks,
        Location(label="Current location", lat=37.5882, lng=126.9936),
    )
    routes = build_route_candidates(
        pois,
        Location(label="Current location", lat=37.5882, lng=126.9936),
    )
    high_crowd = next(route for route in routes if route.id == "route-faster")
    calm_route = next(route for route in routes if route.id == "route-recovery-friendly")

    high_score = score_route_for_emotion(high_crowd, intent.emotion, intent.constraints)
    calm_score = score_route_for_emotion(calm_route, intent.emotion, intent.constraints)

    assert high_score.crowd_cost > calm_score.crowd_cost
    assert calm_score.recovery_bonus > 0
    assert high_score.comfort_score + high_score.stress_score == 100


def test_deadline_fallback_selects_least_late_route() -> None:
    intent = extract_intent("I need to print and visit a clinic before 5. I am tired.")
    pois = search_poi_candidates(
        intent.tasks,
        Location(label="Current location", lat=37.5882, lng=126.9936),
    )
    routes = build_route_candidates(
        pois,
        Location(label="Current location", lat=37.5882, lng=126.9936),
    )
    constraints = Constraints(deadline="14:10", destination="home")
    emotion = EmotionState(
        primary="steady",
        walking_tolerance="medium",
        crowd_tolerance="medium",
        transfer_tolerance="medium",
        time_pressure_tolerance="medium",
        recovery_need="low",
    )
    scores = [score_route_for_emotion(route, emotion, constraints) for route in routes]

    evaluation = evaluate_tradeoffs(routes, scores, constraints, emotion)

    assert evaluation.fallback_used is True
    assert evaluation.selected_route.id == "route-faster"
    assert any("least-late" in summary for summary in evaluation.tradeoff_summaries)


def _run(user_text: str):
    agent = DailyPlanningAgent()
    return agent.run(
        PlanRequest(
            user_text=user_text,
            origin=Location(label="Current location", lat=37.5882, lng=126.9936),
        )
    )

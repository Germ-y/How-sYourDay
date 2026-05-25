from agent.daily_planning_agent import DailyPlanningAgent
from api.schemas import Coordinate, Constraints, EmotionState, Location, PlanRequest, PoiCandidate
from planner.evaluate_tradeoffs import evaluate_tradeoffs
from tools.emotion_score import score_route_for_emotion
from tools.landmark_emotion_prior import LANDMARK_PRIORS
from tools.route_path import build_route_candidates
from tools.search_poi import search_poi_candidates
from tools.extract_intent import extract_intent


def setup_module() -> None:
    import os

    os.environ["HYS_DISABLE_TMAP"] = "1"


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


def test_mock_routes_expose_reliability_metadata() -> None:
    plan = _run("I need to rest before going home.")

    assert all(route.provider == "mock" for route in plan.routes)
    assert all(route.route_mode == "mock" for route in plan.routes)
    assert all(route.estimated_duration_minutes for route in plan.routes)
    assert all(route.fallback_reason for route in plan.routes)


def test_real_tmap_route_excludes_mock_candidates(monkeypatch) -> None:
    from tools import route_path

    monkeypatch.setattr(
        route_path,
        "build_tmap_route_candidates",
        lambda stops, origin, destination: [
            route_path.RouteCandidate(
                id="route-tmap-walk",
                provider="tmap-pedestrian",
                route_mode="walk",
                stops=stops,
                walking_minutes=12,
                transfer_count=0,
                crowd_level="low",
                estimated_minutes=12,
                real_duration_minutes=12,
                estimated_duration_minutes=None,
                distance_meters=900,
                fare=0,
                fallback_reason=None,
                polyline=[
                    Coordinate(lat=origin.lat, lng=origin.lng),
                    Coordinate(lat=destination.lat, lng=destination.lng),
                ],
                segments=[],
            )
        ],
    )

    routes = route_path.build_route_candidates(
        [],
        Location(label="Current location", lat=37.5882, lng=126.9936),
        Location(label="Home", lat=37.5826, lng=127.0019),
    )

    assert [route.provider for route in routes] == ["tmap-pedestrian"]


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


def test_tmap_pedestrian_route_is_normalized(monkeypatch) -> None:
    from tools import tmap_route

    monkeypatch.delenv("HYS_DISABLE_TMAP", raising=False)
    monkeypatch.setattr(tmap_route, "_get_tmap_app_key", lambda: "test-key")
    monkeypatch.setattr(
        tmap_route,
        "_fetch_pedestrian_leg",
        lambda app_key, start, end: tmap_route.TmapLegResult(
            duration_minutes=12,
            walking_minutes=12,
            transfer_count=0,
            distance_meters=900,
            fare=0,
            polyline=[start, end],
            segments=[],
        ),
    )
    monkeypatch.setattr(tmap_route, "_fetch_transit_leg", lambda app_key, start, end: None)

    routes = tmap_route.build_tmap_route_candidates(
        [],
        Location(label="Current location", lat=37.5882, lng=126.9936),
        Location(label="Home", lat=37.5826, lng=127.0019),
    )

    assert routes[0].provider == "tmap-pedestrian"
    assert routes[0].route_mode == "walk"
    assert routes[0].real_duration_minutes == 12
    assert routes[0].distance_meters == 900


def test_tmap_pedestrian_request_uses_encoded_names(monkeypatch) -> None:
    from tools import tmap_route

    captured = {}

    def fake_post_json(url, app_key, body):
        captured["url"] = url
        captured["body"] = body
        return {
            "features": [
                {
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[126.9936, 37.5882], [127.0019, 37.5826]],
                    },
                    "properties": {"distance": 1000, "time": 600},
                }
            ]
        }

    monkeypatch.setattr(tmap_route, "_post_json", fake_post_json)

    leg = tmap_route._fetch_pedestrian_leg(
        "test-key",
        Location(label="Current location", lat=37.5882, lng=126.9936),
        Location(label="Home", lat=37.5826, lng=127.0019),
    )

    assert leg is not None
    assert "version=1" in captured["url"]
    assert captured["body"]["startName"].startswith("%")
    assert captured["body"]["endName"].startswith("%")


def test_tmap_transit_route_is_normalized(monkeypatch) -> None:
    from tools import tmap_route

    monkeypatch.delenv("HYS_DISABLE_TMAP", raising=False)
    monkeypatch.setattr(tmap_route, "_get_tmap_app_key", lambda: "test-key")
    monkeypatch.setattr(
        tmap_route,
        "_fetch_pedestrian_leg",
        lambda app_key, start, end: tmap_route.TmapLegResult(
            duration_minutes=12,
            walking_minutes=12,
            transfer_count=0,
            distance_meters=900,
            fare=0,
            polyline=[start, end],
            segments=[],
        ),
    )
    monkeypatch.setattr(
        tmap_route,
        "_fetch_transit_leg",
        lambda app_key, start, end: tmap_route.TmapLegResult(
            duration_minutes=18,
            walking_minutes=5,
            transfer_count=1,
            distance_meters=2300,
            fare=1450,
            polyline=[start, end],
            segments=[],
        ),
    )

    routes = tmap_route.build_tmap_route_candidates(
        [],
        Location(label="Current location", lat=37.5882, lng=126.9936),
        Location(label="Home", lat=37.5826, lng=127.0019),
    )

    transit = next(route for route in routes if route.id == "route-tmap-transit")
    assert transit.provider == "tmap-transit"
    assert transit.route_mode == "transit"
    assert transit.transfer_count == 1
    assert transit.fare == 1450


def test_tmap_failed_leg_becomes_mixed_route(monkeypatch) -> None:
    from tools import tmap_route

    monkeypatch.delenv("HYS_DISABLE_TMAP", raising=False)
    monkeypatch.setattr(tmap_route, "_get_tmap_app_key", lambda: "test-key")
    monkeypatch.setattr(tmap_route, "_fetch_pedestrian_leg", lambda app_key, start, end: None)
    monkeypatch.setattr(
        tmap_route,
        "_fetch_transit_leg",
        lambda app_key, start, end: tmap_route.TmapLegResult(
            duration_minutes=10,
            walking_minutes=3,
            transfer_count=0,
            distance_meters=1000,
            fare=1200,
            polyline=[start, end],
            segments=[],
        )
        if start.lat == 37.5882
        else None,
    )

    routes = tmap_route.build_tmap_route_candidates(
        [
            PoiCandidate(
                id="poi-test",
                name="Test stop",
                category="recovery",
                landmark_type="side_street",
                lat=37.586,
                lng=126.996,
            )
        ],
        Location(label="Current location", lat=37.5882, lng=126.9936),
        Location(label="Home", lat=37.5826, lng=127.0019),
    )

    transit = next(route for route in routes if route.id == "route-tmap-transit")
    assert transit.provider == "tmap-mixed"
    assert transit.fallback_reason


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


def test_real_route_duration_affects_hurried_time_pressure() -> None:
    intent = extract_intent("I am in a hurry and need to get home by 5.")
    route = build_route_candidates(
        [],
        Location(label="Current location", lat=37.5882, lng=126.9936),
        Location(label="Home", lat=37.5826, lng=127.0019),
    )[0].model_copy(
        update={
            "real_duration_minutes": 50,
            "estimated_duration_minutes": None,
            "estimated_minutes": 20,
            "provider": "tmap-transit",
            "route_mode": "transit",
            "fare": 2400,
        }
    )

    score = score_route_for_emotion(route, intent.emotion, intent.constraints)

    assert score.time_pressure_cost >= 37
    assert any("Real route duration" in reason for reason in score.reasons)


def test_feedback_memory_changes_scoring_weights(tmp_path, monkeypatch) -> None:
    from memory.preferences import (
        load_preference_weights,
        record_route_feedback,
    )

    monkeypatch.setenv("HYS_PREFERENCES_PATH", str(tmp_path / "preferences.json"))

    before = load_preference_weights()
    after = record_route_feedback(liked_route=False, reason="Too much walking")

    assert after.walking_sensitivity > before.walking_sensitivity
    assert load_preference_weights().walking_sensitivity == after.walking_sensitivity


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

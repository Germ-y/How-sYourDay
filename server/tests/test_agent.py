from agent.daily_planning_agent import DailyPlanningAgent
from api.schemas import (
    Coordinate,
    Constraints,
    EmotionState,
    Location,
    LocationCandidate,
    PlanRequest,
    PlacePreferenceCreate,
    PoiCandidate,
    RouteCandidate,
    RouteSegment,
    SavedPlaceCreate,
    Task,
)
from auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from db.models import Base
from planner.evaluate_tradeoffs import evaluate_tradeoffs
from repositories.place_preferences import list_place_preferences, upsert_place_preference
from repositories.saved_places import create_saved_place, list_saved_places
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tools.emotion_score import score_route_for_emotion
from tools.landmark_emotion_prior import LANDMARK_PRIORS
from tools.route_path import build_route_candidates
from tools.search_poi import search_poi_candidates
from tools.extract_intent import extract_intent
from tools.extract_route_locations import extract_route_locations
from tools.geocode import geocode_location, search_location_candidates
from tools.preview_insights import build_preview_insights
from tools.prompt_loader import kst_runtime_context
from tools import route_location_resolution


def setup_module() -> None:
    import os

    os.environ["HYS_DISABLE_TMAP"] = "1"
    os.environ["HYS_DISABLE_OSRM"] = "1"
    os.environ["HYS_DISABLE_LLM"] = "1"


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
    assert any("시간이 촉박" in summary for summary in plan.tradeoff_summaries)


def test_recovery_request_adds_recovery_poi_and_recommendation() -> None:
    plan = _run("I need to rest before going home.")

    assert any(stop.category == "recovery" for stop in plan.stops)
    assert any(item.kind == "recovery" for item in plan.recommendations)


def test_tired_user_gets_optional_recovery_route_candidate() -> None:
    plan = _run("I need to print before 5. I am tired.")

    assert any(
        any(stop.category == "recovery" for stop in route.stops)
        for route in plan.routes
    )


def test_hurried_user_does_not_get_optional_recovery_detour() -> None:
    plan = _run("I need to print before 5. I am in a hurry.")

    assert all(
        all(stop.category != "recovery" for stop in route.stops)
        for route in plan.routes
    )


def test_mock_routes_expose_reliability_metadata() -> None:
    plan = _run("I need to rest before going home.")

    assert all(route.provider == "mock" for route in plan.routes)
    assert all(route.route_mode == "mock" for route in plan.routes)
    assert all(route.estimated_duration_minutes for route in plan.routes)
    assert all(route.fallback_reason for route in plan.routes)


def test_real_tmap_route_excludes_mock_candidates(monkeypatch) -> None:
    from tools import route_path

    monkeypatch.setenv("HYS_DISABLE_OSRM", "1")
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


def test_osrm_route_is_normalized(monkeypatch) -> None:
    from tools import osrm_route

    monkeypatch.delenv("HYS_DISABLE_OSRM", raising=False)
    monkeypatch.setenv("OSRM_PROFILE", "driving")
    monkeypatch.setattr(osrm_route, "_get_osrm_base_url", lambda: "https://osrm.test")
    monkeypatch.setattr(
        osrm_route,
        "_fetch_osrm_route",
        lambda base_url, profile, waypoints: {
            "routes": [
                {
                    "duration": 900,
                    "distance": 3200,
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [waypoints[0].lng, waypoints[0].lat],
                            [waypoints[-1].lng, waypoints[-1].lat],
                        ],
                    },
                    "legs": [{"duration": 900}],
                }
            ]
        },
    )

    routes = osrm_route.build_osrm_route_candidates(
        [],
        Location(label="Current location", lat=37.5882, lng=126.9936),
        Location(label="Home", lat=37.5826, lng=127.0019),
    )

    assert routes[0].provider == "osrm"
    assert routes[0].route_mode == "driving"
    assert routes[0].real_duration_minutes == 15
    assert routes[0].distance_meters == 3200
    assert routes[0].polyline[0].lat == 37.5882


def test_route_path_uses_osrm_when_tmap_is_disabled(monkeypatch) -> None:
    from tools import route_path

    monkeypatch.setenv("HYS_DISABLE_TMAP", "1")
    monkeypatch.delenv("HYS_DISABLE_OSRM", raising=False)
    monkeypatch.setattr(route_path, "build_tmap_route_candidates", lambda stops, origin, destination: [])
    monkeypatch.setattr(
        route_path,
        "build_osrm_route_candidates",
        lambda stops, origin, destination: [
            route_path.RouteCandidate(
                id="route-osrm-driving",
                provider="osrm",
                route_mode="driving",
                stops=stops,
                walking_minutes=5,
                transfer_count=0,
                crowd_level="medium",
                estimated_minutes=12,
                real_duration_minutes=12,
                estimated_duration_minutes=None,
                distance_meters=2200,
                fare=0,
                fallback_reason="OSRM 개발용 경로로 계산했어요.",
                cost_estimate=0,
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

    assert [route.provider for route in routes] == ["osrm"]


def test_tmap_disable_flag_can_come_from_env_file(monkeypatch) -> None:
    from tools import tmap_route

    monkeypatch.delenv("HYS_DISABLE_TMAP", raising=False)
    monkeypatch.setattr(
        tmap_route,
        "_get_env_value",
        lambda name: "1" if name == "HYS_DISABLE_TMAP" else "test-key",
    )

    assert tmap_route._get_tmap_app_key() is None


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


def test_recovery_poi_uses_destination_area_when_text_places_task_there(
    monkeypatch,
) -> None:
    from tools import search_poi

    captured_anchors: list[str] = []

    def fake_kakao_candidates(tasks, origin):
        captured_anchors.append(origin.label)
        if origin.label == "수림식당 홍대점":
            return [
                PoiCandidate(
                    id="poi-cafe-hongdae",
                    provider_id="cafe-hongdae",
                    name="홍대 작업 카페",
                    category="recovery",
                    landmark_type="cafe",
                    emotion_tags=["calm", "recovery"],
                    lat=37.552,
                    lng=126.923,
                    source_confidence="kakao",
                ),
                PoiCandidate(
                    id="poi-cafe-hongdae-2",
                    provider_id="cafe-hongdae-2",
                    name="홍대 조용한 카페",
                    category="recovery",
                    landmark_type="cafe",
                    emotion_tags=["calm", "recovery"],
                    lat=37.553,
                    lng=126.924,
                    source_confidence="kakao",
                )
            ]
        return [
            PoiCandidate(
                id="poi-cafe-origin",
                provider_id="cafe-origin",
                name="오목교 카페",
                category="recovery",
                landmark_type="cafe",
                emotion_tags=["calm", "recovery"],
                lat=37.524,
                lng=126.877,
                source_confidence="kakao",
            )
        ]

    monkeypatch.setattr(search_poi, "search_kakao_poi_candidates", fake_kakao_candidates)

    candidates = search_poi.search_poi_candidates(
        [
            Task(
                kind="recovery",
                label="카페에서 과제",
                poi_query="카페",
                priority=1,
                required=True,
            )
        ],
        Location(label="오목교", lat=37.5243, lng=126.8780),
        Location(label="수림식당 홍대점", lat=37.5515, lng=126.9227),
        "오목교에서 홍대입구역으로 가서 과제를 카페에서 하다가 수림식당에서 약속",
    )

    assert captured_anchors[0] == "수림식당 홍대점"
    assert candidates[0].name == "홍대 작업 카페"
    assert [candidate.name for candidate in candidates] == [
        "홍대 작업 카페",
        "홍대 조용한 카페",
    ]


def test_recovery_candidates_become_alternative_route_variants() -> None:
    recovery_a = PoiCandidate(
        id="poi-cafe-a",
        provider_id="cafe-a",
        name="카페 A",
        category="recovery",
        landmark_type="cafe",
        emotion_tags=["calm", "recovery"],
        lat=37.552,
        lng=126.923,
    )
    recovery_b = PoiCandidate(
        id="poi-cafe-b",
        provider_id="cafe-b",
        name="카페 B",
        category="recovery",
        landmark_type="cafe",
        emotion_tags=["calm", "recovery"],
        lat=37.553,
        lng=126.924,
    )

    routes = build_route_candidates(
        [recovery_a, recovery_b],
        Location(label="오목교", lat=37.5243, lng=126.8780),
        Location(label="수림식당 홍대점", lat=37.5515, lng=126.9227),
    )

    assert routes
    assert all(len(route.stops) == 1 for route in routes)
    assert {route.stops[0].name for route in routes} == {"카페 A", "카페 B"}
    assert any(route.id.endswith("recovery-1") for route in routes)
    assert any(route.id.endswith("recovery-2") for route in routes)


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


def test_geocode_uses_known_location_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)

    result = geocode_location("집")

    assert result is not None
    location, source = result
    assert source == "known"
    assert location.label == "집"


def test_location_search_returns_known_candidates_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)

    candidates = search_location_candidates("집")

    assert candidates
    assert candidates[0].label == "집"
    assert candidates[0].source == "known"


def test_saved_places_are_scoped_by_user() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        create_saved_place(
            db,
            "user-a",
            SavedPlaceCreate(name="집", address="서울시 성북구", kind="home"),
        )
        create_saved_place(
            db,
            "user-b",
            SavedPlaceCreate(name="학교", address="성균관대학교", kind="school"),
        )

        user_a_places = list_saved_places(db, "user-a")
        user_b_places = list_saved_places(db, "user-b")

    assert [place.name for place in user_a_places] == ["집"]
    assert [place.name for place in user_b_places] == ["학교"]


def test_place_preferences_are_scoped_and_upserted_by_user() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        upsert_place_preference(
            db,
            "user-a",
            PlacePreferenceCreate(
                poi_provider_id="poi-1",
                name="Quiet Cafe",
                category="cafe",
                lat=37.5,
                lng=126.9,
                preference="like",
            ),
        )
        upsert_place_preference(
            db,
            "user-a",
            PlacePreferenceCreate(
                poi_provider_id="poi-1",
                name="Quiet Cafe",
                category="cafe",
                lat=37.5,
                lng=126.9,
                preference="dislike",
            ),
        )
        upsert_place_preference(
            db,
            "user-b",
            PlacePreferenceCreate(
                poi_provider_id="poi-1",
                name="Quiet Cafe",
                category="cafe",
                lat=37.5,
                lng=126.9,
                preference="like",
            ),
        )

        user_a_preferences = list_place_preferences(db, "user-a")
        user_b_preferences = list_place_preferences(db, "user-b")

    assert len(user_a_preferences) == 1
    assert user_a_preferences[0].preference == "dislike"
    assert len(user_b_preferences) == 1
    assert user_b_preferences[0].preference == "like"


def test_auth_security_hashes_password_and_decodes_token() -> None:
    hashed = hash_password("password123")

    assert hashed != "password123"
    assert verify_password("password123", hashed)
    assert not verify_password("wrong-password", hashed)
    assert decode_access_token(create_access_token("user-123")) == "user-123"


def test_kst_runtime_context_is_available_for_prompts() -> None:
    context = kst_runtime_context()

    assert "Asia/Seoul" in context
    assert "KST" in context
    assert "Current KST datetime:" in context


def test_preview_insights_reflect_route_and_time(monkeypatch) -> None:
    monkeypatch.setenv("HYS_DISABLE_LLM", "1")

    insights, source, mood_candidates = build_preview_insights(
        "성균관대학교에서 서울역까지 18시 전 도착",
        "성균관대학교",
        "서울역",
        "피곤",
    )

    assert source == "rules"
    assert insights[0].label == "이동"
    assert "성균관대학교" in insights[0].value
    assert any(insight.kind == "time" for insight in insights)
    assert "바쁨" in mood_candidates


def test_preview_insights_prefers_typed_route_over_saved_fields(monkeypatch) -> None:
    monkeypatch.setenv("HYS_DISABLE_LLM", "1")

    insights, _, _ = build_preview_insights(
        "성균관대학교 수원에서 서울역까지 2시간 안에 도착해야해",
        "학교",
        "집",
        "바쁨",
    )

    assert insights[0].kind == "route"
    assert "성균관대학교 수원" in insights[0].value
    assert "서울역" in insights[0].value
    assert "학교 → 집" not in insights[0].value


def test_preview_insights_extracts_multiple_stop_candidates(monkeypatch) -> None:
    monkeypatch.setenv("HYS_DISABLE_LLM", "1")

    insights, _, mood_candidates = build_preview_insights(
        "오목교역에서 출발해서 홍대까지 갈거야. 날씨 선선해서 홍대 주변 좀 걷고 카페에서 과제 좀 하다가 숯림 식당이라는 식당에서 3시에 친구 보기로 했어",
        None,
        None,
        "여유",
    )

    stop_values = [insight.value for insight in insights if insight.kind == "stop"]

    assert any("홍대 주변 산책" in value for value in stop_values)
    assert any("홍대 근처" in value for value in stop_values)
    assert not any(insight.label == "조건" for insight in insights)
    assert mood_candidates[:3] == ["바쁨", "산책", "휴식"]


def test_preview_insights_uses_final_appointment_and_waypoints(monkeypatch) -> None:
    monkeypatch.setenv("HYS_DISABLE_LLM", "1")

    insights, _, _ = build_preview_insights(
        "오목교에서 홍대입구역으로 가서 과제를 좀 카페에서 하다가 5시에 수림식당에서 약속있어 거기 가야해",
        None,
        None,
        "집중",
    )

    values = [insight.value for insight in insights]

    assert values[0] == "오목교 → 수림식당"
    assert any("17:00" in value for value in values)
    assert any("홍대입구역 주변" in value for value in values)
    assert any("홍대입구역 근처" in value for value in values)
    assert any(insight.label == "작업할 카페" for insight in insights)


def test_route_location_extraction_handles_korean_from_to(monkeypatch) -> None:
    monkeypatch.setenv("HYS_DISABLE_LLM", "1")

    hints = extract_route_locations("성균관대학교에서 서울역까지 18시 전 도착. 조용한 카페 경유 가능.")

    assert hints.origin_text == "성균관대학교"
    assert hints.destination_text == "서울역"
    assert hints.source == "rules"


def test_route_location_extraction_handles_casual_go_phrase(monkeypatch) -> None:
    monkeypatch.setenv("HYS_DISABLE_LLM", "1")

    hints = extract_route_locations(
        "오목교역에서 홍대입구역 가고 싶어 홍대입구역 가서 조금 걸을까 해"
    )

    assert hints.origin_text == "오목교역"
    assert hints.destination_text == "홍대입구역"


def test_route_location_extraction_handles_destination_before_origin(monkeypatch) -> None:
    monkeypatch.setenv("HYS_DISABLE_LLM", "1")

    hints = extract_route_locations(
        "나 홍대까지 가고 싶어 오목교역에서 날씨 선선해서 홍대 주변 좀 걸을까 해 가서 커피 한잔하게"
    )

    assert hints.origin_text == "오목교역"
    assert hints.destination_text == "홍대"


def test_route_location_extraction_prefers_specific_commitment_destination(monkeypatch) -> None:
    monkeypatch.setenv("HYS_DISABLE_LLM", "1")

    hints = extract_route_locations(
        "오목교역에서 출발해서 홍대까지 갈거야 홍대 가서 카페에서 과제 좀 하다가 숯림 식당이라는 식당에서 3시에 친구 보기로 했어"
    )

    assert hints.origin_text == "오목교역"
    assert hints.destination_text == "숯림 식당"


def test_route_location_extraction_allows_missing_origin(monkeypatch) -> None:
    monkeypatch.setenv("HYS_DISABLE_LLM", "1")

    hints = extract_route_locations("집에 가기 전에 조용한 카페에 들르고 싶다")

    assert hints.origin_text is None
    assert hints.destination_text == "집"


def test_route_location_resolution_selects_real_search_candidates(monkeypatch) -> None:
    monkeypatch.setenv("HYS_DISABLE_LLM", "1")

    def fake_search(query: str, size: int = 5) -> list[LocationCandidate]:
        if query == "성균관대학교 수원":
            return [
                LocationCandidate(
                    label="성균관대학교 자연과학캠퍼스",
                    address="경기 수원시 장안구 서부로 2066",
                    lat=37.295039,
                    lng=126.977422,
                    source="kakao-keyword",
                    category="학교",
                ),
                LocationCandidate(
                    label="디딤웍스 수원성균관대점",
                    address="경기 수원시 장안구 화산로213번길 15",
                    lat=37.298881,
                    lng=126.972745,
                    source="kakao-keyword",
                    category="공유오피스",
                ),
            ]
        if query == "서울역":
            return [
                LocationCandidate(
                    label="서울역",
                    address="서울 중구 한강대로 405",
                    lat=37.554069,
                    lng=126.970703,
                    source="kakao-keyword",
                    category="기차역",
                )
            ]
        return []

    monkeypatch.setattr(
        route_location_resolution, "search_location_candidates", fake_search
    )

    result = route_location_resolution.resolve_route_locations(
        "성균관대학교 수원에서 서울역까지 2시간 안에 도착해야해"
    )

    assert result.origin_text == "성균관대학교 수원"
    assert result.origin is not None
    assert result.origin.label == "성균관대학교 자연과학캠퍼스"
    assert result.destination is not None
    assert result.destination.label == "서울역"
    assert result.selection_source == "score"


def test_route_location_resolution_retrieves_specific_final_place(monkeypatch) -> None:
    monkeypatch.setenv("HYS_DISABLE_LLM", "1")

    def fake_search(query: str, size: int = 5) -> list[LocationCandidate]:
        if query == "오목교역":
            return [
                LocationCandidate(
                    label="오목교역 5호선",
                    address="서울 양천구 오목로 지하 342",
                    lat=37.524496,
                    lng=126.875181,
                    source="kakao-keyword",
                    category="지하철역",
                )
            ]
        if query == "숯림 식당":
            return [
                LocationCandidate(
                    label="숯림",
                    address="서울 마포구 와우산로29길 48",
                    lat=37.555302,
                    lng=126.924891,
                    source="kakao-keyword",
                    category="음식점 > 한식",
                )
            ]
        if query == "홍대":
            return [
                LocationCandidate(
                    label="홍대입구역 2호선",
                    address="서울 마포구 양화로 지하 160",
                    lat=37.557192,
                    lng=126.925381,
                    source="kakao-keyword",
                    category="지하철역",
                )
            ]
        return []

    monkeypatch.setattr(
        route_location_resolution, "search_location_candidates", fake_search
    )

    result = route_location_resolution.resolve_route_locations(
        "오목교역에서 출발해서 홍대까지 갈거야 홍대 가서 카페에서 과제 좀 하다가 숯림 식당이라는 식당에서 3시에 친구 보기로 했어"
    )

    assert result.origin is not None
    assert result.origin.label == "오목교역 5호선"
    assert result.destination_text == "숯림 식당"
    assert result.destination is not None
    assert result.destination.label == "숯림"


def test_route_location_resolution_searches_final_place_with_area_context(
    monkeypatch,
) -> None:
    monkeypatch.setenv("HYS_DISABLE_LLM", "1")
    captured_queries: list[str] = []

    def fake_search(query: str, size: int = 5) -> list[LocationCandidate]:
        captured_queries.append(query)
        if query == "오목교":
            return [
                LocationCandidate(
                    label="오목교역 5호선",
                    address="서울 양천구 오목로 지하 342",
                    lat=37.524496,
                    lng=126.875181,
                    source="kakao-keyword",
                    category="지하철역",
                )
            ]
        if query == "홍대 수림식당":
            return [
                LocationCandidate(
                    label="수림식당 홍대점",
                    address="서울 마포구 와우산로29길 48",
                    lat=37.555302,
                    lng=126.924891,
                    source="kakao-keyword",
                    category="음식점 > 한식",
                )
            ]
        if query == "수림식당":
            return [
                LocationCandidate(
                    label="수림식당",
                    address="울산 남구 삼산로",
                    lat=35.538377,
                    lng=129.338492,
                    source="kakao-keyword",
                    category="음식점 > 한식",
                )
            ]
        if query == "홍대입구역":
            return [
                LocationCandidate(
                    label="홍대입구역 2호선",
                    address="서울 마포구 양화로 지하 160",
                    lat=37.557192,
                    lng=126.925381,
                    source="kakao-keyword",
                    category="지하철역",
                )
            ]
        return []

    monkeypatch.setattr(
        route_location_resolution, "search_location_candidates", fake_search
    )

    result = route_location_resolution.resolve_route_locations(
        "오목교에서 홍대입구역으로 가서 과제를 카페에서 하다가 5시에 수림식당에서 약속있어 거기 가야해"
    )

    assert "홍대 수림식당" in captured_queries
    assert result.destination is not None
    assert result.destination.label == "수림식당 홍대점"


def test_route_location_resolution_falls_back_to_broad_area_when_specific_missing(
    monkeypatch,
) -> None:
    monkeypatch.setenv("HYS_DISABLE_LLM", "1")

    def fake_search(query: str, size: int = 5) -> list[LocationCandidate]:
        if query == "오목교역":
            return [
                LocationCandidate(
                    label="오목교역 5호선",
                    address="서울 양천구 오목로 지하 342",
                    lat=37.524496,
                    lng=126.875181,
                    source="kakao-keyword",
                    category="지하철역",
                )
            ]
        if query == "홍대":
            return [
                LocationCandidate(
                    label="홍대입구역 2호선",
                    address="서울 마포구 양화로 지하 160",
                    lat=37.557192,
                    lng=126.925381,
                    source="kakao-keyword",
                    category="지하철역",
                )
            ]
        return []

    monkeypatch.setattr(
        route_location_resolution, "search_location_candidates", fake_search
    )

    result = route_location_resolution.resolve_route_locations(
        "오목교역에서 출발해서 홍대까지 갈거야 홍대 가서 카페에서 과제 좀 하다가 숯림 식당이라는 식당에서 3시에 친구 보기로 했어"
    )

    assert result.origin is not None
    assert result.origin.label == "오목교역 5호선"
    assert result.destination is not None
    assert result.destination.label == "홍대입구역 2호선"


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


def test_tmap_candidate_is_skipped_when_all_legs_are_estimated(monkeypatch) -> None:
    from tools import tmap_route

    monkeypatch.delenv("HYS_DISABLE_TMAP", raising=False)
    monkeypatch.setattr(tmap_route, "_get_tmap_app_key", lambda: "test-key")
    monkeypatch.setattr(tmap_route, "_fetch_pedestrian_leg", lambda app_key, start, end: None)
    monkeypatch.setattr(tmap_route, "_fetch_transit_leg", lambda app_key, start, end: None)

    routes = tmap_route.build_tmap_route_candidates(
        [],
        Location(label="Current location", lat=37.5882, lng=126.9936),
        Location(label="Home", lat=37.5826, lng=127.0019),
    )

    assert routes == []


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


def test_tmap_score_uses_stop_landmark_priors() -> None:
    emotion = EmotionState(
        primary="tired",
        walking_tolerance="low",
        crowd_tolerance="low",
        transfer_tolerance="medium",
        time_pressure_tolerance="medium",
        recovery_need="high",
    )
    base_route = RouteCandidate(
        id="route-tmap-base",
        provider="tmap-pedestrian",
        route_mode="walk",
        stops=[],
        walking_minutes=12,
        transfer_count=0,
        crowd_level="low",
        estimated_minutes=20,
        real_duration_minutes=20,
        estimated_duration_minutes=None,
        distance_meters=900,
        fare=0,
        polyline=[],
        segments=[
            RouteSegment(
                mode="walk",
                minutes=12,
                landmark_type="side_street",
                emotion_tags=["walkable"],
            )
        ],
    )
    cafe_route = base_route.model_copy(
        update={
            "id": "route-tmap-cafe",
            "stops": [
                PoiCandidate(
                    id="poi-cafe-test",
                    name="Quiet Table Cafe",
                    category="recovery",
                    landmark_type="cafe",
                    emotion_tags=["calm", "recovery"],
                    lat=37.5876,
                    lng=126.9926,
                )
            ],
        }
    )
    school_route = base_route.model_copy(
        update={
            "id": "route-tmap-school",
            "stops": [
                PoiCandidate(
                    id="poi-school-test",
                    name="Busy School Gate",
                    category="school",
                    landmark_type="school",
                    emotion_tags=["crowded", "stressful"],
                    lat=37.5876,
                    lng=126.9926,
                )
            ],
        }
    )

    cafe_score = score_route_for_emotion(cafe_route, emotion)
    school_score = score_route_for_emotion(school_route, emotion)

    assert cafe_score.total_emotional_cost < school_score.total_emotional_cost
    assert cafe_score.recovery_bonus > school_score.recovery_bonus
    assert school_score.crowd_cost > cafe_score.crowd_cost


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
    assert any("가장 덜 늦는" in summary for summary in evaluation.tradeoff_summaries)


def _run(user_text: str):
    agent = DailyPlanningAgent()
    return agent.run(
        PlanRequest(
            user_text=user_text,
            origin=Location(label="Current location", lat=37.5882, lng=126.9936),
        )
    )

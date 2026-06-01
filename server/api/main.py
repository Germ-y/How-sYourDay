from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agent.daily_planning_agent import DailyPlanningAgent
from api.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    GeocodeRequest,
    GeocodeResponse,
    LocationSearchRequest,
    LocationSearchResponse,
    PlanRequest,
    PlanResponse,
    PreferencePointsRequest,
    PreferencePointsResponse,
    RouteExtractionRequest,
    RouteExtractionResponse,
)
from memory.preferences import record_route_feedback
from tools.extract_route_locations import extract_route_locations
from tools.geocode import geocode_location, search_location_candidates
from tools.preference_points import search_preference_points

app = FastAPI(title="How's Your Day API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4000",
        "http://127.0.0.1:4000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = DailyPlanningAgent()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/plan", response_model=PlanResponse)
def plan_day(request: PlanRequest) -> PlanResponse:
    return agent.run(request)


@app.post("/geocode", response_model=GeocodeResponse)
def geocode(request: GeocodeRequest) -> GeocodeResponse:
    result = geocode_location(request.query)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="주소나 장소명을 찾지 못했어요. 더 정확한 주소로 다시 입력해주세요.",
        )

    location, source = result
    return GeocodeResponse(location=location, source=source)


@app.post("/search-locations", response_model=LocationSearchResponse)
def search_locations(request: LocationSearchRequest) -> LocationSearchResponse:
    return LocationSearchResponse(
        candidates=search_location_candidates(request.query, size=request.size)
    )


@app.post("/extract-route", response_model=RouteExtractionResponse)
def extract_route(request: RouteExtractionRequest) -> RouteExtractionResponse:
    hints = extract_route_locations(request.user_text)
    return RouteExtractionResponse(
        origin_text=hints.origin_text,
        destination_text=hints.destination_text,
        source=hints.source,
    )


@app.post("/preference-points", response_model=PreferencePointsResponse)
def preference_points(request: PreferencePointsRequest) -> PreferencePointsResponse:
    points = search_preference_points(
        request.origin,
        radius_meters=request.radius_meters,
    )
    return PreferencePointsResponse(
        points=points,
        source="kakao" if points else "empty",
    )


@app.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    weights = record_route_feedback(
        liked_route=request.liked,
        reason=request.reason,
    )
    return FeedbackResponse(
        status="ok",
        walking_sensitivity=weights.walking_sensitivity,
        crowd_sensitivity=weights.crowd_sensitivity,
        transfer_sensitivity=weights.transfer_sensitivity,
        recovery_affinity=weights.recovery_affinity,
    )

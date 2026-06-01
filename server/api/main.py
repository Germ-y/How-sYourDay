from fastapi import Depends
from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

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
    PreviewInsightsRequest,
    PreviewInsightsResponse,
    RouteExtractionRequest,
    RouteExtractionResponse,
    RouteLocationResolutionResponse,
    SavedPlaceCreate,
    SavedPlaceResponse,
    SavedPlacesResponse,
)
from auth.router import router as auth_router
from auth.security import decode_access_token
from db.session import get_db, init_db
from memory.preferences import record_route_feedback
from repositories.saved_places import create_saved_place, delete_saved_place, list_saved_places
from tools.extract_route_locations import extract_route_locations
from tools.geocode import geocode_location, search_location_candidates
from tools.preference_points import search_preference_points
from tools.preview_insights import build_preview_insights
from tools.route_location_resolution import resolve_route_locations

app = FastAPI(title="How's Your Day API")
app.include_router(auth_router)

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
_db_initialized = False


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def current_user_id(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        token_user_id = decode_access_token(authorization.split(" ", 1)[1])
        if token_user_id:
            return token_user_id
    return x_user_id or "demo-user"


def database(db: Session = Depends(get_db)) -> Session:
    global _db_initialized
    try:
        if not _db_initialized:
            init_db()
            _db_initialized = True
        return db
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="DB 연결이 필요합니다. Postgres 실행 후 DATABASE_URL을 확인해주세요.",
        ) from exc


def saved_place_response(place) -> SavedPlaceResponse:
    return SavedPlaceResponse(
        id=place.id,
        name=place.name,
        address=place.address,
        kind=place.kind,
        lat=place.lat,
        lng=place.lng,
        created_at=place.created_at.isoformat(),
        updated_at=place.updated_at.isoformat(),
    )


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


@app.post("/resolve-route-locations", response_model=RouteLocationResolutionResponse)
def resolve_route(request: RouteExtractionRequest) -> RouteLocationResolutionResponse:
    result = resolve_route_locations(request.user_text)
    return RouteLocationResolutionResponse(
        origin_text=result.origin_text,
        destination_text=result.destination_text,
        origin=result.origin,
        destination=result.destination,
        origin_candidates=result.origin_candidates,
        destination_candidates=result.destination_candidates,
        source=result.source,
        selection_source=result.selection_source,
    )


@app.post("/preview-insights", response_model=PreviewInsightsResponse)
def preview_insights(request: PreviewInsightsRequest) -> PreviewInsightsResponse:
    insights, source, mood_candidates = build_preview_insights(
        request.user_text,
        request.origin_text,
        request.destination_text,
        request.active_mood,
    )
    return PreviewInsightsResponse(
        insights=insights,
        source=source,
        mood_candidates=mood_candidates,
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


@app.get("/me/saved-places", response_model=SavedPlacesResponse)
def get_my_saved_places(
    user_id: str = Depends(current_user_id),
    db: Session = Depends(database),
) -> SavedPlacesResponse:
    places = list_saved_places(db, user_id)
    return SavedPlacesResponse(places=[saved_place_response(place) for place in places])


@app.post("/me/saved-places", response_model=SavedPlaceResponse)
def add_my_saved_place(
    request: SavedPlaceCreate,
    user_id: str = Depends(current_user_id),
    db: Session = Depends(database),
) -> SavedPlaceResponse:
    place = create_saved_place(db, user_id, request)
    return saved_place_response(place)


@app.delete("/me/saved-places/{place_id}", status_code=204)
def remove_my_saved_place(
    place_id: str,
    user_id: str = Depends(current_user_id),
    db: Session = Depends(database),
) -> None:
    deleted = delete_saved_place(db, user_id, place_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="저장 장소를 찾지 못했어요.")

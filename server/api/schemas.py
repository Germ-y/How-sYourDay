from pydantic import BaseModel, Field


class Location(BaseModel):
    label: str
    lat: float
    lng: float


class PlanRequest(BaseModel):
    user_text: str = Field(min_length=1)
    origin: Location


class Task(BaseModel):
    kind: str
    label: str
    poi_query: str
    priority: int


class Constraints(BaseModel):
    deadline: str | None = None
    destination: str | None = None


class EmotionState(BaseModel):
    primary: str
    walking_tolerance: str
    crowd_tolerance: str
    transfer_tolerance: str
    recovery_need: str


class PoiCandidate(BaseModel):
    id: str
    name: str
    category: str
    landmark_type: str
    lat: float
    lng: float


class RouteCandidate(BaseModel):
    id: str
    stops: list[PoiCandidate]
    walking_minutes: int
    transfer_count: int
    crowd_level: str
    estimated_minutes: int


class EmotionScore(BaseModel):
    comfort_score: int
    stress_score: int
    reasons: list[str]


class PlanResponse(BaseModel):
    summary: str
    emotion: EmotionState
    constraints: Constraints
    tasks: list[Task]
    stops: list[PoiCandidate]
    routes: list[RouteCandidate]
    score: EmotionScore
    tradeoffs: list[str]


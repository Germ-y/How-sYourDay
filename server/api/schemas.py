from pydantic import BaseModel, Field


class Coordinate(BaseModel):
    lat: float
    lng: float


class Location(BaseModel):
    label: str
    lat: float
    lng: float


class PlanRequest(BaseModel):
    user_text: str = Field(min_length=1)
    origin: Location
    destination: Location | None = None


class Task(BaseModel):
    kind: str
    label: str
    poi_query: str
    priority: int
    required: bool = True


class Constraints(BaseModel):
    deadline: str | None = None
    destination: str | None = None
    max_walking_minutes: int | None = None
    must_arrive_before_deadline: bool = True


class EmotionState(BaseModel):
    primary: str
    walking_tolerance: str
    crowd_tolerance: str
    transfer_tolerance: str
    time_pressure_tolerance: str = "medium"
    recovery_need: str


class LandmarkEmotionPrior(BaseModel):
    landmark_type: str
    emotion_tags: list[str]
    fatigue_modifier: int
    crowd_modifier: int
    noise_modifier: int
    recovery_bonus: int
    reason: str


class PoiCandidate(BaseModel):
    id: str
    provider_id: str | None = None
    name: str
    category: str
    landmark_type: str
    emotion_tags: list[str] = Field(default_factory=list)
    lat: float
    lng: float
    distance_meters: int | None = None
    source_confidence: str = "mock"


class RouteSegment(BaseModel):
    mode: str
    minutes: int
    landmark_type: str
    emotion_tags: list[str] = Field(default_factory=list)


class RouteCandidate(BaseModel):
    id: str
    provider: str = "mock"
    route_mode: str = "mock"
    stops: list[PoiCandidate]
    walking_minutes: int
    transfer_count: int
    crowd_level: str
    estimated_minutes: int
    real_duration_minutes: int | None = None
    estimated_duration_minutes: int | None = None
    distance_meters: int | None = None
    fare: int | None = None
    fallback_reason: str | None = None
    cost_estimate: int | None = None
    polyline: list[Coordinate] = Field(default_factory=list)
    segments: list[RouteSegment] = Field(default_factory=list)


class EmotionCost(BaseModel):
    route_id: str
    fatigue_cost: int
    walking_cost: int
    crowd_cost: int
    transfer_cost: int
    time_pressure_cost: int
    familiarity_bonus: int
    recovery_bonus: int
    total_emotional_cost: int
    comfort_score: int
    stress_score: int
    reasons: list[str]


class EmotionScore(EmotionCost):
    pass


class TradeoffCostDelta(BaseModel):
    estimated_minutes: int
    emotional_cost: int


class Tradeoff(BaseModel):
    chosen_option: str
    rejected_option: str
    reason: str
    user_visible_label: str
    cost_delta: TradeoffCostDelta


class TimelineItem(BaseModel):
    time: str
    label: str
    type: str


class OrderedStop(BaseModel):
    stop_id: str
    task_kind: str
    arrival_time: str
    departure_time: str
    why_here: str


class Recommendation(BaseModel):
    kind: str
    label: str


class MapBounds(BaseModel):
    south_west: Coordinate
    north_east: Coordinate


class MapMarker(BaseModel):
    id: str
    type: str
    lat: float
    lng: float
    label: str
    badge: str


class MapPolyline(BaseModel):
    id: str
    route_id: str
    selected: bool
    points: list[Coordinate]
    emotion_level: str


class EmotionZone(BaseModel):
    id: str
    type: str
    emotion_tags: list[str]
    center: Coordinate
    radius_meters: int


class TradeoffBadge(BaseModel):
    route_id: str
    label: str
    description: str


class MapViewModel(BaseModel):
    center: Coordinate
    fit_bounds: MapBounds
    selected_route_id: str
    markers: list[MapMarker] = Field(default_factory=list)
    polylines: list[MapPolyline] = Field(default_factory=list)
    emotion_zones: list[EmotionZone] = Field(default_factory=list)
    tradeoff_badges: list[TradeoffBadge] = Field(default_factory=list)


class PlanResponse(BaseModel):
    summary: str
    emotion: EmotionState
    constraints: Constraints
    tasks: list[Task]
    stops: list[PoiCandidate]
    routes: list[RouteCandidate]
    score: EmotionScore
    tradeoffs: list[Tradeoff]
    tradeoff_summaries: list[str] = Field(default_factory=list)
    ordered_stops: list[OrderedStop]
    estimated_timeline: list[TimelineItem]
    selected_route: RouteCandidate
    emotional_cost: EmotionCost
    recommendations: list[Recommendation]
    map_overlays: MapViewModel
    explanation: str

export type Coordinate = {
  lat: number;
  lng: number;
};

export type Location = Coordinate & {
  label: string;
};

export type EmotionState = {
  primary: string;
  walking_tolerance: string;
  crowd_tolerance: string;
  transfer_tolerance: string;
  time_pressure_tolerance: string;
  recovery_need: string;
};

export type Constraints = {
  deadline: string | null;
  destination: string | null;
  max_walking_minutes: number | null;
  must_arrive_before_deadline: boolean;
};

export type Task = {
  kind: string;
  label: string;
  poi_query: string;
  priority: number;
  required: boolean;
};

export type PoiCandidate = {
  id: string;
  provider_id: string | null;
  name: string;
  category: string;
  landmark_type: string;
  emotion_tags: string[];
  lat: number;
  lng: number;
  distance_meters: number | null;
  source_confidence: string;
};

export type RouteSegment = {
  mode: string;
  minutes: number;
  landmark_type: string;
  emotion_tags: string[];
};

export type RouteCandidate = {
  id: string;
  provider: string;
  stops: PoiCandidate[];
  walking_minutes: number;
  transfer_count: number;
  crowd_level: string;
  estimated_minutes: number;
  cost_estimate: number | null;
  polyline: Coordinate[];
  segments: RouteSegment[];
};

export type EmotionCost = {
  route_id: string;
  fatigue_cost: number;
  walking_cost: number;
  crowd_cost: number;
  transfer_cost: number;
  time_pressure_cost: number;
  familiarity_bonus: number;
  recovery_bonus: number;
  total_emotional_cost: number;
  comfort_score: number;
  stress_score: number;
  reasons: string[];
};

export type Tradeoff = {
  chosen_option: string;
  rejected_option: string;
  reason: string;
  user_visible_label: string;
  cost_delta: {
    estimated_minutes: number;
    emotional_cost: number;
  };
};

export type TimelineItem = {
  time: string;
  label: string;
  type: string;
};

export type OrderedStop = {
  stop_id: string;
  task_kind: string;
  arrival_time: string;
  departure_time: string;
  why_here: string;
};

export type Recommendation = {
  kind: string;
  label: string;
};

export type MapViewModel = {
  center: Coordinate;
  fit_bounds: {
    south_west: Coordinate;
    north_east: Coordinate;
  };
  selected_route_id: string;
  markers: Array<{
    id: string;
    type: string;
    lat: number;
    lng: number;
    label: string;
    badge: string;
  }>;
  polylines: Array<{
    id: string;
    route_id: string;
    selected: boolean;
    points: Coordinate[];
    emotion_level: string;
  }>;
  emotion_zones: Array<{
    id: string;
    type: string;
    emotion_tags: string[];
    center: Coordinate;
    radius_meters: number;
  }>;
  tradeoff_badges: Array<{
    route_id: string;
    label: string;
    description: string;
  }>;
};

export type DailyPlan = {
  summary: string;
  emotion: EmotionState;
  constraints: Constraints;
  tasks: Task[];
  stops: PoiCandidate[];
  routes: RouteCandidate[];
  score: EmotionCost;
  tradeoffs: Tradeoff[];
  tradeoff_summaries: string[];
  ordered_stops: OrderedStop[];
  estimated_timeline: TimelineItem[];
  selected_route: RouteCandidate;
  emotional_cost: EmotionCost;
  recommendations: Recommendation[];
  map_overlays: MapViewModel;
  explanation: string;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8010";

export async function requestDailyPlan(
  userText: string,
  origin: Location,
  destination: Location
): Promise<DailyPlan> {
  const response = await fetch(`${API_BASE_URL}/plan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      user_text: userText,
      origin,
      destination
    })
  });

  if (!response.ok) {
    throw new Error(`API request failed with ${response.status}`);
  }

  return response.json();
}

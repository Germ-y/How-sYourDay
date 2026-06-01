export type Coordinate = {
  lat: number;
  lng: number;
};

export type Location = Coordinate & {
  label: string;
};

export type GeocodeResult = {
  location: Location;
  source: string;
};

export type RouteExtractionResult = {
  origin_text: string | null;
  destination_text: string | null;
  source: string;
};

export type PreferencePointsResult = {
  points: PoiCandidate[];
  source: string;
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
  route_mode: string;
  stops: PoiCandidate[];
  walking_minutes: number;
  transfer_count: number;
  crowd_level: string;
  estimated_minutes: number;
  real_duration_minutes: number | null;
  estimated_duration_minutes: number | null;
  distance_meters: number | null;
  fare: number | null;
  fallback_reason: string | null;
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

export type FeedbackPayload = {
  route_id: string;
  liked: boolean;
  emotion_primary: string;
  provider: string;
  reason?: string;
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

export async function geocodeLocation(query: string): Promise<GeocodeResult> {
  const response = await fetch(`${API_BASE_URL}/geocode`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ query })
  });

  if (!response.ok) {
    let message = `Location lookup failed with ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Keep the status-based fallback message.
    }
    throw new Error(message);
  }

  return response.json();
}

export async function extractRouteLocations(
  userText: string
): Promise<RouteExtractionResult> {
  const response = await fetch(`${API_BASE_URL}/extract-route`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ user_text: userText })
  });

  if (!response.ok) {
    throw new Error(`Route extraction failed with ${response.status}`);
  }

  return response.json();
}

export async function fetchPreferencePoints(
  origin: Location,
  radiusMeters = 1800
): Promise<PreferencePointsResult> {
  const response = await fetch(`${API_BASE_URL}/preference-points`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      origin,
      radius_meters: radiusMeters
    })
  });

  if (!response.ok) {
    throw new Error(`Preference points request failed with ${response.status}`);
  }

  return response.json();
}

export async function sendRouteFeedback(payload: FeedbackPayload): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Feedback request failed with ${response.status}`);
  }
}

// ── 인증 API ─────────────────────────────────────────────────

export const TOKEN_KEY = "hows-your-day.access-token.v1";

export type AuthUser = {
  id: string;
  email: string;
  nickname: string;
};

export async function signUp(
  email: string,
  password: string,
  nickname: string
): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, nickname })
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail ?? "회원가입에 실패했습니다");
  }
  return response.json();
}

export async function logIn(
  email: string,
  password: string
): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail ?? "로그인에 실패했습니다");
  }
  const data = await response.json();
  return data.access_token as string;
}

export async function fetchMe(token: string): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) {
    throw new Error("인증 실패");
  }
  return response.json();
}

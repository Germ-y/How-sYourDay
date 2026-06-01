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

export type LocationCandidate = Location & {
  address: string | null;
  source: string;
  category: string | null;
  distance_meters: number | null;
};

export type LocationSearchResult = {
  candidates: LocationCandidate[];
};

export type RouteExtractionResult = {
  origin_text: string | null;
  destination_text: string | null;
  source: string;
};

export type RouteLocationResolutionResult = {
  origin_text: string | null;
  destination_text: string | null;
  origin: LocationCandidate | null;
  destination: LocationCandidate | null;
  origin_candidates: LocationCandidate[];
  destination_candidates: LocationCandidate[];
  source: string;
  selection_source: string;
};

export type PreviewInsight = {
  label: string;
  value: string;
  kind: "route" | "time" | "stop" | "task" | "mood" | string;
};

export type PreviewInsightsResult = {
  insights: PreviewInsight[];
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

export type SavedPlacePayload = {
  name: string;
  address: string;
  kind: string;
  lat?: number | null;
  lng?: number | null;
};

export type SavedPlaceRecord = SavedPlacePayload & {
  id: string;
  created_at: string;
  updated_at: string;
};

export type SavedPlacesResult = {
  places: SavedPlaceRecord[];
};

export type AuthUser = {
  id: string;
  email: string;
  nickname: string;
};

export type LoginResult = {
  access_token: string;
  token_type: string;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8010";
const DEMO_USER_ID = "demo-user";
const ACCESS_TOKEN_KEY = "hows-your-day.access-token.v1";

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

export async function searchLocations(
  query: string,
  size = 5
): Promise<LocationSearchResult> {
  const response = await fetch(`${API_BASE_URL}/search-locations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ query, size })
  });

  if (!response.ok) {
    throw new Error(`Location search failed with ${response.status}`);
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

export async function resolveRouteLocations(
  userText: string
): Promise<RouteLocationResolutionResult> {
  const response = await fetch(`${API_BASE_URL}/resolve-route-locations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ user_text: userText })
  });

  if (!response.ok) {
    throw new Error(`Route location resolution failed with ${response.status}`);
  }

  return response.json();
}

export async function fetchPreviewInsights(payload: {
  user_text: string;
  origin_text?: string;
  destination_text?: string;
  active_mood?: string;
}): Promise<PreviewInsightsResult> {
  const response = await fetch(`${API_BASE_URL}/preview-insights`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Preview insights failed with ${response.status}`);
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

export async function fetchSavedPlaces(): Promise<SavedPlacesResult> {
  const response = await fetch(`${API_BASE_URL}/me/saved-places`, {
    headers: userHeaders()
  });

  if (!response.ok) {
    throw new Error(`Saved places request failed with ${response.status}`);
  }

  return response.json();
}

export async function createSavedPlace(
  payload: SavedPlacePayload
): Promise<SavedPlaceRecord> {
  const response = await fetch(`${API_BASE_URL}/me/saved-places`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...userHeaders()
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Saved place create failed with ${response.status}`);
  }

  return response.json();
}

export async function deleteSavedPlace(id: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/me/saved-places/${id}`, {
    method: "DELETE",
    headers: userHeaders()
  });

  if (!response.ok) {
    throw new Error(`Saved place delete failed with ${response.status}`);
  }
}

export async function signup(payload: {
  email: string;
  password: string;
  nickname: string;
}): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/auth/signup`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Signup failed with ${response.status}`);
  }

  return response.json();
}

export async function login(payload: {
  email: string;
  password: string;
}): Promise<LoginResult> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Login failed with ${response.status}`);
  }

  const result = await response.json();
  setAccessToken(result.access_token);
  return result;
}

export async function fetchMe(): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: authHeaders()
  });

  if (!response.ok) {
    throw new Error(`Me request failed with ${response.status}`);
  }

  return response.json();
}

export function logout() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  }
}

function userHeaders(): Record<string, string> {
  const token = accessToken();
  if (token) {
    return {
      Authorization: `Bearer ${token}`,
      "X-User-Id": DEMO_USER_ID
    };
  }

  return {
    "X-User-Id": DEMO_USER_ID
  };
}

function authHeaders(): Record<string, string> {
  const token = accessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function accessToken() {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

function setAccessToken(token: string) {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
  }
}

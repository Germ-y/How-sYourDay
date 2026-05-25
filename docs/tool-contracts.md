# Tool Contracts

All tools return structured data. Provider-specific fields must be normalized at
the tool boundary so the agent and planner do not depend on Kakao, Naver, Tmap,
or any single map vendor.

## `extract_intent`

Input:

```json
{
  "user_text": "print my report, visit clinic, home by 5, tired"
}
```

Output:

```json
{
  "tasks": [
    {
      "kind": "print",
      "label": "Print document",
      "poi_query": "print shop",
      "priority": 1,
      "required": true
    }
  ],
  "constraints": {
    "deadline": "17:00",
    "destination": "home",
    "max_walking_minutes": null,
    "must_arrive_before_deadline": true
  }
}
```

## `analyze_emotion`

Output:

```json
{
  "primary": "tired",
  "walking_tolerance": "low",
  "crowd_tolerance": "low",
  "transfer_tolerance": "medium",
  "time_pressure_tolerance": "medium",
  "recovery_need": "high"
}
```

## `landmark_emotion_prior`

Purpose: provide cold-start emotional metadata for POIs, route segments, and
areas before user feedback exists.

Input:

```json
{
  "landmark_type": "park"
}
```

Output:

```json
{
  "landmark_type": "park",
  "emotion_tags": ["calm", "recovery", "walkable"],
  "fatigue_modifier": -4,
  "crowd_modifier": -3,
  "noise_modifier": -2,
  "recovery_bonus": 8,
  "reason": "Parks are usually calmer recovery spaces for cold-start scoring."
}
```

Allowed `landmark_type` values:

- `park`
- `river`
- `university`
- `transit_hub`
- `main_road`
- `side_street`
- `medical`
- `commercial`

Allowed `emotion_tags` values:

- `calm`
- `recovery`
- `crowded`
- `familiar`
- `high_noise`
- `walkable`
- `stressful`

## `map_search_poi`

Purpose: wrap Kakao Local API or a mock provider and return normalized POI
candidates.

Input:

```json
{
  "query": "print shop",
  "category": "print",
  "origin": {
    "lat": 37.5882,
    "lng": 126.9936
  },
  "radius_meters": 1500
}
```

Output:

```json
{
  "provider": "kakao",
  "candidates": [
    {
      "id": "poi-print-1",
      "provider_id": "kakao-123",
      "name": "Campus Print Lab",
      "category": "print",
      "landmark_type": "university",
      "emotion_tags": ["familiar", "walkable"],
      "lat": 37.5889,
      "lng": 126.9942,
      "distance_meters": 180,
      "source_confidence": "mock"
    }
  ]
}
```

## `map_route_path`

Purpose: wrap a route provider or deterministic mock routing and return route
candidates the planner can compare.

Input:

```json
{
  "origin": {
    "lat": 37.5882,
    "lng": 126.9936
  },
  "stops": [
    {
      "id": "poi-print-1",
      "lat": 37.5889,
      "lng": 126.9942
    }
  ],
  "destination": "home",
  "mode_preferences": ["walk", "transit"]
}
```

Output:

```json
{
  "routes": [
    {
      "id": "route-low-stress",
      "provider": "mock",
      "stops": ["poi-print-1", "poi-clinic-1"],
      "estimated_minutes": 50,
      "walking_minutes": 20,
      "transfer_count": 1,
      "crowd_level": "medium",
      "cost_estimate": null,
      "polyline": [
        {
          "lat": 37.5882,
          "lng": 126.9936
        },
        {
          "lat": 37.5889,
          "lng": 126.9942
        }
      ],
      "segments": [
        {
          "mode": "walk",
          "minutes": 8,
          "landmark_type": "side_street",
          "emotion_tags": ["calm", "walkable"]
        }
      ]
    }
  ]
}
```

## `emotion_score`

Purpose: calculate decomposed emotional cost for each route candidate. The
planner should use this structure instead of relying only on a final score.

Input:

```json
{
  "route": {
    "id": "route-low-stress",
    "walking_minutes": 20,
    "transfer_count": 1,
    "crowd_level": "medium"
  },
  "emotion_state": {
    "primary": "tired",
    "walking_tolerance": "low",
    "crowd_tolerance": "low",
    "transfer_tolerance": "medium",
    "recovery_need": "high"
  },
  "landmark_priors": []
}
```

Output:

```json
{
  "route_id": "route-low-stress",
  "fatigue_cost": 12,
  "walking_cost": 18,
  "crowd_cost": 3,
  "transfer_cost": 2,
  "time_pressure_cost": 8,
  "familiarity_bonus": 10,
  "recovery_bonus": 7,
  "total_emotional_cost": 26,
  "comfort_score": 74,
  "stress_score": 26,
  "reasons": [
    "Walking is near the upper limit for a tired day.",
    "Transfer count is low.",
    "Route includes a calm side street segment."
  ]
}
```

## `evaluate_tradeoffs`

Purpose: compare viable route and stop combinations before composing a final
daily plan.

Input:

```json
{
  "routes": [],
  "emotion_scores": [],
  "constraints": {
    "deadline": "17:00"
  }
}
```

Output:

```json
{
  "selected_route_id": "route-low-stress",
  "tradeoffs": [
    {
      "chosen_option": "route-low-stress",
      "rejected_option": "route-faster",
      "reason": "The faster route saves 10 minutes but adds transfers and crowd exposure.",
      "user_visible_label": "Calmer route over fastest route",
      "cost_delta": {
        "estimated_minutes": 10,
        "emotional_cost": -18
      }
    }
  ]
}
```

## `compose_daily_plan`

Purpose: assemble the chosen POIs, route, emotional cost, timeline, tradeoffs,
and recommendation text into a single planner response.

Input:

```json
{
  "tasks": [],
  "emotion_state": {},
  "poi_candidates": [],
  "route_candidates": [],
  "constraints": {},
  "selected_route_id": "route-low-stress",
  "tradeoffs": []
}
```

Output:

```json
{
  "ordered_stops": [
    {
      "stop_id": "poi-print-1",
      "task_kind": "print",
      "arrival_time": "14:18",
      "departure_time": "14:28",
      "why_here": "Closest print option with a familiar university landmark prior."
    }
  ],
  "estimated_timeline": [
    {
      "time": "14:00",
      "label": "Leave current location",
      "type": "depart"
    },
    {
      "time": "14:18",
      "label": "Print document",
      "type": "task"
    }
  ],
  "selected_route": {
    "id": "route-low-stress",
    "estimated_minutes": 50
  },
  "emotional_cost": {
    "total_emotional_cost": 26,
    "comfort_score": 74,
    "stress_score": 26
  },
  "tradeoffs": [],
  "recommendations": [
    {
      "kind": "recovery",
      "label": "Skip the cafe unless you still feel drained after the clinic."
    }
  ],
  "map_overlays": {},
  "explanation": "This route is slower than the fastest option, but it keeps transfers low and avoids the highest-crowd path."
}
```

## `map_view_model`

Purpose: convert planner output into a provider-agnostic map shape for the web
client. The frontend may render this with Kakao Maps JS SDK, but the contract
must not expose Kakao-specific fields.

Output:

```json
{
  "center": {
    "lat": 37.5889,
    "lng": 126.9942
  },
  "fit_bounds": {
    "south_west": {
      "lat": 37.5876,
      "lng": 126.9926
    },
    "north_east": {
      "lat": 37.5897,
      "lng": 126.9954
    }
  },
  "selected_route_id": "route-low-stress",
  "markers": [
    {
      "id": "marker-poi-print-1",
      "type": "stop",
      "lat": 37.5889,
      "lng": 126.9942,
      "label": "Campus Print Lab",
      "badge": "1"
    }
  ],
  "polylines": [
    {
      "id": "polyline-route-low-stress",
      "route_id": "route-low-stress",
      "selected": true,
      "points": [
        {
          "lat": 37.5882,
          "lng": 126.9936
        }
      ],
      "emotion_level": "calm"
    }
  ],
  "emotion_zones": [
    {
      "id": "zone-transit-hub-1",
      "type": "hotspot",
      "emotion_tags": ["crowded", "stressful"],
      "center": {
        "lat": 37.59,
        "lng": 126.996
      },
      "radius_meters": 120
    }
  ],
  "tradeoff_badges": [
    {
      "route_id": "route-low-stress",
      "label": "Calmer",
      "description": "Fewer transfers, slightly longer duration."
    }
  ]
}
```

## Acceptance Scenarios

These are not implementation tests yet, but future code should be validated
against them.

- If the user says they are tired and must be home by 5, the planner should
  choose a lower-stress route unless the deadline would be missed.
- If time is tight, the planner may choose a faster but more stressful route and
  must explain that tradeoff.
- If the user asks to rest or recover, candidate expansion should include a
  recovery POI.
- If no feedback memory exists, landmark priors alone should still produce a
  route emotional cost.

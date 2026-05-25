# Tool Contract

모든 tool은 구조화된 데이터를 반환합니다. Kakao, Naver, Tmap 같은 provider
응답은 tool boundary에서 내부 contract로 정규화해야 합니다.

## `extract_intent`

사용자 입력에서 task, constraint, emotion state를 추출합니다.

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
    "max_walking_minutes": 20,
    "must_arrive_before_deadline": true
  },
  "emotion": {
    "primary": "tired",
    "walking_tolerance": "low",
    "crowd_tolerance": "low",
    "transfer_tolerance": "medium",
    "time_pressure_tolerance": "medium",
    "recovery_need": "high"
  }
}
```

## `map_search_poi`

Kakao Local API 또는 mock provider를 감싸고, planner가 사용할 POI 후보로
정규화합니다.

```json
{
  "id": "poi-print-1",
  "provider_id": "mock-print-1",
  "name": "Campus Print Lab",
  "category": "print",
  "landmark_type": "university",
  "emotion_tags": ["familiar", "walkable"],
  "lat": 37.5889,
  "lng": 126.9942,
  "distance_meters": 180,
  "source_confidence": "mock"
}
```

## `map_route_path`

route provider 또는 mock routing을 감싸고, planner가 비교할 수 있는 후보
route를 반환합니다.

```json
{
  "id": "route-low-stress",
  "provider": "mock",
  "estimated_minutes": 50,
  "walking_minutes": 20,
  "transfer_count": 1,
  "crowd_level": "medium",
  "cost_estimate": null,
  "polyline": [
    {
      "lat": 37.5882,
      "lng": 126.9936
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
```

## `landmark_emotion_prior`

사용자 피드백이 없는 cold start 상황에서 landmark별 감정 prior를 제공합니다.

```json
{
  "landmark_type": "park",
  "emotion_tags": ["calm", "recovery", "walkable"],
  "fatigue_modifier": -4,
  "crowd_modifier": -3,
  "noise_modifier": -2,
  "recovery_bonus": 8,
  "reason": "Parks usually provide calm recovery value for cold-start scoring."
}
```

## `emotion_score`

route별 감정 비용을 분해해서 계산합니다. planner는 단일 점수가 아니라
이 비용 구조를 이용해 route를 비교합니다.

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
    "Walking load stays within a tolerable range.",
    "Calm or recovery-friendly landmarks reduce emotional cost."
  ]
}
```

## `evaluate_tradeoffs`

route 후보와 감정 비용을 비교해 최종 route를 선택합니다.

```json
{
  "selected_route_id": "route-low-stress",
  "tradeoffs": [
    {
      "chosen_option": "route-low-stress",
      "rejected_option": "route-faster",
      "reason": "route-low-stress adds 10 minutes but lowers emotional cost by 18.",
      "user_visible_label": "Calmer route over fastest route",
      "cost_delta": {
        "estimated_minutes": 10,
        "emotional_cost": -18
      }
    }
  ],
  "fallback_used": false
}
```

## `compose_daily_plan`

선택된 route, stop, timeline, recommendation, map overlay, explanation을
하나의 planner response로 조립합니다.

```json
{
  "ordered_stops": [
    {
      "stop_id": "poi-print-1",
      "task_kind": "print",
      "arrival_time": "14:18",
      "departure_time": "14:28",
      "why_here": "Campus Print Lab handles the print task near a university area."
    }
  ],
  "estimated_timeline": [],
  "selected_route": {},
  "emotional_cost": {},
  "tradeoffs": [],
  "recommendations": [],
  "map_overlays": {},
  "explanation": "Chosen because it keeps transfers low and avoids high-crowd corridors."
}
```

## `map_view_model`

frontend가 Kakao Maps JS SDK로 렌더링할 수 있는 provider-agnostic 지도
view model입니다.

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
  "markers": [],
  "polylines": [],
  "emotion_zones": [],
  "tradeoff_badges": []
}
```

## Acceptance Scenarios

- 피곤하고 5시까지 집에 가야 하면 fastest route보다 lower-stress route를 우선한다.
- 시간이 촉박하면 faster route를 선택할 수 있고, stress 증가 tradeoff를 설명한다.
- 쉬고 싶다는 입력이 있으면 recovery POI와 recommendation이 포함된다.
- 사용자 memory가 없어도 landmark prior만으로 emotional cost를 계산한다.

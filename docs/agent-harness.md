# Agent Harness 설계

## 목표

How's Your Day의 핵심은 최단 경로 추천이 아니라, 사용자의 하루를 감정
비용까지 포함해 조율하는 planning system입니다.

감정은 `mood label`이 아닙니다. 예를 들어 `tired`는 낮은 걷기 허용량,
낮은 혼잡 허용량, 높은 회복 필요성으로 번역됩니다. planner는 이 값을
route와 POI 후보를 선택할 때 실제 decision variable로 사용합니다.

## Planning Pipeline

```text
User Intent
  -> Constraint Extraction
  -> Candidate Expansion
  -> Emotional Cost Modeling
  -> Tradeoff Evaluation
  -> Plan Composition
  -> Natural Language Synthesis
```

도구는 후보와 비용을 구조화해 반환하고, planner는 그 후보들을 비교해
하루 동선을 선택합니다. 이 흐름이 프로젝트의 agent harness입니다.

## Agent Input

```json
{
  "user_text": "I need to print, visit the clinic, and get home by 5. I am tired.",
  "origin": {
    "label": "Current location",
    "lat": 37.5882,
    "lng": 126.9936
  }
}
```

## Planner Output

planner 출력은 UI 렌더링, 디버깅, 발표 설명이 모두 가능하도록 의사결정
근거를 포함해야 합니다.

```json
{
  "summary": "A planned day optimized around tired energy.",
  "ordered_stops": [],
  "estimated_timeline": [],
  "selected_route": {},
  "emotional_cost": {
    "fatigue_cost": 12,
    "walking_cost": 18,
    "crowd_cost": 3,
    "transfer_cost": 2,
    "time_pressure_cost": 8,
    "familiarity_bonus": 10,
    "recovery_bonus": 7,
    "total_emotional_cost": 26
  },
  "tradeoffs": [],
  "recommendations": [],
  "map_overlays": {},
  "explanation": "Chosen because it keeps transfers low and avoids high-crowd corridors."
}
```

## Tool Order

1. `extract_intent`
2. `map_search_poi`
3. `map_route_path`
4. `emotion_score`
5. `evaluate_tradeoffs`
6. `compose_daily_plan`
7. `map_view_model`

현재 구현은 mock provider 기반 deterministic logic입니다. 실제 Kakao API나
LLM은 provider adapter 뒤에 붙여야 하며, agent나 frontend가 vendor 응답에
직접 의존하면 안 됩니다.

## Planner Policy

planner는 첫 번째 route를 선택하지 않습니다. 다음 순서로 판단합니다.

1. required task를 수행할 수 있는가
2. deadline을 만족하는가
3. 감정 비용이 낮은가
4. 걷기, 환승, 혼잡 비용이 과도하지 않은가
5. 회복 POI나 calm landmark가 도움이 되는가
6. 시간 압박이 크면 빠른 route를 선택할 필요가 있는가

deadline을 만족하는 route가 없으면 가장 덜 늦는 route를 fallback으로
선택하고, explanation에 그 사실을 명시합니다.

## Tradeoff Model

tradeoff는 planner의 핵심 출력입니다.

예시:

- 더 편한 길 vs 더 빠른 길
- 덜 걷는 길 vs 더 오래 걸리는 길
- 익숙한 길 vs 시간 증가
- recovery stop 추가 vs 귀가 지연
- 환승 감소 vs 걷기 증가

각 tradeoff는 다음 정보를 포함합니다.

- `chosen_option`
- `rejected_option`
- `reason`
- `user_visible_label`
- `cost_delta`

## Cold Start 전략

사용자 피드백이 없을 때는 landmark prior로 감정 비용을 계산합니다.

지원하는 `landmark_type`:

- `park`
- `river`
- `university`
- `transit_hub`
- `main_road`
- `side_street`
- `medical`
- `commercial`

지원하는 `emotion_tags`:

- `calm`
- `recovery`
- `crowded`
- `familiar`
- `high_noise`
- `walkable`
- `stressful`

예시:

```json
{
  "landmark_type": "park",
  "emotion_tags": ["calm", "recovery", "walkable"],
  "fatigue_modifier": -4,
  "crowd_modifier": -3,
  "recovery_bonus": 8
}
```

## 지도 전략

MVP의 기본 provider는 Kakao입니다.

- `Kakao Local API`: POI/category search
- `Kakao Maps JS SDK`: marker, polyline, 지도 렌더링
- Directions: 우선 mock route provider 사용, 이후 필요하면 Tmap/Naver 등으로 교체

planner는 provider-agnostic `map_view_model`만 반환합니다. frontend는 이
view model을 Kakao Maps JS SDK로 렌더링하면 됩니다.

## 지도는 검증 표면

지도는 장식이 아니라 planner 판단을 검증하는 표면입니다.

향후 UI에서 보여야 할 것:

- stop markers
- selected route polyline
- alternative route summary
- emotional hotspots
- recovery candidates
- tradeoff badges

## 이후 개인화

memory/personalization은 v1 이후 단계입니다.

사용자 피드백 예시:

- "이 길은 너무 복잡했어."
- "이 버스는 익숙해서 편했어."
- "걷는 시간이 너무 길었어."
- "중간에 쉬니까 좋았어."

이 피드백은 free-form memory가 아니라 walking/crowd/transfer/recovery
weight 업데이트로 이어져야 합니다.

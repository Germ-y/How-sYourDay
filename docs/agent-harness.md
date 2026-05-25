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

## Provider Strategy

현재 MVP는 다음 provider 조합을 사용합니다.

- `Kakao Local API`: POI/category search
- `Tmap pedestrian/transit API`: 실제 route 후보 생성
- `Kakao Maps JS SDK`: marker, polyline, 지도 렌더링
- `mock route`: Tmap route를 전혀 만들 수 없을 때만 fallback

agent와 planner는 provider 응답에 직접 의존하지 않고, 내부 contract인
`PoiCandidate`, `RouteCandidate`, `MapViewModel`만 사용합니다.

## Agent Input

```json
{
  "user_text": "I need to print, visit the clinic, and get home by 5. I am tired.",
  "origin": {
    "label": "Current location",
    "lat": 37.5882,
    "lng": 126.9936
  },
  "destination": {
    "label": "집",
    "lat": 37.5826,
    "lng": 127.0019
  }
}
```

## Planner Output

planner 출력은 UI 렌더링, 디버깅, 발표 설명이 모두 가능하도록 의사결정
근거를 포함합니다.

```json
{
  "summary": "일정을 Tmap 혼합 기준으로 조율했어요.",
  "ordered_stops": [],
  "estimated_timeline": [],
  "selected_route": {
    "provider": "tmap-mixed",
    "real_duration_minutes": 17,
    "fallback_reason": "일부 짧은 구간은 추정 이동으로 보완했어요."
  },
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
  "explanation": "Tmap 실제 경로와 감정 비용을 기준으로 선택했어요."
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

## Route Policy

planner는 첫 번째 route를 선택하지 않습니다. 다음 순서로 판단합니다.

1. required task를 수행할 수 있는가
2. deadline을 만족하는가
3. 실제 route duration이 어느 정도인가
4. 감정 비용이 낮은가
5. 걷기, 환승, 혼잡 비용이 과도하지 않은가
6. 회복 POI나 calm landmark가 도움이 되는가

Tmap route가 하나라도 생성되면 mock route는 후보에서 제외합니다. Tmap route를
전혀 만들 수 없을 때만 mock fallback을 반환합니다.

## Tmap Mixed Route

Tmap route는 `origin -> stops -> destination`을 leg 단위로 생성합니다.
특정 leg가 실패하면 전체 route를 버리지 않고, 해당 leg만 estimated walking으로
보완합니다. 이 경우 provider는 `tmap-mixed`이며, UI에는 일부 추정 구간이
포함되었다고 표시합니다.

## Tradeoff Model

tradeoff는 planner의 핵심 출력입니다.

- 더 편한 길 vs 더 빠른 길
- 덜 걷는 길 vs 더 오래 걸리는 길
- 환승 감소 vs 걷기 증가
- recovery stop 추가 vs 귀가 지연
- 실제 route 우선 vs fallback route 사용

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

## 지도는 검증 표면

지도는 장식이 아니라 planner 판단을 검증하는 표면입니다.

- stop markers
- selected route polyline
- alternative route summary
- emotional hotspots
- recovery candidates
- tradeoff badges

frontend는 provider-agnostic `map_view_model`을 Kakao Maps JS SDK로 렌더링합니다.

## 이후 개인화

route feedback은 free-form memory가 아니라 walking/crowd/transfer/recovery
weight 업데이트로 이어집니다.

예시:

- "이 길은 너무 복잡했어."
- "이 버스는 익숙해서 편했어."
- "걷는 시간이 너무 길었어."
- "중간에 쉬니까 좋았어."

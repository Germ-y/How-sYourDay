# Agent Harness Spec

## Goal

Build a tool-using daily planning agent that converts natural language into a
usable daily movement plan. The product value is not the shortest path. It is a
daily orchestration system that models emotional cost alongside time, distance,
and task constraints.

Emotion is treated as a decision variable, not a mood label. For example,
`tired` becomes lower walking tolerance, lower crowd tolerance, and higher
recovery need. The planner must use those variables when choosing between route
and POI candidates.

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

This pipeline is the core harness. Tools produce structured candidates and
costs. The planner compares them, explains tradeoffs, and returns a daily flow
that the frontend can render on a map.

## Agent Inputs

```json
{
  "user_text": "I need to print, visit the clinic, and get home by 5. I am tired.",
  "origin": {
    "label": "Current location",
    "lat": 37.5882,
    "lng": 126.9936
  },
  "time_context": "2026-05-25T14:00:00+09:00"
}
```

## Planner Output

The planner output must make the decision process visible enough for UI,
debugging, and later LLM synthesis.

```json
{
  "summary": "A low-stress plan with printing first, clinic second, then home.",
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
2. `analyze_emotion`
3. `landmark_emotion_prior`
4. `map_search_poi`
5. `map_route_path`
6. `emotion_score`
7. `evaluate_tradeoffs`
8. `compose_daily_plan`
9. `map_view_model`
10. `natural_language_synthesis`

The current implementation may keep deterministic mock tools, but it should
preserve this order conceptually. Real providers should be added behind tool
adapters, not called directly from the agent or frontend.

## Planner Decision Rules

The planner must compare route and POI combinations. It must not simply select
the first route returned by a map provider.

Selection should consider:

- task priority and required order
- deadline and time pressure
- walking minutes
- transfer count
- expected crowd level
- landmark emotional prior
- recovery opportunity
- user preference memory when available

The selected plan should include tradeoffs. A plan that is slower but calmer is
valid only if the response explains the time cost. A plan that is faster but
more stressful is valid only if deadline pressure justifies it.

## Tradeoff Model

Tradeoffs are first-class planner output. Examples:

- more comfortable route vs faster route
- less walking vs higher travel cost
- familiar bus route vs longer duration
- recovery cafe stop vs delayed return home
- fewer transfers vs slightly more walking

Each tradeoff should include:

- `chosen_option`
- `rejected_option`
- `reason`
- `user_visible_label`
- `cost_delta`

## Cold Start Strategy

Before user feedback exists, the system scores places and routes using
landmark-based emotional priors.

Supported `landmark_type` values:

- `park`
- `river`
- `university`
- `transit_hub`
- `main_road`
- `side_street`
- `medical`
- `commercial`

Supported `emotion_tags` values:

- `calm`
- `recovery`
- `crowded`
- `familiar`
- `high_noise`
- `walkable`
- `stressful`

Example priors:

```json
{
  "landmark_type": "park",
  "emotion_tags": ["calm", "recovery", "walkable"],
  "fatigue_modifier": -4,
  "crowd_modifier": -3,
  "recovery_bonus": 8
}
```

The planner should use these priors when no personal feedback exists. Later,
explicit feedback updates preference weights and can override generic priors.

## Map Provider Strategy

Kakao is the default provider for the MVP contract.

- `Kakao Local API`: POI and category search
- `Kakao Maps JS SDK`: map rendering, stop markers, route polylines
- Directions: keep behind `map_route_path`; use mock routing first, then replace
  with Kakao-compatible, Tmap, Naver, or another route provider if needed

Provider-specific responses must be normalized before reaching the planner.
The planner should only know the internal contracts in `tool-contracts.md`.

## Map As Validation Surface

The map is not just a visual decoration. It is the surface where the planner's
decision can be inspected.

The frontend should eventually render:

- stop markers
- selected route polyline
- alternative route summaries
- emotional hotspots
- recovery candidates
- tradeoff badges

The map should receive a provider-agnostic `map_view_model` so Kakao can be
replaced later without changing planner output.

## Personalization Later

Feedback updates user preference weights:

- walking tolerance
- crowd tolerance
- transfer sensitivity
- landmark affinity
- recovery-place preference

Feedback examples:

- "This route was too crowded."
- "This bus felt familiar."
- "The walk was too long."
- "The recovery stop helped."

These updates should change future emotional cost calculations, not just add
free-form memory text.

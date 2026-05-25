# Agent Harness Spec

## Goal

Build a tool-using daily planning agent that converts natural language into a
usable daily movement plan.

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

## Agent Output

```json
{
  "summary": "A low-stress plan with printing first, clinic second, then home.",
  "emotion": {
    "primary": "tired",
    "walking_tolerance": "low",
    "crowd_tolerance": "low"
  },
  "stops": [],
  "routes": [],
  "tradeoffs": []
}
```

## Tool Order

1. `extract_intent`
2. `analyze_emotion`
3. `search_poi`
4. `route_path`
5. `emotion_score`
6. `compose_plan`

## Cold Start Strategy

Before user feedback exists, the system scores routes and places using:

- place type
- landmark type
- expected crowd level
- walking distance
- transfer count
- familiarity proxy
- weather and time of day later

## Personalization Later

Feedback updates user preference weights:

- walking tolerance
- crowd tolerance
- transfer sensitivity
- landmark affinity
- recovery-place preference


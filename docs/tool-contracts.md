# Tool Contracts

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
      "priority": 1
    }
  ],
  "constraints": {
    "deadline": "17:00",
    "destination": "home"
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
  "recovery_need": "high"
}
```

## `search_poi`

Output:

```json
{
  "candidates": [
    {
      "id": "poi-print-1",
      "name": "Campus Print Lab",
      "category": "print",
      "landmark_type": "university",
      "lat": 37.5889,
      "lng": 126.9942
    }
  ]
}
```

## `emotion_score`

Output:

```json
{
  "comfort_score": 82,
  "stress_score": 18,
  "reasons": [
    "Short walking distance",
    "Low transfer count"
  ]
}
```


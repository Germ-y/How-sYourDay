import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from api.schemas import Constraints, EmotionState
from tools.kakao_local import _get_env_value
from tools.llm_intent import DEFAULT_INTENT_MODEL, OPENAI_RESPONSES_URL, _response_text

_WAYPOINT_POLICY_CACHE: dict[str, "WaypointPolicy"] = {}
_WAYPOINT_POLICY_CACHE_LIMIT = 80

WAYPOINT_POLICY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "allow_optional_waypoints",
        "positive_queries",
        "avoid_landmark_types",
        "max_optional_waypoints",
        "max_detour_minutes",
        "reason",
    ],
    "properties": {
        "allow_optional_waypoints": {"type": "boolean"},
        "positive_queries": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["query", "landmark_type", "reason"],
                "properties": {
                    "query": {"type": "string"},
                    "landmark_type": {
                        "type": "string",
                        "enum": [
                            "cafe",
                            "park",
                            "library",
                            "river",
                            "side_street",
                            "convenience_store",
                        ],
                    },
                    "reason": {"type": "string"},
                },
            },
        },
        "avoid_landmark_types": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "transit_hub",
                    "main_road",
                    "shopping_mall",
                    "nightlife",
                    "school",
                    "medical",
                    "commercial",
                ],
            },
        },
        "max_optional_waypoints": {"type": "integer", "minimum": 0, "maximum": 2},
        "max_detour_minutes": {"type": "integer", "minimum": 0, "maximum": 20},
        "reason": {"type": "string"},
    },
}


@dataclass(frozen=True)
class WaypointQuery:
    query: str
    landmark_type: str
    reason: str


@dataclass(frozen=True)
class WaypointPolicy:
    allow_optional_waypoints: bool
    positive_queries: list[WaypointQuery]
    avoid_landmark_types: list[str]
    max_optional_waypoints: int
    max_detour_minutes: int
    reason: str


def build_waypoint_policy(
    user_text: str,
    emotion: EmotionState,
    constraints: Constraints,
) -> WaypointPolicy:
    if _time_is_tight(emotion, constraints):
        return WaypointPolicy(
            allow_optional_waypoints=False,
            positive_queries=[],
            avoid_landmark_types=["transit_hub", "main_road", "shopping_mall"],
            max_optional_waypoints=0,
            max_detour_minutes=0,
            reason="시간 압박이 커서 감정 경유지를 추가하지 않습니다.",
        )

    llm_policy = _build_waypoint_policy_with_llm(user_text, emotion, constraints)
    if llm_policy:
        return llm_policy

    return _fallback_waypoint_policy(emotion)


def _build_waypoint_policy_with_llm(
    user_text: str,
    emotion: EmotionState,
    constraints: Constraints,
) -> WaypointPolicy | None:
    if (os.environ.get("HYS_DISABLE_LLM") or _get_env_value("HYS_DISABLE_LLM")) == "1":
        return None

    api_key = _get_env_value("OPENAI_API_KEY")
    if not api_key:
        return None

    model = (
        os.environ.get("OPENAI_INTENT_MODEL")
        or _get_env_value("OPENAI_INTENT_MODEL")
        or DEFAULT_INTENT_MODEL
    )
    cache_key = _policy_cache_key(model, user_text, emotion, constraints)
    if cache_key in _WAYPOINT_POLICY_CACHE:
        return _WAYPOINT_POLICY_CACHE[cache_key]

    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You decide whether an emotion-aware route should add a real "
                    "optional waypoint. Never invent coordinates. Return search "
                    "queries and landmark types only. If time pressure is high or "
                    "there is a hard deadline risk, disallow optional waypoints. "
                    "Prefer at most one small detour for tired, anxious, low-crowd, "
                    "or high-recovery users."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_text": user_text,
                        "emotion": emotion.model_dump(),
                        "constraints": constraints.model_dump(),
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "emotion_waypoint_policy",
                "strict": True,
                "schema": WAYPOINT_POLICY_SCHEMA,
            }
        },
        "max_output_tokens": 700,
    }

    raw = _post_openai(api_key, payload)
    if raw is None:
        return None

    text = _response_text(raw)
    if not text:
        return None

    try:
        data = json.loads(text)
        policy = WaypointPolicy(
            allow_optional_waypoints=bool(data["allow_optional_waypoints"]),
            positive_queries=[
                WaypointQuery(
                    query=item["query"],
                    landmark_type=item["landmark_type"],
                    reason=item["reason"],
                )
                for item in data["positive_queries"]
            ],
            avoid_landmark_types=list(data["avoid_landmark_types"]),
            max_optional_waypoints=int(data["max_optional_waypoints"]),
            max_detour_minutes=int(data["max_detour_minutes"]),
            reason=str(data["reason"]),
        )
        _remember_policy(cache_key, policy)
        return policy
    except (KeyError, TypeError, ValueError):
        return None


def _policy_cache_key(
    model: str,
    user_text: str,
    emotion: EmotionState,
    constraints: Constraints,
) -> str:
    return json.dumps(
        {
            "model": model,
            "text": user_text.strip(),
            "emotion": emotion.model_dump(),
            "constraints": constraints.model_dump(),
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _remember_policy(cache_key: str, policy: WaypointPolicy) -> None:
    if len(_WAYPOINT_POLICY_CACHE) >= _WAYPOINT_POLICY_CACHE_LIMIT:
        _WAYPOINT_POLICY_CACHE.pop(next(iter(_WAYPOINT_POLICY_CACHE)))
    _WAYPOINT_POLICY_CACHE[cache_key] = policy


def _fallback_waypoint_policy(emotion: EmotionState) -> WaypointPolicy:
    if emotion.primary not in {"tired", "anxious"} and emotion.recovery_need != "high":
        return WaypointPolicy(
            allow_optional_waypoints=False,
            positive_queries=[],
            avoid_landmark_types=["transit_hub", "main_road"],
            max_optional_waypoints=0,
            max_detour_minutes=0,
            reason="감정 경유지를 추가할 필요가 낮습니다.",
        )

    queries = [
        WaypointQuery(
            query="조용한 카페",
            landmark_type="cafe",
            reason="짧게 앉아 회복할 수 있습니다.",
        ),
        WaypointQuery(
            query="공원",
            landmark_type="park",
            reason="혼잡과 소음을 줄이는 데 도움이 됩니다.",
        ),
        WaypointQuery(
            query="도서관",
            landmark_type="library",
            reason="조용한 공간을 경유할 수 있습니다.",
        ),
    ]
    if emotion.crowd_tolerance == "low":
        queries.insert(
            0,
            WaypointQuery(
                query="조용한 골목",
                landmark_type="side_street",
                reason="사람 많은 구간을 피하는 데 도움이 됩니다.",
            ),
        )

    return WaypointPolicy(
        allow_optional_waypoints=True,
        positive_queries=queries,
        avoid_landmark_types=["transit_hub", "main_road", "shopping_mall", "nightlife"],
        max_optional_waypoints=1,
        max_detour_minutes=10,
        reason="감정 부담을 낮출 수 있는 작은 경유지를 탐색합니다.",
    )


def _time_is_tight(emotion: EmotionState, constraints: Constraints) -> bool:
    return emotion.time_pressure_tolerance == "high" or (
        constraints.deadline is not None and emotion.recovery_need == "low"
    )


def _post_openai(api_key: str, payload: dict) -> dict | None:
    request = Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return None

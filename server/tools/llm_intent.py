import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from api.schemas import Constraints, EmotionState, Task
from tools.extract_intent import ExtractedIntent
from tools.kakao_local import _get_env_value

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_INTENT_MODEL = "gpt-5-nano"
_LLM_INTENT_CACHE: dict[str, ExtractedIntent] = {}
_LLM_INTENT_CACHE_LIMIT = 80

INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tasks", "constraints", "emotion"],
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "label", "poi_query", "priority", "required"],
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["print", "clinic", "recovery"],
                    },
                    "label": {"type": "string"},
                    "poi_query": {"type": "string"},
                    "priority": {"type": "integer", "minimum": 1, "maximum": 10},
                    "required": {"type": "boolean"},
                },
            },
        },
        "constraints": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "deadline",
                "destination",
                "max_walking_minutes",
                "must_arrive_before_deadline",
            ],
            "properties": {
                "deadline": {
                    "anyOf": [
                        {"type": "string", "pattern": "^([01][0-9]|2[0-3]):[0-5][0-9]$"},
                        {"type": "null"},
                    ]
                },
                "destination": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "max_walking_minutes": {
                    "anyOf": [
                        {"type": "integer", "minimum": 1, "maximum": 120},
                        {"type": "null"},
                    ]
                },
                "must_arrive_before_deadline": {"type": "boolean"},
            },
        },
        "emotion": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "primary",
                "walking_tolerance",
                "crowd_tolerance",
                "transfer_tolerance",
                "time_pressure_tolerance",
                "recovery_need",
            ],
            "properties": {
                "primary": {
                    "type": "string",
                    "enum": ["tired", "anxious", "hurried", "steady"],
                },
                "walking_tolerance": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "crowd_tolerance": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "transfer_tolerance": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "time_pressure_tolerance": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "recovery_need": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
            },
        },
    },
}


def extract_intent_with_llm(user_text: str) -> ExtractedIntent | None:
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
    cache_key = _intent_cache_key(model, user_text)
    if cache_key in _LLM_INTENT_CACHE:
        return _LLM_INTENT_CACHE[cache_key]

    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You extract daily planning intent from Korean or English text. "
                    "Return only JSON matching the schema. Use concise Korean labels "
                    "when the user writes Korean. Supported task kinds are print, "
                    "clinic, and recovery. If the user mainly asks for a destination "
                    "route with no task, use one recovery task only when they mention "
                    "rest, fatigue, calm, cafe, or needing a break; otherwise use an "
                    "empty tasks array. Infer tolerances conservatively from emotion."
                ),
            },
            {"role": "user", "content": user_text},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "daily_planning_intent",
                "strict": True,
                "schema": INTENT_SCHEMA,
            }
        },
        "max_output_tokens": 900,
    }

    raw = _post_openai(api_key, payload)
    if raw is None:
        return None

    text = _response_text(raw)
    if not text:
        return None

    try:
        data = json.loads(text)
        tasks = [
            Task(
                kind=task["kind"],
                label=task["label"],
                poi_query=task["poi_query"],
                priority=task["priority"],
                required=task["required"],
            )
            for task in data.get("tasks", [])
        ]
        intent = ExtractedIntent(
            tasks=tasks,
            constraints=Constraints(**data["constraints"]),
            emotion=EmotionState(**data["emotion"]),
        )
        _remember_intent(cache_key, intent)
        return intent
    except (KeyError, TypeError, ValueError, ValidationError):
        return None


def _intent_cache_key(model: str, user_text: str) -> str:
    return f"{model}:{user_text.strip()}"


def _remember_intent(cache_key: str, intent: ExtractedIntent) -> None:
    if len(_LLM_INTENT_CACHE) >= _LLM_INTENT_CACHE_LIMIT:
        _LLM_INTENT_CACHE.pop(next(iter(_LLM_INTENT_CACHE)))
    _LLM_INTENT_CACHE[cache_key] = intent


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


def _response_text(payload: dict) -> str | None:
    direct = payload.get("output_text")
    if isinstance(direct, str):
        return direct

    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if isinstance(text, str):
                return text
    return None

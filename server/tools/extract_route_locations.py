import json
import os
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tools.kakao_local import _get_env_value
from tools.llm_intent import DEFAULT_INTENT_MODEL, OPENAI_RESPONSES_URL, _response_text


ROUTE_EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["origin_text", "destination_text"],
    "properties": {
        "origin_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "destination_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    },
}


@dataclass(frozen=True)
class RouteLocationHints:
    origin_text: str | None
    destination_text: str | None
    source: str


def extract_route_locations(user_text: str) -> RouteLocationHints:
    fallback = _extract_route_locations_with_rules(user_text)
    llm_result = _extract_route_locations_with_llm(user_text)
    if llm_result is None:
        return fallback

    if not llm_result.origin_text and not llm_result.destination_text:
        return fallback

    return RouteLocationHints(
        origin_text=llm_result.origin_text or fallback.origin_text,
        destination_text=llm_result.destination_text or fallback.destination_text,
        source="llm",
    )


def _extract_route_locations_with_rules(user_text: str) -> RouteLocationHints:
    text = re.sub(r"\s+", " ", user_text).strip()
    origin = _first_location_match(
        text,
        [
            r"(?:출발지|시작점)\s*(?:는|은|:)?\s*([^,.;\n]+?)(?=\s*(?:이고|이고요|에서|부터|,|\.|;|$))",
            r"(?:from|starting at|start at|leaving from)\s+([^,.;\n]+?)(?=\s+(?:to|and|then)|[,.;]|$)",
            r"([^,.;\n]+?)(?:에서|부터)\s*(?:출발|시작)",
            r"([^,.;\n]+?)(?:에서|부터)\s+[^,.;\n]+?(?:까지|으로|로)",
        ],
    )
    destination = _known_destination_hint(text) or _first_location_match(
        text,
        [
            r"(?:도착지|목적지)\s*(?:는|은|:)?\s*([^,.;\n]+?)(?=\s*(?:이고|이고요|,|\.|;|$))",
            r"(?:to|get to|go to|going to|head to)\s+([^,.;\n]+?)(?=\s+(?:by|before|after|and|then)|[,.;]|$)",
            r"(?:에서|부터)\s*([^,.;\n]+?)(?:까지|으로|로)(?=\s|,|\.|;|$)",
            r"([^,.;\n]+?)(?:으로|로|까지)\s*(?:가야|갈|가기|가려고|이동|도착|가고|가자|$)",
            r"([^,.;\n]+?)(?:에)\s*(?:가야|갈|가기|가려고|도착)",
        ],
    )

    return RouteLocationHints(
        origin_text=origin,
        destination_text=destination,
        source="rules",
    )


def _extract_route_locations_with_llm(user_text: str) -> RouteLocationHints | None:
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
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "Extract only the route origin and destination mentioned by the user. "
                    "Return place names as written, without coordinates. If the user omits "
                    "one side, return null for that field. Do not infer home, school, or work "
                    "unless the user explicitly mentions them."
                ),
            },
            {"role": "user", "content": user_text},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "route_location_extraction",
                "strict": True,
                "schema": ROUTE_EXTRACTION_SCHEMA,
            }
        },
        "max_output_tokens": 300,
    }

    raw = _post_openai(api_key, payload)
    if raw is None:
        return None

    text = _response_text(raw)
    if not text:
        return None

    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None

    return RouteLocationHints(
        origin_text=_clean_location_hint(data.get("origin_text")),
        destination_text=_clean_location_hint(data.get("destination_text")),
        source="llm",
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


def _first_location_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        cleaned = _clean_location_hint(match.group(1) if match else None)
        if cleaned:
            return cleaned
    return None


def _known_destination_hint(text: str) -> str | None:
    normalized = _normalize_location_text(text)
    if re.search(r"home|집(에|으로|까지|가야|갈|가기|가려고|도착)", text, flags=re.IGNORECASE):
        return "집"
    if "회사로" in normalized or "회사까지" in normalized:
        return "회사"
    if "학교로" in normalized or "학교까지" in normalized:
        return "학교"
    return None


def _clean_location_hint(value) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = re.sub(r"^(오늘|내일|지금|일단|그리고|나는|제가|저는|i)\s+", "", value.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(에서|부터|으로|로|까지|에)$", "", cleaned)
    cleaned = re.sub(r"\s*(가야|갈|가기|가려고|도착|출발|시작).*$", "", cleaned)
    cleaned = cleaned.strip()

    if len(cleaned) < 2:
        return None

    return cleaned


def _normalize_location_text(value: str) -> str:
    return value.lower().replace(" ", "")

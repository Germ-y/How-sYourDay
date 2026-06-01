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
            r"([^,.;\n]+?)(?:에서|부터)\s+[^,.;\n]+?\s*(?:가고\s*싶|가야|갈|가기|가려고|도착|이동|가서)",
        ],
    )
    destination = (
        _known_destination_hint(text)
        or _specific_commitment_destination_hint(text)
        or _destination_before_origin_hint(text)
        or _first_location_match(
        text,
        [
            r"(?:도착지|목적지)\s*(?:는|은|:)?\s*([^,.;\n]+?)(?=\s*(?:이고|이고요|,|\.|;|$))",
            r"(?:to|get to|go to|going to|head to)\s+([^,.;\n]+?)(?=\s+(?:by|before|after|and|then)|[,.;]|$)",
            r"(?:에서|부터)\s*([^,.;\n]+?)(?:까지|으로|로)(?=\s|,|\.|;|$)",
            r"(?:에서|부터)\s*([^,.;\n]+?)\s*(?:가고\s*싶|가야|갈|가기|가려고|도착|이동|가서)",
            r"([^,.;\n]+?)(?:으로|로|까지)\s*(?:가야|갈|가기|가려고|이동|도착|가고|가자|$)",
            r"([^,.;\n]+?)(?:에)\s*(?:가야|갈|가기|가려고|도착)",
        ],
        )
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
                    "You extract route origin and destination from casual Korean or English "
                    "travel requests. Return only the place text, not coordinates, addresses, "
                    "times, emotions, weather, tasks, or reasons. Preserve the user's place "
                    "names as written, but remove filler words such as '나', '오늘', '가고 싶어', "
                    "'날씨 선선해서', '조금 걸을까', and '커피 한잔하게'. "
                    "\n\nRules:\n"
                    "- origin_text is the place after markers like '에서', '부터', '출발', "
                    "'starting from', or the current starting location the user names.\n"
                    "- destination_text is the place after/before markers like '까지', '로', "
                    "'으로', '가고 싶어', '가야 해', '도착', 'to', or the main place the user "
                    "wants to visit.\n"
                    "- If the destination is mentioned before the origin, still extract both. "
                    "Example: '나 홍대까지 가고 싶어 오목교역에서 날씨 선선해서 홍대 주변 좀 "
                    "걸을까 해' => origin_text='오목교역', destination_text='홍대'.\n"
                    "- If a destination is repeated with extra context like '홍대 주변', choose "
                    "the core destination '홍대' unless the surrounding place is clearly the target.\n"
                    "- If the user names a broad area first and later names a specific committed "
                    "appointment or task location, use the specific final place as destination. "
                    "Example: '오목교역에서 출발해서 홍대까지 갈거야. 홍대 가서 카페에서 "
                    "과제하다가 숯림 식당이라는 식당에서 3시에 친구 보기로 했어' => "
                    "origin_text='오목교역', destination_text='숯림 식당'.\n"
                    "- If only one side is clearly present, return null for the missing side. "
                    "Do not invent home, school, work, or current location unless explicitly written.\n"
                    "- Return JSON matching the schema exactly."
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


def _specific_commitment_destination_hint(text: str) -> str | None:
    patterns = [
        r"([가-힣A-Za-z0-9\s]+?)(?:이라는|라는)\s*(?:식당|카페|장소|곳)?에서\s*(?:\d{1,2}시|친구|약속|보기|만나)",
        r"([가-힣A-Za-z0-9\s]+?(?:식당|카페|역|학교|병원|도서관|공원))에서\s*(?:\d{1,2}시|친구|약속|보기|만나)",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        for value in reversed(matches):
            candidate = re.split(r"(?:하다가|가서|그리고|,|\.|;)", value)[-1]
            cleaned = _clean_location_hint(candidate)
            if cleaned:
                return cleaned
    return None


def _destination_before_origin_hint(text: str) -> str | None:
    match = re.search(
        r"(.+?)(?:까지|으로|로)\s*(?:가고\s*싶|가야|갈|가기|가려고|도착|이동)",
        text,
        flags=re.IGNORECASE,
    )
    return _clean_location_hint(match.group(1) if match else None)


def _clean_location_hint(value) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    cleaned = re.sub(r"^.*(?:가고\s*싶어|가고싶어|싶어)\s+", "", cleaned)
    cleaned = re.sub(r"^(오늘|내일|지금|일단|그리고|나는|나|제가|저는|i)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(가야|갈|가기|가려고|도착|출발|시작).*$", "", cleaned)
    cleaned = re.sub(r"\s*(에서|부터|으로|로|까지|에)$", "", cleaned)
    cleaned = cleaned.strip()

    if len(cleaned) < 2:
        return None

    return cleaned


def _normalize_location_text(value: str) -> str:
    return value.lower().replace(" ", "")

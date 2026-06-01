from functools import lru_cache
from pathlib import Path
from datetime import datetime, timedelta, timezone


PROMPT_ROOT = Path(__file__).resolve().parents[1] / "prompts"
KST = timezone(timedelta(hours=9), name="KST")


@lru_cache(maxsize=16)
def load_prompt(name: str) -> str:
    if "/" in name or "\\" in name or name.startswith("."):
        raise ValueError("Prompt name must be a plain file stem")

    path = PROMPT_ROOT / f"{name}.txt"
    return path.read_text(encoding="utf-8").strip()


def kst_runtime_context() -> str:
    now = datetime.now(KST)
    return "\n".join(
        [
            "Runtime Context",
            "Timezone: Asia/Seoul (KST, UTC+09:00)",
            f"Current KST datetime: {now:%Y-%m-%d %H:%M:%S}",
            f"Current KST weekday: {now:%A}",
            "Use this time context for relative words such as now, today, tonight, tomorrow, after work, before class, and clock times.",
            "This runtime context is not a user-provided place. Do not extract it as origin_text or destination_text.",
        ]
    )

from functools import lru_cache
from pathlib import Path


PROMPT_ROOT = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=16)
def load_prompt(name: str) -> str:
    if "/" in name or "\\" in name or name.startswith("."):
        raise ValueError("Prompt name must be a plain file stem")

    path = PROMPT_ROOT / f"{name}.txt"
    return path.read_text(encoding="utf-8").strip()

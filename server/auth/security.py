from datetime import datetime, timedelta, timezone
import os
from pathlib import Path

import bcrypt
from jose import JWTError, jwt


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
DEFAULT_SECRET_KEY = "hows-your-day-dev-secret-change-me"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, _jwt_secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, _jwt_secret_key(), algorithms=[ALGORITHM])
    except JWTError:
        return None

    subject = payload.get("sub")
    return subject if isinstance(subject, str) and subject else None


def _jwt_secret_key() -> str:
    return (
        os.environ.get("JWT_SECRET_KEY")
        or _env_file_value("JWT_SECRET_KEY")
        or DEFAULT_SECRET_KEY
    )


def _env_file_value(name: str) -> str | None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        if key.strip().lstrip("\ufeff") == name:
            cleaned = raw_value.strip().strip('"').strip("'")
            return cleaned or None
    return None

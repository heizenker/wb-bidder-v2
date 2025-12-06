from __future__ import annotations

import os
from typing import Final

"""Authorization helpers for the Wildberries API."""

ENV_PATH: Final[str] = ".env"
TOKEN_VAR_NAME: Final[str] = "WB_TOKEN"
API_BASE_URL_VAR_NAME: Final[str] = "WB_API_V2_BASE_URL"
DEFAULT_API_BASE_URL: Final[str] = "http://127.0.0.1:8002"


class TokenNotFoundError(RuntimeError):
    """Raised when WB_TOKEN cannot be loaded from .env or environment."""

    pass


def load_token(
    env_path: str = ENV_PATH,
    var_name: str = TOKEN_VAR_NAME,
) -> str:
    """
    Load WB API token from .env or environment.

    ВАЖНО:
    - Поведение должно остаться таким же, как у старой реализации.
    - Если раньше поднимался RuntimeError с конкретным текстом, сохраняем тот же текст.
    - Приоритет чтения (.env vs переменные окружения) оставляем тем же.
    """
    if not os.path.exists(env_path):
        raise TokenNotFoundError(".env не найден в /opt/wb-bidder")

    token: str | None = None
    with open(env_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(f"{var_name}="):
                token = line.split("=", 1)[1].strip()
                # Убираем кавычки, если они есть
                if token.startswith('"') and token.endswith('"'):
                    token = token[1:-1]
                elif token.startswith("'") and token.endswith("'"):
                    token = token[1:-1]
                break

    if not token:
        raise TokenNotFoundError("WB_TOKEN не найден в .env")

    return token


def load_api_base_url(
    env_path: str = ENV_PATH,
    var_name: str = API_BASE_URL_VAR_NAME,
    default: str = DEFAULT_API_BASE_URL,
) -> str:
    """
    Load backend_v2 base URL from .env. Falls back to DEFAULT_API_BASE_URL.
    """
    if not os.path.exists(env_path):
        return default

    value: str | None = None
    with open(env_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(f"{var_name}="):
                value = line.split("=", 1)[1].strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                break

    return value or default


def build_headers(token: str) -> dict[str, str]:
    """Prepare authorization headers."""
    return {"Authorization": token}


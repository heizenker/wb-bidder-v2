from __future__ import annotations

"""
Placeholder for bidder configuration.

The current working config still lives in `config.py` at project root.
Later we will migrate all configuration data into this module.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Temporary stub constants to make imports safe.

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTROLLED_ITEMS_FILE = PROJECT_ROOT / "controlled_items.json"


def _load_controlled_items() -> list[dict]:
    """
    Загрузить список контролируемых товаров из controlled_items.json.
    
    Если файл не существует или повреждён, возвращает пустой список.
    Логирует короткое сообщение (без токенов и приватных данных).
    """
    if not CONTROLLED_ITEMS_FILE.exists():
        logger.info(f"controlled_items.json не найден: {CONTROLLED_ITEMS_FILE}")
        return []

    try:
        with CONTROLLED_ITEMS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"Ошибка при загрузке controlled_items.json: {e}")
        return []

    if not isinstance(data, list):
        logger.warning(f"controlled_items.json должен содержать список, получен {type(data)}")
        return []

    # Оставляем только словари
    valid_items = [item for item in data if isinstance(item, dict)]
    logger.info(f"Загружено {len(valid_items)} контролируемых товаров из controlled_items.json")
    return valid_items


CONTROLLED_ITEMS: list[dict] = _load_controlled_items()
CHECK_INTERVAL_SEC: int | None = None


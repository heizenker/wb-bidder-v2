from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Final

# Временно тянем TIME_SHIFT_HOURS из старого config.py,
# чтобы не ломать текущий код. Позже перенесём это в новый config.
try:
    from config import TIME_SHIFT_HOURS  # type: ignore
except Exception:
    TIME_SHIFT_HOURS: Final[int] = 3  # безопасный дефолт, если что-то пойдёт не так


def now_shifted(hours: int | None = None) -> datetime:
    """
    Текущее время с учётом сдвига TIME_SHIFT_HOURS.

    Если hours не None — используем его вместо TIME_SHIFT_HOURS.
    """
    shift = TIME_SHIFT_HOURS if hours is None else hours
    # считаем, что вся логика WB относительно UTC, поэтому берём now(timezone.utc)
    return datetime.now(timezone.utc) + timedelta(hours=shift)


def today_date_str(hours: int | None = None) -> str:
    """
    Дата для запросов к WB в формате YYYY-MM-DD, с учётом сдвига.

    Пока только хелпер — существующий код, который формирует даты,
    НЕ трогаем.
    """
    return now_shifted(hours).strftime("%Y-%m-%d")


from __future__ import annotations

from datetime import datetime, timedelta, timezone, date
from typing import Any, Dict, List


def build_sales_funnel_request(
    nm_ids: List[int],
    days: int = 30,
    end_date: date | None = None,
) -> Dict[str, Any]:
    """
    Формирует корректный payload для /api/analytics/v3/sales-funnel/products
    строго по схеме ProductsRequest.

    - selectedPeriod и pastPeriod одной длины.
    - Формат дат: YYYY-MM-DD (без времени и таймзоны).
    - nmIds — список товаров.
    - limit/offset заданы явно.
    """

    # Ориентируемся либо на end_date из аргумента, либо на сегодняшний день.
    if end_date is not None:
        today = end_date
    else:
        today = datetime.now(timezone.utc).date()

    selected_end = today
    selected_start = today - timedelta(days=days)

    # Длина периода (в днях)
    period_delta = selected_end - selected_start

    # Прошлый период той же длины, сразу перед текущим
    past_end = selected_start - timedelta(days=1)
    past_start = past_end - period_delta

    nm_ids_clean = [int(x) for x in nm_ids] if nm_ids else []

    payload = {
        "selectedPeriod": {
            "start": selected_start.isoformat(),
            "end": selected_end.isoformat(),
        },
        "pastPeriod": {
            "start": past_start.isoformat(),
            "end": past_end.isoformat(),
        },
        "nmIds": nm_ids_clean,
        "brandNames": [],
        "subjectIds": [],
        "tagIds": [],
        "skipDeletedNm": False,
        "orderBy": {
            "field": "openCard",
            "mode": "desc",
        },
        "limit": 1000,
        "offset": 0,
    }

    if nm_ids_clean:
        payload["nmIds"] = nm_ids_clean

    return payload


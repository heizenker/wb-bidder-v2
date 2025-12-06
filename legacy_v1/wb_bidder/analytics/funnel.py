from __future__ import annotations

from typing import Any, Dict, Iterable, List
from collections import defaultdict


class FunnelAnalyzer:
    """
    Универсальный анализатор воронки для рекламных данных.
    На вход принимает список строк (dict) со статистикой по дням/рекламам,
    как возвращает AdsCollector.
    """

    def aggregate_by_campaign(self, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Агрегировать по рекламной кампании (advertId).

        rows — список словарей вида:
        {
            "advertId": ...,
            "date": "YYYY-MM-DD",
            "views": ...,
            "clicks": ...,
            "spend": ...,
            "orders": ...,
            "cr": ...,
            "cpo": ...,
        }
        """

        agg = defaultdict(lambda: {"views": 0, "clicks": 0, "spend": 0.0, "orders": 0})

        for r in rows:
            aid = r.get("advertId")
            if aid is None:
                continue

            a = agg[aid]
            a["views"] += r.get("views", 0)
            a["clicks"] += r.get("clicks", 0)
            a["spend"] += r.get("spend", 0.0)
            a["orders"] += r.get("orders", 0)

        result: List[Dict[str, Any]] = []

        for aid, data in agg.items():
            views = data["views"]
            clicks = data["clicks"]
            orders = data["orders"]
            spend = data["spend"]

            row = {
                "advertId": aid,
                "views": views,
                "clicks": clicks,
                "spend": spend,
                "orders": orders,
                "ctr": (clicks / views * 100) if views > 0 else 0.0,
                "cr": (orders / clicks * 100) if clicks > 0 else 0.0,
                "cpo": (spend / orders) if orders > 0 else None,
                "roas": (orders * 100 / spend) if spend > 0 else None,
            }

            result.append(row)

        return result


# Мини-тест
if __name__ == "__main__":
    sample = [
        {"advertId": 111, "views": 1000, "clicks": 20, "orders": 3, "spend": 150},
        {"advertId": 111, "views": 700, "clicks": 10, "orders": 2, "spend": 90},
        {"advertId": 222, "views": 1500, "clicks": 25, "orders": 4, "spend": 200},
    ]

    f = FunnelAnalyzer()
    out = f.aggregate_by_campaign(sample)
    print(out)

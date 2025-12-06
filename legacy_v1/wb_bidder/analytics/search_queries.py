from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
from collections import defaultdict


# --- helpers ---------------------------------------------------------------


def _to_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).replace(" ", "").replace(",", ".")
    try:
        return int(float(s))
    except:
        return 0


def _to_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0


def _get(row: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in row:
            return row[k]
    return default


# --- структура метрик по запросу -------------------------------------------


@dataclass
class SearchQueryStats:
    """
    Метрики по одному поисковому запросу для одного артикула:

    - показы
    - клики
    - траты рекламы
    - конверсия
    - средняя позиция
    """

    article_id: int
    query: str

    impressions: int
    clicks: int
    spend: float
    orders: int
    revenue: float

    avg_position: float

    def ctr(self) -> float:
        if self.impressions <= 0:
            return 0.0
        return self.clicks * 100.0 / float(self.impressions)

    def cpc(self) -> float:
        if self.clicks <= 0:
            return 0.0
        return self.spend / float(self.clicks)

    def cpo(self) -> float:
        if self.orders <= 0:
            return 0.0
        return self.spend / float(self.orders)

    def roas(self) -> float:
        if self.spend <= 0:
            return 0.0
        return self.revenue / float(self.spend)


# --- агрегатор --------------------------------------------------------------


def aggregate_search_queries(rows: Iterable[Dict[str, Any]]) -> List[SearchQueryStats]:
    """
    Превращает строки отчёта о5675 (поисковые запросы) в агрегированные данные.

    В отчёте обычно есть столбцы:
    - Артикул WB / nmId
    - Поисковый запрос
    - Показы
    - Клики
    - Расход
    - Заказы
    - Выручка
    - Средняя позиция показа / avg_position

    Мы аккуратно поддерживаем и русские, и английские варианты колонок.
    """

    acc: dict[tuple[int, str], Dict[str, Any]] = defaultdict(
        lambda: {
            "impressions": 0,
            "clicks": 0,
            "spend": 0.0,
            "orders": 0,
            "revenue": 0.0,
            "avg_pos_sum": 0.0,
            "avg_pos_count": 0,
        }
    )

    for row in rows:
        article_raw = _get(row, "nmId", "article_id", "Артикул WB")
        article_id = _to_int(article_raw)
        if article_id <= 0:
            continue

        query = _get(row, "query", "Поисковый запрос", "Запрос")
        if not query:
            continue
        query = str(query).strip()

        key = (article_id, query)
        b = acc[key]

        b["impressions"] += _to_int(_get(row, "impressions", "Показы"))
        b["clicks"] += _to_int(_get(row, "clicks", "Клики"))
        b["spend"] += _to_float(_get(row, "spend", "Расход", "Траты"))
        b["orders"] += _to_int(_get(row, "orders", "Заказы"))
        b["revenue"] += _to_float(_get(row, "revenue", "Выручка"))

        pos = _get(row, "avg_position", "Средняя позиция")
        if pos not in (None, ""):
            b["avg_pos_sum"] += _to_float(pos)
            b["avg_pos_count"] += 1

    out: List[SearchQueryStats] = []

    for (article_id, query), b in acc.items():
        if b["avg_pos_count"] > 0:
            avg_pos = b["avg_pos_sum"] / float(b["avg_pos_count"])
        else:
            avg_pos = 0.0

        out.append(
            SearchQueryStats(
                article_id=article_id,
                query=query,
                impressions=b["impressions"],
                clicks=b["clicks"],
                spend=b["spend"],
                orders=b["orders"],
                revenue=b["revenue"],
                avg_position=avg_pos,
            )
        )

    # сортировка для удобства: по расходу и показам
    out.sort(key=lambda x: (-x.spend, -x.impressions))
    return out


if __name__ == "__main__":
    sample = [
        {
            "Артикул WB": 265104282,
            "Поисковый запрос": "носки мужские теплые",
            "Показы": 10000,
            "Клики": 250,
            "Расход": 1800,
            "Заказы": 12,
            "Выручка": 15000,
            "Средняя позиция": 8.4,
        }
    ]

    stats = aggregate_search_queries(sample)
    for s in stats:
        print(s)
        print("CTR=", s.ctr(), "CPC=", s.cpc(), "CPO=", s.cpo(), "ROAS=", s.roas())



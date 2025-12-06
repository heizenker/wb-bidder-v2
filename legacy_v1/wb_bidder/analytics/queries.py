from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Tuple

from wb_bidder.core.stats_utils import read_stats_raw

NUM_FIELDS = ("clicks", "impressions", "orders", "cost", "revenue")


def _to_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(round(float(str(value).replace(",", "."))))
    except ValueError:
        return 0


def _to_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return 0.0


@dataclass
class QueryStats:
    """
    Агрегированная статистика по одной паре (advert_id, query)
    за некоторый период (обычно несколько дней).

    Все "сырые" значения целочисленные/вещественные,
    а показатели воронки считаются через свойства.
    """

    advert_id: int
    query: str

    clicks: int = 0
    impressions: int = 0
    orders: int = 0
    cost: float = 0.0
    revenue: float = 0.0

    def ctr(self) -> float:
        """CTR = клики / показы."""
        if self.impressions <= 0:
            return 0.0
        return self.clicks / float(self.impressions)

    def cr(self) -> float:
        """Конверсия = заказы / клики."""
        if self.clicks <= 0:
            return 0.0
        return self.orders / float(self.clicks)

    def cpo(self) -> float:
        """CPO = расходы / заказы."""
        if self.orders <= 0:
            return 0.0
        return self.cost / float(self.orders)

    def roas(self) -> float:
        """ROAS = выручка / расходы."""
        if self.cost <= 0:
            return 0.0
        return self.revenue / float(self.cost)


def aggregate_query_stats(rows: Iterable[Dict[str, Any]]) -> List[QueryStats]:
    """
    Сгруппировать сырые строки stats.csv по (advert_id, query)
    и вернуть список QueryStats.

    rows — это обычно результат read_stats_raw(), возможно отфильтрованный по датам.
    """
    aggregated: Dict[Tuple[int, str], QueryStats] = {}

    for row in rows:
        advert_raw = row.get("advert_id", "") or "0"
        try:
            advert_id = int(str(advert_raw))
        except ValueError:
            advert_id = 0

        query = (row.get("query") or "").strip()

        key = (advert_id, query)
        if key not in aggregated:
            aggregated[key] = QueryStats(
                advert_id=advert_id,
                query=query,
            )

        agg = aggregated[key]
        agg.clicks += _to_int(row.get("clicks"))
        agg.impressions += _to_int(row.get("impressions"))
        agg.orders += _to_int(row.get("orders"))
        agg.cost += _to_float(row.get("cost"))
        agg.revenue += _to_float(row.get("revenue"))

    # Возвращаем отсортированный список: сначала по advert_id, потом по убыванию заказов
    result = list(aggregated.values())
    result.sort(key=lambda qs: (qs.advert_id, -qs.orders, -qs.clicks))
    return result


def _parse_date(value: str) -> date:
    """
    Парсим дату из stats.csv. Ожидаем формат YYYY-MM-DD,
    но стараемся быть максимально толерантными.
    """
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except Exception:
            continue
    # если не получилось — считаем, что это "сегодня", чтобы не выкидывать строку
    return date.today()


def load_query_stats_for_last_days(days: int) -> List[QueryStats]:
    """
    Удобный хелпер: загружает stats.csv, фильтрует строки за последние N дней
    и возвращает агрегированную статистику по запросам.

    Ничего не пишет в файлы, только читает.
    """
    raw = read_stats_raw()
    if not raw:
        return []

    today = date.today()
    threshold = today - timedelta(days=days)

    window_rows: List[Dict[str, Any]] = []
    for row in raw:
        row_date = _parse_date(row.get("date", ""))
        if row_date >= threshold:
            window_rows.append(row)

    return aggregate_query_stats(window_rows)


def top_queries_by_orders(
    stats: Iterable[QueryStats],
    min_clicks: int = 10,
    min_orders: int = 1,
    limit: int = 50,
) -> List[QueryStats]:
    """
    Отфильтровать и отсортировать список QueryStats по количеству заказов
    (для поиска "топовых" запросов).

    - min_clicks / min_orders — фильтры по минимальному трафику.
    - limit — максимальное количество элементов в результатах.
    """
    filtered: List[QueryStats] = []
    for qs in stats:
        if qs.clicks < min_clicks:
            continue
        if qs.orders < min_orders:
            continue
        filtered.append(qs)

    filtered.sort(key=lambda qs: (-qs.orders, -qs.clicks))
    return filtered[:limit]

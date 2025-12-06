from __future__ import annotations

import csv
from typing import List

from wb_bidder.analytics.queries import (
    QueryStats,
    load_query_stats_for_last_days,
    top_queries_by_orders,
)


def export_queries_to_csv(
    days: int,
    output_path: str,
    min_clicks: int = 10,
    min_orders: int = 1,
    limit: int = 200,
) -> None:
    """
    Выгружает топовые запросы за последние days дней в CSV-файл.

    Столбцы:
    - advert_id
    - query
    - clicks
    - impressions
    - orders
    - cost
    - revenue
    - ctr
    - cr
    - cpo
    - roas
    """
    all_stats: List[QueryStats] = load_query_stats_for_last_days(days)
    if not all_stats:
        print("Нет данных в stats.csv")
        return

    top = top_queries_by_orders(
        all_stats,
        min_clicks=min_clicks,
        min_orders=min_orders,
        limit=limit,
    )

    if not top:
        print("Нет запросов, удовлетворяющих фильтрам.")
        return

    fieldnames = [
        "advert_id",
        "query",
        "clicks",
        "impressions",
        "orders",
        "cost",
        "revenue",
        "ctr",
        "cr",
        "cpo",
        "roas",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()

        for q in top:
            row = {
                "advert_id": q.advert_id,
                "query": q.query,
                "clicks": q.clicks,
                "impressions": q.impressions,
                "orders": q.orders,
                "cost": f"{q.cost:.2f}",
                "revenue": f"{q.revenue:.2f}",
                "ctr": f"{q.ctr() * 100:.2f}",
                "cr": f"{q.cr() * 100:.2f}",
                "cpo": f"{q.cpo():.2f}",
                "roas": f"{q.roas():.2f}",
            }
            writer.writerow(row)

    print(f"Экспорт завершён. Файл: {output_path}")


def main() -> None:
    DAYS = 7  # период по умолчанию
    OUTPUT = "queries_export.csv"

    print(
        f"Экспорт запросов за последние {DAYS} дней "
        f"в файл {OUTPUT!r}"
    )

    export_queries_to_csv(
        days=DAYS,
        output_path=OUTPUT,
        min_clicks=10,
        min_orders=1,
        limit=200,
    )


if __name__ == "__main__":
    main()


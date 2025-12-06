from __future__ import annotations

from typing import List

from wb_bidder.analytics.queries import (
    QueryStats,
    load_query_stats_for_last_days,
    top_queries_by_orders,
)


def print_query_row(q: QueryStats) -> None:
    """
    Красивый вывод строки статистики по запросу.
    """
    ctr = q.ctr() * 100
    cr = q.cr() * 100
    roas = q.roas()
    cpo = q.cpo()

    print(
        f"{q.advert_id:<10} | {q.query:<40} | "
        f"клики {q.clicks:<6} | показы {q.impressions:<7} | "
        f"заказы {q.orders:<4} | "
        f"CTR {ctr:5.1f}% | CR {cr:5.1f}% | "
        f"CPO {cpo:7.1f} | ROAS {roas:5.2f}"
    )


def main() -> None:
    DAYS = 7  # <-- можно менять

    print(f"\nАналитика запросов за последние {DAYS} дней")
    print("-" * 100)

    all_stats: List[QueryStats] = load_query_stats_for_last_days(DAYS)
    if not all_stats:
        print("Нет данных в stats.csv")
        return

    top = top_queries_by_orders(
        all_stats,
        min_clicks=10,
        min_orders=1,
        limit=50,
    )

    if not top:
        print("Запросов с достаточным трафиком нет.")
        return

    for q in top:
        print_query_row(q)


if __name__ == "__main__":
    main()


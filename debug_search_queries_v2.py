from __future__ import annotations

from pprint import pprint

from wb_bidder_v2.collectors_v2.search_queries_collector import (
    SearchQueriesCollectorV2,
)


def main() -> None:
    collector = SearchQueriesCollectorV2()
    rows = collector.collect(days=7)

    print(f"Всего записей: {len(rows)}")
    print("--- Первые 3 записи ---")
    for row in rows[:3]:
        pprint(row)
        print("-----------------------")


if __name__ == "__main__":
    main()


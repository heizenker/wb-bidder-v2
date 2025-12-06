from __future__ import annotations

import sys
from pprint import pprint

from wb_bidder_v2.collectors_v2.sales_funnel_collector import (
    SalesFunnelCollectorV2,
)


def main() -> None:
    if len(sys.argv) > 1:
        nm_ids = [int(sys.argv[1])]
    else:
        nm_ids = None

    print(f"Используем nm_ids: {nm_ids}")

    collector = SalesFunnelCollectorV2()
    rows = collector.collect(days=7, nm_ids=nm_ids)

    print(f"Всего записей: {len(rows)}")
    print("--- Первые 3 записи ---")
    for row in rows[:3]:
        pprint(row)
        print("-----------------------")


if __name__ == "__main__":
    main()


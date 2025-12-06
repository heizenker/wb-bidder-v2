from __future__ import annotations

import datetime
from pprint import pprint

from wb_bidder_v2.collectors_v2.sales_funnel_collector import SalesFunnelCollectorV2


def main() -> None:
    today = datetime.date.today()
    date_to = today
    date_from = today - datetime.timedelta(days=7)

    print(f"Период: {date_from} → {date_to}")
    print("Запрашиваем ВСЕ товары (nm_ids=None)...")

    collector = SalesFunnelCollectorV2.from_env()
    rows = collector.fetch_sales_funnel(
        date_from=date_from,
        date_to=date_to,
        nm_ids=None,
    )

    print(f"Всего записей: {len(rows)}")
    print("--- Первые 5 записей ---")
    for row in rows[:5]:
        nm_id = row.get("item_id") or row.get("nm_id") or row.get("nmId")
        print("nmId:", nm_id)
        pprint(row)
        print("-----------------------")


if __name__ == "__main__":
    main()


from __future__ import annotations

from wb_bidder_v2.analytics.search_funnel_joiner_v2 import (
    join_search_and_funnel,
)
from wb_bidder_v2.collectors_v2.sales_funnel_collector import (
    SalesFunnelCollectorV2,
)
from wb_bidder_v2.collectors_v2.search_queries_collector import (
    SearchQueriesCollectorV2,
)


def main() -> None:
    search_rows = SearchQueriesCollectorV2().collect(days=7)
    funnel_rows = SalesFunnelCollectorV2().collect(days=7)

    joined = join_search_and_funnel(search_rows, funnel_rows)

    print(f"Всего уникальных nm_id: {len(joined)}")
    print("--- Первые 3 nm_id ---")
    for nm_id in list(joined.keys())[:3]:
        bucket = joined[nm_id]
        search_len = len(bucket.get("search", []))
        funnel_len = len(bucket.get("funnel", []))
        print(f"nm_id={nm_id}: search={search_len}, funnel={funnel_len}")


if __name__ == "__main__":
    main()


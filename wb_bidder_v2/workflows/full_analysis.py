from __future__ import annotations

import datetime as dt
import logging
from typing import Dict, List, Any

from wb_bidder_v2.collectors_v2.ads_collector import AdsCollectorV2
from wb_bidder_v2.collectors_v2.sales_funnel_collector import SalesFunnelCollectorV2
from wb_bidder_v2.collectors_v2.search_queries_collector import SearchQueriesCollectorV2
from wb_bidder_v2.analytics.analytics_v2 import CombinedAnalyzerV2
from wb_bidder_v2.analytics.sales_funnel import aggregate_sales_funnel
from wb_bidder_v2.analytics.search_queries import aggregate_search_queries
from wb_bidder_v2.analytics.combined_cpo_analysis import CombinedAnalyzer
from wb_bidder_v2.workflows.utils import (
    bootstrap_state_from_campaigns,
    collect_full_cycle,
    get_controlled_campaign_ids,
    get_controlled_nm_ids,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def refresh_and_collect(
    date_from: dt.date,
    date_to: dt.date,
) -> Dict[str, Any]:
    bootstrap_state_from_campaigns()
    collect_full_cycle(date_from=date_from, date_to=date_to)

    campaign_ids = get_controlled_campaign_ids()
    nm_ids = get_controlled_nm_ids()

    ads = AdsCollectorV2.from_env().fetch_ads(
        date_from=date_from,
        date_to=date_to,
        campaign_ids=campaign_ids,
        nm_ids=nm_ids,
        placement=None,
    )
    funnel = SalesFunnelCollectorV2.from_env().fetch_sales_funnel(
        date_from=date_from,
        date_to=date_to,
        nm_ids=nm_ids,
    )
    queries = SearchQueriesCollectorV2.from_env().fetch_search_queries(
        date_from=date_from,
        date_to=date_to,
        nm_ids=nm_ids,
        queries=None,
    )
    return {
        "ads": ads,
        "funnel": funnel,
        "queries": queries,
        "campaign_ids": campaign_ids,
        "nm_ids": nm_ids,
    }


def build_report_block(combined_stats: List[Any]) -> str:
    lines = []
    for stat in combined_stats:
        line = (
            f"nmId={stat.article_id} | "
            f"ads: views={stat.ads_views}, clicks={stat.ads_clicks}, "
            f"orders={stat.ads_orders}, spend={stat.ads_spend:.2f}, "
            f"CPC={stat.ads_cpc():.2f}, CPO={stat.ads_cpo():.2f}"
        )
        if stat.funnel:
            line += (
                f" | funnel: views={stat.funnel.views}, "
                f"cart={stat.funnel.cart_adds}, orders={stat.funnel.orders}, "
                f"buyouts={stat.funnel.buyouts}"
            )
        lines.append(line)
    return "\n".join(lines)


def run_full_analysis(days: int = 7) -> None:
    date_to = dt.date.today()
    date_from = date_to - dt.timedelta(days=days - 1)
    logger.info("Full analysis window: %s -> %s", date_from, date_to)

    payload = refresh_and_collect(date_from, date_to)
    ads = payload["ads"]
    funnel = payload["funnel"]
    queries = payload["queries"]
    nm_ids = payload["nm_ids"] or None

    logger.info("Loaded rows: ads=%s, funnel=%s, queries=%s", len(ads), len(funnel), len(queries))

    analyzer = CombinedAnalyzerV2(
        ads_source=ads,
        queries_source=queries,
        funnel_source=funnel,
    )
    report = analyzer.build_report()

    funnel_stats = aggregate_sales_funnel(funnel)
    query_stats = aggregate_search_queries(queries)
    article_stats = CombinedAnalyzer(
        funnel_stats=funnel_stats,
        query_stats=query_stats,
        ads_rows=ads,
    ).build()

    print("=== Combined metrics by nmId ===")
    for nm_id, sections in report.items():
        ads_agg = sections["ads"]["agg"]
        print(
            f"nmId={nm_id} | views={ads_agg['impressions']} "
            f"| clicks={ads_agg['clicks']} | orders={ads_agg['orders']} "
            f"| spend={ads_agg['spend']:.2f} | cpo={ads_agg['cpo']:.2f}"
        )

    print("\n=== Article breakdown ===")
    print(build_report_block(article_stats))


def main() -> None:
    run_full_analysis()


if __name__ == "__main__":
    main()


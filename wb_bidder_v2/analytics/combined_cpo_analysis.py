from __future__ import annotations



import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Mapping

from wb_bidder_v2.analytics.sales_funnel import SalesFunnelStats
from wb_bidder_v2.analytics.search_queries import SearchQueryStats
from wb_bidder_v2.adapters.state_store import lookup_nm_by_campaign

logger = logging.getLogger(__name__)





@dataclass

class CombinedArticleStats:

    article_id: int



    funnel: Optional[SalesFunnelStats]

    queries: List[SearchQueryStats]



    ads_views: int

    ads_clicks: int

    ads_spend: float

    ads_orders: int



    def ads_ctr(self) -> float:

        if self.ads_views <= 0:

            return 0.0

        return self.ads_clicks * 100.0 / float(self.ads_views)



    def ads_cpc(self) -> float:

        if self.ads_clicks <= 0:

            return 0.0

        return self.ads_spend / float(self.ads_clicks)



    def ads_cpo(self) -> float:

        if self.ads_orders <= 0:

            return 0.0

        return self.ads_spend / float(self.ads_orders)



    def blended_roas(self) -> float:

        if not self.funnel or self.ads_spend <= 0:

            return 0.0

        return self.funnel.revenue_buyouts / float(self.ads_spend)



    def funnel_summary(self) -> str:

        if not self.funnel:

            return "Нет данных воронки"

        f = self.funnel

        return (

            f"CTR={f.ctr():.2f}% | "

            f"CR_cart={f.cr_to_cart():.2f}% | "

            f"CR_order_clicks={f.cr_to_order_from_clicks():.2f}% | "

            f"Buyout={f.buyout_rate():.2f}% | "

            f"AOV={f.aov():.0f}₽"

        )





class CombinedAnalyzer:

    def __init__(

        self,
        funnel_stats: List[SalesFunnelStats],
        query_stats: List[SearchQueryStats],
        ads_rows: List[Dict[str, Any]],
        campaign_to_item: Mapping[Any, Any] | None = None,
    ):

        self.funnel_by_article = {f.article_id: f for f in funnel_stats}



        self.queries_by_article: Dict[int, List[SearchQueryStats]] = {}

        for q in query_stats:

            self.queries_by_article.setdefault(q.article_id, []).append(q)



        self.ads_by_article: Dict[int, Dict[str, Any]] = defaultdict(

            lambda: {"views": 0, "clicks": 0, "spend": 0.0, "orders": 0}

        )



        def resolve_nm(row: Dict[str, Any]) -> Optional[int]:
            nm_candidate = (
                row.get("nmId")
                or row.get("nm_id")
                or row.get("article_id")
                or row.get("nm")
            )
            if nm_candidate:
                try:
                    return int(nm_candidate)
                except (TypeError, ValueError):
                    pass

            campaign_id = (
                row.get("campaign_id")
                or row.get("campaignId")
                or row.get("advertId")
                or row.get("advert_id")
            )
            if campaign_to_item and campaign_id is not None:
                try:
                    nid = campaign_to_item.get(str(campaign_id)) or campaign_to_item.get(int(campaign_id))
                except (TypeError, ValueError):
                    nid = None
                if nid is not None:
                    try:
                        return int(nid)
                    except (TypeError, ValueError):
                        pass

            if campaign_id:
                lookup = lookup_nm_by_campaign(campaign_id)
                if lookup is not None:
                    return lookup

            return None

        for row in ads_rows:
            aid = resolve_nm(row)
            if aid is None:
                logger.warning("CombinedAnalyzer: skipping ads row without nmId")
                continue



            b = self.ads_by_article[aid]

            b["views"] += int(row.get("views", 0) or 0)

            b["clicks"] += int(row.get("clicks", 0) or 0)

            b["spend"] += float(row.get("spend", 0.0) or 0.0)

            b["orders"] += int(row.get("orders", 0) or 0)



    def build(self) -> List[CombinedArticleStats]:

        article_ids = (

            set(self.funnel_by_article.keys())

            | set(self.queries_by_article.keys())

            | set(self.ads_by_article.keys())

        )



        combined: List[CombinedArticleStats] = []



        for a in sorted(article_ids):

            funnel = self.funnel_by_article.get(a)

            queries = self.queries_by_article.get(a, [])

            ads = self.ads_by_article.get(a, {"views": 0, "clicks": 0, "spend": 0.0, "orders": 0})



            combined.append(

                CombinedArticleStats(

                    article_id=a,

                    funnel=funnel,

                    queries=queries,

                    ads_views=ads["views"],

                    ads_clicks=ads["clicks"],

                    ads_spend=ads["spend"],

                    ads_orders=ads["orders"],

                )

            )



        return combined



    def make_text_report(self, combined: List[CombinedArticleStats]) -> str:

        lines: List[str] = []



        for c in combined:

            lines.append(f"\n=== Артикул {c.article_id} ===")



            if c.funnel:

                lines.append("Воронка: " + c.funnel_summary())

            else:

                lines.append("Воронка: нет данных")



            lines.append(

                "Реклама: "

                f"CTR={c.ads_ctr():.2f}% | "

                f"CPC={c.ads_cpc():.2f}₽ | "

                f"CPO={c.ads_cpo():.2f}₽ | "

                f"Blended ROAS={c.blended_roas():.2f}"

            )



            lines.append(f"Поисковые запросы ({len(c.queries)} шт, топ-5):")

            for q in c.queries[:5]:

                lines.append(

                    f"  • {q.query} | "

                    f"импр={q.impressions} | клики={q.clicks} | заказы={q.orders} | "

                    f"CTR={q.ctr():.1f}% | CPO={q.cpo():.0f}₽ | ROAS={q.roas():.2f}"

                )



        return "\n".join(lines)


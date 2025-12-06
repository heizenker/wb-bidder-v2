from __future__ import annotations

from typing import Any, Dict, Iterable, List

from wb_bidder.collectors.ads_collector import AdsCollector
from wb_bidder.analytics.funnel import FunnelAnalyzer


class AdsReporter:
    """
    Единый интерфейс:
    1) собирает статистику по рекламным кампаниям через AdsCollector
    2) прогоняет её через FunnelAnalyzer
    3) возвращает итоговую агрегированную таблицу, готовую
       для аналитики, CPO, bidder и отчетов
    """

    def __init__(self, collector: AdsCollector | None = None):
        self.collector = collector or AdsCollector()
        self.funnel = FunnelAnalyzer()

    def report_campaigns(
        self,
        campaign_ids: Iterable[int],
        days: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает список строк вида:
        {
            "advertId": ...,
            "views": ...,
            "clicks": ...,
            "spend": ...,
            "orders": ...,
            "ctr": ...,
            "cr": ...,
            "cpo": ...,
            "roas": ...,
        }
        """

        raw_rows = self.collector.collect_campaign_stats(
            campaign_ids=campaign_ids,
            days=days,
        )

        agg = self.funnel.aggregate_by_campaign(raw_rows)
        return agg


# Мини-тест
if __name__ == "__main__":
    r = AdsReporter()
    client = r.collector.client

    campaigns = client.get_campaigns()
    ids = [c.get("advertId") or c.get("id") for c in campaigns][:5]

    print("CAMPAIGNS:", ids)

    out = r.report_campaigns(ids, days=3)
    for row in out:
        print(row)



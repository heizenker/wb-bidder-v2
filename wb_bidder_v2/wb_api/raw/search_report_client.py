from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence, Any

from wb_bidder_v2.wb_api.client import WildberriesClient
from wb_bidder_v2.adapters.storage.raw_store import save_raw

SEARCH_REPORT_URL = "https://seller-analytics-api.wildberries.ru/api/v2/search-report/report"


@dataclass
class SearchReportRawClient:
    client: WildberriesClient

    @classmethod
    def from_env(cls) -> "SearchReportRawClient":
        return cls(client=WildberriesClient.from_env())

    def fetch_search_report(
        self,
        *,
        nm_ids: Sequence[int],
        date_from: str,
        date_to: str,
        limit: int = 500,
        offset: int = 0,
    ) -> Any:
        from_dt = datetime.fromisoformat(date_from).date()
        to_dt = datetime.fromisoformat(date_to).date()
        period_days = (to_dt - from_dt).days + 1

        past_end = from_dt - timedelta(days=1)
        past_start = past_end - timedelta(days=period_days - 1)

        body = {
            "currentPeriod": {
                "start": date_from,
                "end": date_to,
            },
            "pastPeriod": {
                "start": past_start.strftime("%Y-%m-%d"),
                "end": past_end.strftime("%Y-%m-%d"),
            },
            "nmIds": list(nm_ids),
            "subjectIds": [],
            "brandNames": [],
            "tagIds": [],
            "positionCluster": "all",
            "includeSubstitutedSKUs": True,
            "includeSearchTexts": True,
            "limit": limit,
            "offset": offset,
            "orderBy": {
                "field": "orders",
                "mode": "desc",
            },
        }

        response = self.client.post(
            SEARCH_REPORT_URL,
            json=body,
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        save_raw("search_report", data)
        return data


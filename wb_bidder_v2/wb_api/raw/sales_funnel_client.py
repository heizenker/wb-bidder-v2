from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Any, Sequence

from wb_bidder_v2.wb_api.client import WildberriesClient
from wb_bidder_v2.core.sales_funnel_payload import build_sales_funnel_request
from wb_bidder_v2.adapters.storage.raw_store import save_raw

SALES_FUNNEL_URL = "https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products"


@dataclass
class SalesFunnelRawClient:
    client: WildberriesClient

    @classmethod
    def from_env(cls) -> "SalesFunnelRawClient":
        return cls(client=WildberriesClient.from_env())

    def fetch_sales_funnel(
        self,
        *,
        nm_ids: Sequence[int] | None,
        date_from: str,
        date_to: str,
    ) -> Any:
        start_dt = datetime.fromisoformat(date_from).date()
        end_dt = datetime.fromisoformat(date_to).date()
        days = (end_dt - start_dt).days or 1

        payload = build_sales_funnel_request(
            nm_ids=list(nm_ids) if nm_ids else [],
            days=days,
            end_date=end_dt,
        )
        response = self.client.post(
            SALES_FUNNEL_URL,
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        save_raw("sales_funnel", data)
        return data


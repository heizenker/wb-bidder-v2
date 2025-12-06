from __future__ import annotations

import datetime
import logging
from typing import Dict, List, Optional

from wb_bidder.core.api_client_v2 import ApiClientV2

logger = logging.getLogger(__name__)


class SalesFunnelCollectorV2:
    """
    Коллектор по воронке продаж через backend_v2.
    """

    def __init__(self, client: Optional[ApiClientV2] = None) -> None:
        self.client: ApiClientV2 = client or ApiClientV2(
            base_url="http://127.0.0.1:8002",
        )

    def collect(self, days: int, nm_ids: Optional[List[int]] = None) -> List[Dict]:
        """
        Забирает данные воронки за последние N дней.
        """
        today = datetime.date.today()
        date_from = (today - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        date_to = today.strftime("%Y-%m-%d")

        params: Dict[str, str] = {
            "date_from": date_from,
            "date_to": date_to,
        }
        if nm_ids:
            params["nm_ids"] = ",".join(str(i) for i in nm_ids)

        try:
            data = self.client.get_sales_funnel(params=params)
        except Exception as exc:
            logger.error("SalesFunnelCollectorV2.collect failed: %s", exc)
            return []

        # Нормализуем разные форматы ответа backend_v2 / WB analytics
        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            # Формат analytics v3: {"data": {"products": [...]} }
            inner = data.get("data")
            if isinstance(inner, dict):
                products = inner.get("products")
                if isinstance(products, list):
                    return products

            # Старый формат: {"items": [...]} — на всякий случай оставляем
            items = data.get("items")
            if isinstance(items, list):
                return items

            return [data]

        return []


from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, Iterable, List, Optional

from wb_bidder_v2.collectors_v2.base import BaseCollectorV2

logger = logging.getLogger(__name__)


class SalesFunnelCollectorV2(BaseCollectorV2):
    """
    Сборщик воронки продаж из нового API.

    Ожидаемый endpoint:
        GET /sales-funnel

    Рекомендуемый формат строки:
        {
            "date": "2025-11-01",
            "nm_id": 123456,
            "views": 10000,            # показы карточки
            "product_views": 4000,     # переходы в карточку
            "cart_adds": 300,          # в корзину
            "orders": 180,             # заказали
            "purchases": 150,          # выкупили
            "ordered_revenue": 20000.0,
            "purchased_revenue": 17000.0
        }
    """

    raw_section = "sales_funnel"

    def fetch_sales_funnel(
        self,
        date_from: datetime.date,
        date_to: datetime.date,
        nm_ids: Optional[Iterable[int]] = None,
    ) -> List[Dict[str, Any]]:
        raw = self.load_raw_payload()
        return self._ensure_rows(raw)

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _normalize_legacy_row(cls, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        nm_value = (
            row.get("nmId")
            or row.get("nm_id")
            or row.get("itemId")
            or row.get("item_id")
        )
        if not nm_value:
            campaign_id = row.get("campaignId") or row.get("campaign_id")
            nm_value = BaseCollectorV2.attach_nm_from_state({"campaign_id": campaign_id})
            if campaign_id and not nm_value:
                logger.warning("Sales funnel row without nmId (campaignId=%s)", campaign_id)
        if not nm_value:
            return None

        date_value = (
            row.get("date")
            or row.get("period")
            or row.get("analyticsDate")
            or row.get("calcDate")
            or row.get("day")
            or ""
        )

        views = cls._safe_int(
            row.get("views")
            or row.get("shows")
            or row.get("impressions")
            or row.get("detailViews")
            or row.get("productViews")
            or row.get("openCard")
        )
        add_to_cart = cls._safe_int(
            row.get("addToCart")
            or row.get("cartAdds")
            or row.get("addToBasket")
            or row.get("cart")
        )
        orders = cls._safe_int(row.get("orders") or row.get("purchases") or row.get("buyouts"))
        revenue = cls._safe_float(
            row.get("revenue")
            or row.get("orderedRevenue")
            or row.get("purchasedRevenue")
            or row.get("turnover")
        )

        cr = (orders / views * 100.0) if views > 0 else 0.0

        return {
            "nmId": int(nm_value),
            "date": date_value,
            "views": views,
            "addToCart": add_to_cart,
            "orders": orders,
            "revenue": revenue,
            "cr": cr,
        }

    @classmethod
    def _normalize_products_entry(cls, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        product = entry.get("product")
        statistic = entry.get("statistic")
        if not isinstance(product, dict) or not isinstance(statistic, dict):
            return None

        selected = statistic.get("selected")
        if not isinstance(selected, dict):
            return None

        nm_id = cls._safe_int(product.get("nmId") or product.get("nm_id"))
        if nm_id <= 0:
            return None

        period = selected.get("period") or {}
        date_value = period.get("end") or period.get("start") or ""

        views = cls._safe_int(
            selected.get("openCount") or selected.get("views") or selected.get("detailViews")
        )
        add_to_cart = cls._safe_int(selected.get("cartCount") or selected.get("cartAdds"))
        orders = cls._safe_int(selected.get("orderCount"))
        revenue = cls._safe_float(selected.get("orderSum"))

        cr = (orders / views * 100.0) if views > 0 else 0.0

        return {
            "nmId": nm_id,
            "date": date_value,
            "views": views,
            "addToCart": add_to_cart,
            "orders": orders,
            "revenue": revenue,
            "cr": cr,
        }

    @classmethod
    def _ensure_rows(cls, raw: Any) -> List[Dict[str, Any]]:
        # New format (data.products -> product/statistic)
        if isinstance(raw, dict):
            data_block = raw.get("data")
            if isinstance(data_block, dict) and isinstance(data_block.get("products"), list):
                normalized_new: List[Dict[str, Any]] = []
                for entry in data_block["products"]:
                    if not isinstance(entry, dict):
                        continue
                    normalized_row = cls._normalize_products_entry(entry)
                    if normalized_row:
                        normalized_new.append(normalized_row)
                if normalized_new:
                    return normalized_new

        # Fallback to legacy format
        if isinstance(raw, dict):
            inner = raw.get("data", raw)
            if isinstance(inner, dict):
                rows = inner.get("products") or inner.get("cards") or inner.get("items") or []
            elif isinstance(inner, list):
                rows = inner
            else:
                rows = []
        elif isinstance(raw, list):
            rows = raw
        else:
            rows = []

        normalized: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            normalized_row = cls._normalize_legacy_row(row)
            if normalized_row:
                normalized.append(normalized_row)

        return normalized


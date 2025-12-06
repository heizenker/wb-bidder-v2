from __future__ import annotations

import datetime
from typing import Any, Dict, Iterable, List, Optional

import logging

from wb_bidder_v2.collectors_v2.base import BaseCollectorV2
from wb_bidder_v2.adapters.state_store import lookup_nm_by_campaign


logger = logging.getLogger(__name__)


class SearchQueriesCollectorV2(BaseCollectorV2):
    """
    Сборщик статистики по поисковым запросам из нового API.

    Ожидаемый endpoint:
        GET /search-queries

    Рекомендуемый формат строки:
        {
            "date": "2025-11-01",
            "nm_id": 123456,
            "query": "носки мужские теплые",
            "impressions": 5000,
            "clicks": 200,
            "orders": 25,
            "revenue": 15000.0,
            "spend": 1200.0
        }
    """

    raw_section = "search_report"

    def fetch_search_queries(
        self,
        date_from: datetime.date,
        date_to: datetime.date,
        nm_ids: Optional[Iterable[int]] = None,
        queries: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает плоские строки поиска для CombinedAnalyzerV2 в формате:
        {
            "nmId": int,
            "query": str,
            "shows": int,
            "impressions": int,
            "views": int,
            "clicks": int,
            "orders": int,
            "ctr": float,
            "avg_position": float | None,
        }
        """
        raw = self.load_raw_payload()
        payload = self._extract_payload(raw)

        rows: List[Dict[str, Any]] = self._normalize_groups(payload)
        if not rows:
            rows = self._ensure_rows(payload)

        if nm_ids:
            nm_set = {int(nm) for nm in nm_ids}
            rows = [row for row in rows if int(row.get("nmId") or 0) in nm_set]

        return rows

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_payload(raw: Any) -> Any:
        if isinstance(raw, dict) and "wb_raw" in raw:
            return raw["wb_raw"]
        return raw

    @classmethod
    def _normalize_groups(cls, payload: Any) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if not isinstance(payload, dict):
            return rows

        data_block = payload.get("data")
        if not isinstance(data_block, dict):
            return rows

        groups = data_block.get("groups")
        if not isinstance(groups, list):
            return rows

        for group in groups:
            if not isinstance(group, dict):
                continue
            query_text = group.get("query") or group.get("word") or group.get("searchQuery")
            items = group.get("items")
            if not isinstance(items, list):
                continue
            for card in items:
                if not isinstance(card, dict):
                    continue
                normalized = cls._normalize_card_entry(card, query_text)
                if normalized:
                    rows.append(normalized)

        return rows

    @classmethod
    def _normalize_row(cls, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        nm_value = (
            row.get("nmId")
            or row.get("nm_id")
            or row.get("articleId")
            or row.get("item_id")
        )
        campaign_id = row.get("campaignId") or row.get("campaign_id") or row.get("advertId")
        if not nm_value and campaign_id:
            nm_value = lookup_nm_by_campaign(campaign_id)
            if campaign_id and not nm_value:
                logger.warning("Search queries row with campaignId=%s has no nmId", campaign_id)
        if nm_value is None:
            return None

        query_text = row.get("query") or row.get("word") or row.get("searchQuery")
        if not query_text:
            return None

        shows = cls._safe_int(row.get("shows") or row.get("impressions") or row.get("views"))
        clicks = cls._safe_int(row.get("clicks"))
        orders = cls._safe_int(row.get("orders") or row.get("purchases"))
        avg_position = row.get("avg_position") or row.get("rank") or row.get("position")
        avg_position_float = cls._safe_float(avg_position)
        if avg_position_float is not None and avg_position_float <= 0:
            avg_position_float = None
        ctr = (clicks / shows * 100.0) if shows > 0 else 0.0

        return {
            "nmId": int(nm_value),
            "query": query_text,
            "shows": shows,
            "impressions": shows,
            "views": shows,
            "clicks": clicks,
            "orders": orders,
            "ctr": ctr,
            "avg_position": avg_position_float,
        }

    @classmethod
    def _normalize_card_entry(cls, card: Dict[str, Any], query: Optional[str]) -> Optional[Dict[str, Any]]:
        nm_id = cls._safe_int(card.get("nmId") or card.get("nm_id"))
        if nm_id <= 0:
            return None

        if not query:
            query = "<unknown>"

        metrics_block = card.get("metrics") if isinstance(card.get("metrics"), dict) else None

        shows = cls._metric_current(metrics_block, card, "openCard")
        clicks = cls._metric_current(metrics_block, card, "addToCart")
        orders = cls._metric_current(metrics_block, card, "orders")
        avg_position = cls._metric_current(metrics_block, card, "avgPosition", as_float=True)

        ctr = (clicks / shows * 100.0) if shows > 0 else 0.0
        avg_position_value = avg_position if (avg_position is not None and avg_position > 0) else None

        return {
            "nmId": nm_id,
            "query": query,
            "shows": shows,
            "impressions": shows,
            "views": shows,
            "clicks": clicks,
            "orders": orders,
            "ctr": ctr,
            "avg_position": avg_position_value,
        }

    @classmethod
    def _metric_current(
        cls,
        metrics_block: Optional[Dict[str, Any]],
        card: Dict[str, Any],
        field: str,
        *,
        as_float: bool = False,
    ) -> int | float:
        def _extract(block: Any) -> Any:
            if isinstance(block, dict):
                if "current" in block:
                    return block.get("current")
                return block.get("value")
            return block

        primary = _extract(metrics_block.get(field)) if metrics_block else None
        fallback = _extract(card.get(field))
        value = primary if primary is not None else fallback

        if as_float:
            result = cls._safe_float(value)
            return result if result is not None else 0.0

        return cls._safe_int(value)

    @classmethod
    def _ensure_rows(cls, payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, dict):
            items = payload.get("rows") or payload.get("items") or payload.get("data")
            rows = items if isinstance(items, list) else []
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []

        normalized: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            normalized_row = cls._normalize_row(row)
            if normalized_row:
                normalized.append(normalized_row)

        return normalized

    def collect(self, days: int) -> List[Dict[str, Any]]:
        today = datetime.date.today()
        date_to = today
        date_from = today - datetime.timedelta(days=days)
        return self.fetch_search_queries(date_from, date_to)


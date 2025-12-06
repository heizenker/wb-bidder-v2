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
        Нормализует search-report (analytics v2) в плоские строки:
        date, nmId, query, impressions/views, clicks, orders, spend, revenue.

        CombinedAnalyzerV2 дальше сам досчитает CTR/CPC/CPO/ROAS.
        """
        raw = self.load_raw_payload()

        rows: List[Dict[str, Any]] = []

        # Основной путь: новый формат analytics v2 (data -> groups -> items)
        try:
            payload = raw.get("data") if isinstance(raw, dict) else None
            if isinstance(payload, dict):
                groups = payload.get("groups")
                if isinstance(groups, list):
                    for group in groups:
                        if not isinstance(group, dict):
                            continue
                        query_text = (
                            group.get("query")
                            or group.get("word")
                            or group.get("searchQuery")
                        )
                        items = group.get("items")
                        if not isinstance(items, list):
                            continue
                        for card in items:
                            if not isinstance(card, dict):
                                continue
                            normalized = self._normalize_card_entry(card)
                            if not normalized:
                                continue
                            if query_text:
                                normalized["query"] = query_text
                            rows.append(normalized)
        except Exception:
            logger.exception(
                "SearchQueriesCollectorV2: failed to parse groups/items search-report format"
            )

        # Фоллбек: общий нормалайзер (legacy форматы / старые RAW)
        if not rows:
            rows = self._ensure_rows(raw)

        # Опциональный фильтр по nmId (для panel_cli / CombinedAnalyzerV2)
        if nm_ids:
            nm_set = {int(nm) for nm in nm_ids}

            def _nm_id(row: Dict[str, Any]) -> int:
                return int(row.get("nmId") or row.get("nm_id") or 0)

            rows = [row for row in rows if _nm_id(row) in nm_set]

        return rows

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

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

        shows = cls._safe_int(row.get("impressions") or row.get("views") or row.get("shows"))
        clicks = cls._safe_int(row.get("clicks"))
        orders = cls._safe_int(row.get("orders") or row.get("purchases"))
        ctr = (clicks / shows * 100.0) if shows > 0 else 0.0
        rank = row.get("rank") or row.get("avg_position") or row.get("position")

        return {
            "date": row.get("date") or row.get("currentDate") or "",
            "nmId": int(nm_value),
            "query": query_text,
            "shows": shows,
            "clicks": clicks,
            "orders": orders,
            "ctr": ctr,
            "rank": cls._safe_int(rank) if rank is not None else None,
        }

    @classmethod
    def _normalize_card_entry(cls, card: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        nm_id = cls._safe_int(card.get("nmId") or card.get("nm_id"))
        if nm_id <= 0:
            return None

        open_card = card.get("openCard") or {}
        add_to_cart = card.get("addToCart") or {}
        orders_block = card.get("orders") or {}
        avg_position = card.get("avgPosition") or {}

        shows = cls._safe_int(open_card.get("current"))
        clicks = cls._safe_int(add_to_cart.get("current"))
        orders = cls._safe_int(orders_block.get("current"))
        rank = cls._safe_int(avg_position.get("current"))
        ctr = (clicks / shows * 100.0) if shows > 0 else 0.0

        return {
            "date": None,
            "nmId": nm_id,
            "query": None,
            "shows": shows,
            "views": shows,
            "impressions": shows,
            "clicks": clicks,
            "orders": orders,
            "revenue": 0.0,
            "cost": 0.0,
            "spend": 0.0,
            "ctr": ctr,
            "rank": rank if rank > 0 else None,
        }

    @classmethod
    def _ensure_rows(cls, raw: Any) -> List[Dict[str, Any]]:
        payload = raw
        if isinstance(raw, dict) and "wb_raw" in raw:
            payload = raw["wb_raw"]

        normalized_new: List[Dict[str, Any]] = []
        data_block = None
        if isinstance(payload, dict):
            data_block = payload.get("data")

        # Новый формат: data (dict) -> groups -> items
        if isinstance(data_block, dict):
            groups = data_block.get("groups")
            if isinstance(groups, list):
                for group in groups:
                    if not isinstance(group, dict):
                        continue
                    query_text = group.get("query") or group.get("keyword")
                    items = group.get("items")
                    if not isinstance(items, list):
                        continue
                    for card in items:
                        if not isinstance(card, dict):
                            continue
                        normalized_card = cls._normalize_card_entry(card)
                        if not normalized_card:
                            continue
                        if query_text:
                            normalized_card["query"] = query_text
                        normalized_new.append(normalized_card)
        # Альтернативный формат: data (list) -> block.response.cards
        if not normalized_new and isinstance(data_block, list):
            for block in data_block:
                if not isinstance(block, dict):
                    continue
                response = block.get("response")
                if not isinstance(response, dict):
                    continue
                cards = response.get("cards")
                if not isinstance(cards, list):
                    continue
                for card in cards:
                    if not isinstance(card, dict):
                        continue
                    normalized_card = cls._normalize_card_entry(card)
                    if normalized_card:
                        normalized_new.append(normalized_card)
        if normalized_new:
            return normalized_new

        # Legacy fallback
        if isinstance(payload, dict):
            items = payload.get("data") or payload.get("items") or payload.get("rows")
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


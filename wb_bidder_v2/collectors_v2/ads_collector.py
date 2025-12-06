from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, Iterable, List, Optional

from wb_bidder_v2.collectors_v2.base import BaseCollectorV2

logger = logging.getLogger(__name__)


class AdsCollectorV2(BaseCollectorV2):
    """
    Сборщик рекламной статистики из нового единого API.

    Ожидаемый endpoint backend'а:
        GET /ads

    Каждая строка содержит агрегированную статистику кампании:
    advertId, campaign_id, nmId, views, clicks, orders, revenue, spent (+ производные метрики).
    """

    raw_section = "ads"

    def fetch_ads(
        self,
        date_from: datetime.date,
        date_to: datetime.date,
        nm_ids: Optional[Iterable[int]] = None,
        campaign_ids: Optional[Iterable[int]] = None,
        placement: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Забрать рекламную статистику за период через backend_v2.
        Возвращает список строк в унифицированном формате v2.
        """
        # Параметры сохраняем для совместимости интерфейса,
        # однако данные берём из RAW-слоя (последняя выгрузка).
        raw = self.load_raw_payload()
        return self._ensure_rows(raw)

    def collect_campaign_stats(
        self,
        campaign_ids: Iterable[int],
        days: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Совместимый с v1 метод: собирает статистику по списку кампаний
        за N дней для указанного списка кампаний.

        Возвращает список строк в формате, который ожидает старый код:
        advertId, date, views, clicks, orders, spent, cr, cpo, nm_id и т.д.
        """
        campaign_ids_list = list(campaign_ids)
        if not campaign_ids_list:
            return []

        date_to = datetime.date.today()
        date_from = date_to - datetime.timedelta(days=days)

        return self.fetch_ads(
            date_from=date_from,
            date_to=date_to,
            nm_ids=None,
            campaign_ids=campaign_ids_list,
            placement=None,
        )

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        try:
            result = int(value)
        except (TypeError, ValueError):
            return None
        return result if result > 0 else None

    @classmethod
    def _extract_nm_from_row(cls, row: Dict[str, Any]) -> Optional[int]:
        candidates = [
            row.get("nmId"),
            row.get("nm_id"),
            row.get("nm"),
            row.get("item_id"),
            row.get("itemId"),
            row.get("articleId"),
            row.get("subjectNmId"),
            row.get("subjectId"),
        ]
        for candidate in candidates:
            nm = cls._safe_int(candidate)
            if nm:
                return nm

        params = row.get("params")
        if isinstance(params, list):
            for param in params:
                if not isinstance(param, dict):
                    continue
                nm = cls._safe_int(
                    param.get("nm")
                    or param.get("nmId")
                    or param.get("nm_id")
                    or param.get("item_id")
                )
                if nm:
                    return nm

        apps = row.get("apps")
        if isinstance(apps, list):
            for app in apps:
                if not isinstance(app, dict):
                    continue
                nms = app.get("nms")
                if isinstance(nms, list):
                    for nm_entry in nms:
                        if isinstance(nm_entry, dict):
                            nm = cls._safe_int(
                                nm_entry.get("nm")
                                or nm_entry.get("nmId")
                                or nm_entry.get("nm_id")
                            )
                            if nm:
                                return nm
        stats_blocks = row.get("stats") or row.get("days")
        if isinstance(stats_blocks, list):
            for stat in stats_blocks:
                if isinstance(stat, dict):
                    nm = cls._extract_nm_from_row(stat)
                    if nm:
                        return nm
        return None

    @classmethod
    def _normalize_row(cls, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        advert_id_raw = row.get("advertId") or row.get("campaign_id") or row.get("advert_id")
        try:
            advert_id = int(advert_id_raw)
        except (TypeError, ValueError):
            logger.warning("ADS collector: пропускаю запись без advertId (%s)", advert_id_raw)
            return None

        nm_value = (
            row.get("nmId")
            or row.get("nm_id")
            or row.get("item_id")
            or cls._extract_nm_from_row(row)
            or BaseCollectorV2.attach_nm_from_state({"campaign_id": advert_id})
        )
        nm_id = cls._safe_int(nm_value)
        if nm_id is None:
            logger.warning(
                "ADS collector: campaign without nmId (advertId=%s) — пропускаю запись",
                advert_id,
            )
            return None

        date_value = row.get("date")
        if not isinstance(date_value, str) or not date_value:
            stats_block = row.get("stats") or row.get("days")
            if isinstance(stats_block, list) and stats_block:
                date_value = stats_block[0].get("date")
        if isinstance(date_value, str) and "T" in date_value:
            date_value = date_value.split("T", 1)[0]
        if not isinstance(date_value, str) or not date_value:
            logger.warning("ADS collector: пропускаю запись без даты (advertId=%s)", advert_id)
            return None

        views = int(cls._safe_float(row.get("views") or row.get("impressions")))
        clicks = int(cls._safe_float(row.get("clicks")))
        orders = int(cls._safe_float(row.get("orders")))
        cost = cls._safe_float(
            row.get("cost") or row.get("spent") or row.get("spend") or row.get("sum")
        )
        revenue = cls._safe_float(row.get("revenue") or row.get("sum_price") or row.get("sumPrice"))

        ctr = (clicks / views * 100.0) if views > 0 else 0.0
        cr = (orders / clicks * 100.0) if clicks > 0 else 0.0
        cpc = (cost / clicks) if clicks > 0 else 0.0
        cpo = (cost / orders) if orders > 0 else None

        return {
            "advertId": advert_id,
            "campaign_id": advert_id,
            "nmId": nm_id,
            "date": date_value,
            "views": views,
            "clicks": clicks,
            "cost": cost,
            "orders": orders,
            "revenue": revenue,
            "ctr": row.get("ctr", ctr),
            "cr": row.get("cr", cr),
            "cpc": row.get("cpc", cpc),
            "cpo": row.get("cpo") if row.get("cpo") is not None else cpo,
            "spent": cost,
            "spend": cost,
        }

    @classmethod
    def _ensure_rows(cls, raw: Any) -> List[Dict[str, Any]]:
        payload = raw
        if isinstance(raw, dict) and "wb_raw" in raw:
            payload = raw["wb_raw"]

        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            rows = payload["items"]
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


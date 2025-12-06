from __future__ import annotations

from typing import Any, Dict, List, Optional

from wb_bidder_v2.adapters.storage.raw_store import load_latest
from wb_bidder_v2.adapters.state_store import lookup_nm_by_campaign


class BaseCollectorV2:
    """
    Базовый класс для всех сборщиков v2.

    Работает только с RAW-слоем и не выполняет сетевых запросов.
    """

    raw_section: str = ""

    @classmethod
    def from_env(cls) -> "BaseCollectorV2":
        return cls()

    def load_raw_payload(self) -> Any:
        if not self.raw_section:
            raise RuntimeError("raw_section is not configured for this collector")
        return load_latest(self.raw_section)

    @staticmethod
    def attach_nm_from_state(row: Dict[str, Any]) -> Optional[int]:
        """
        Try to obtain nmId from the state store if it is missing in the row.
        """
        nm_id = row.get("nmId") or row.get("nm_id") or row.get("item_id")
        if nm_id:
            try:
                return int(nm_id)
            except (TypeError, ValueError):
                return None

        campaign_id = (
            row.get("campaign_id")
            or row.get("campaignId")
            or row.get("advertId")
            or row.get("advert_id")
        )
        return lookup_nm_by_campaign(campaign_id)

    # Небольшой helper: из ответа API получить список строк.
    @staticmethod
    def _ensure_rows_old(raw: Any) -> List[Dict[str, Any]]:
        """
        Новый API может вернуть:
          - просто список dict'ов
          - или {"items": [...]}
          - или {"wb_raw": [...]} (ответ от backend_v2 /ads_real)

        Мы везде приводим к List[Dict[str, Any]].
        """

        if isinstance(raw, list):
            return [row for row in raw if isinstance(row, dict)]
        if isinstance(raw, dict):
            # Проверяем wb_raw (ответ от backend_v2)
            if "wb_raw" in raw:
                wb_raw = raw["wb_raw"]
                # wb_raw от WB API /adv/v3/fullstats - это список кампаний
                # Каждая кампания имеет структуру: {"advertId": ..., "days": [...]}
                if isinstance(wb_raw, list):
                    # Нормализуем структуру WB: разворачиваем days в отдельные строки
                    result = []
                    for campaign in wb_raw:
                        if not isinstance(campaign, dict):
                            continue
                        advert_id = campaign.get("advertId") or campaign.get("id")
                        # ВАЖНО: эталон v1 использует поле "stats", не "days"!
                        # Пробуем сначала "stats" (как в старом коде), затем "days" (для совместимости)
                        stats = campaign.get("stats") or campaign.get("days") or []
                        if isinstance(stats, list):
                            for stat_row in stats:
                                if isinstance(stat_row, dict):
                                    # Нормализуем дату (как в старом коде)
                                    day = stat_row.get("date")
                                    if isinstance(day, str) and "T" in day:
                                        day = day.split("T")[0]

                                    # Создаём нормализованную строку (как в старом _normalize_fullstats)
                                    normalized = {
                                        "advertId": advert_id,
                                        "campaign_id": advert_id,
                                        "date": day,
                                        "views": stat_row.get("views", 0),
                                        "clicks": stat_row.get("clicks", 0),
                                        "spend": stat_row.get("sum", 0.0) + stat_row.get("spent", 0.0),
                                        "spent": stat_row.get("sum", 0.0) + stat_row.get("spent", 0.0),
                                        "orders": stat_row.get("orders", 0),
                                    }

                                    # Производные метрики (как в старом коде)
                                    clicks = normalized["clicks"]
                                    orders = normalized["orders"]
                                    spend = normalized["spend"]
                                    normalized["cr"] = (orders / clicks * 100) if clicks > 0 else 0.0
                                    normalized["cpo"] = (spend / orders) if orders > 0 else None

                                    # Извлекаем nm_id из структуры apps/nms если есть (для days)
                                    if "apps" in stat_row and isinstance(stat_row["apps"], list):
                                        for app in stat_row["apps"]:
                                            if isinstance(app, dict) and "nms" in app:
                                                nms = app["nms"]
                                                if isinstance(nms, list) and nms:
                                                    first_nm = nms[0]
                                                    if isinstance(first_nm, dict):
                                                        nm_id = first_nm.get("nm") or first_nm.get("nmId")
                                                        if nm_id:
                                                            normalized["nm_id"] = nm_id
                                                            normalized["item_id"] = nm_id

                                    result.append(normalized)
                        else:
                            # Если days нет, добавляем саму кампанию
                            result.append(campaign)
                    return result
                elif isinstance(wb_raw, dict):
                    # Если это dict, пробуем найти вложенные списки
                    if "adverts" in wb_raw and isinstance(wb_raw["adverts"], list):
                        return [row for row in wb_raw["adverts"] if isinstance(row, dict)]
                    # Или это может быть один объект кампании
                    return [wb_raw]

            # Стандартные ключи
            items = raw.get("items") or raw.get("data") or []

            if isinstance(items, list):
                return [row for row in items if isinstance(row, dict)]

        return []

    @staticmethod
    def _normalize_campaign_stats(campaign: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Превратить структуру одной кампании (advertId + stats/days) в плоский список строк."""
        result: List[Dict[str, Any]] = []
        if not isinstance(campaign, dict):
            return result

        advert_id = campaign.get("advertId") or campaign.get("id")

        def _iter_rows(block: Any) -> List[Dict[str, Any]]:
            if isinstance(block, list):
                return [row for row in block if isinstance(row, dict)]
            return []

        stats_rows = _iter_rows(campaign.get("stats"))
        days_rows = _iter_rows(campaign.get("days"))
        source_rows = stats_rows or days_rows

        for row in source_rows:
            day = row.get("date")
            if isinstance(day, str) and "T" in day:
                day = day.split("T")[0]

            spent_value = row.get("sum")
            if spent_value is None:
                spent_value = row.get("spent")
            if spent_value is None:
                spent_value = 0.0

            spent_float = float(spent_value)
            normalized: Dict[str, Any] = {
                "advertId": advert_id,
                "campaign_id": advert_id,
                "date": day,
                "views": row.get("views", 0),
                "clicks": row.get("clicks", 0),
                "orders": row.get("orders", 0),
                "spend": spent_float,
                "spent": spent_float,
                "cpc": row.get("cpc"),
                "ctr": row.get("ctr"),
                "cr": row.get("cr"),
            }

            apps = row.get("apps")
            if isinstance(apps, list):
                for app in apps:
                    if not isinstance(app, dict):
                        continue
                    nms = app.get("nms")
                    if isinstance(nms, list):
                        for nm in nms:
                            if isinstance(nm, dict):
                                nm_id = nm.get("nm") or nm.get("nmId") or nm.get("nm_id")
                                if nm_id:
                                    normalized["nm_id"] = nm_id
                                    normalized["item_id"] = nm_id
                                    break
                    if "item_id" in normalized:
                        break

            result.append(normalized)

        return result

    @staticmethod
    def _ensure_rows(raw: Any) -> List[Dict[str, Any]]:
        """
        Новый нормализатор, основанный на stats (/adv/v3/fullstats).
        """

        def _collect_campaigns(payload: Any) -> List[Dict[str, Any]]:
            if isinstance(payload, list):
                return [entry for entry in payload if isinstance(entry, dict)]
            if isinstance(payload, dict):
                if isinstance(payload.get("adverts"), list):
                    return [entry for entry in payload["adverts"] if isinstance(entry, dict)]
                return [payload]
            return []

        payload = raw
        if isinstance(raw, dict) and "wb_raw" in raw:
            payload = raw["wb_raw"]

        campaigns = _collect_campaigns(payload)
        normalized_rows: List[Dict[str, Any]] = []
        for campaign in campaigns:
            normalized_rows.extend(BaseCollectorV2._normalize_campaign_stats(campaign))

        return normalized_rows


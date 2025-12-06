from __future__ import annotations



import datetime

from dataclasses import dataclass

from typing import Any, Dict, Iterable, List, Optional



from wb_bidder.core.api_client_v2 import ApiClientV2





# -------------------------------------------------------------------

# БАЗОВЫЙ КОЛЛЕКТОР ДЛЯ API V2

# -------------------------------------------------------------------





@dataclass

class BaseCollectorV2:

    """

    Базовый класс для всех сборщиков v2.



    Работает ТОЛЬКО через новый ApiClientV2 и единый backend.

    Старые endpoints WB никуда не дергаем.

    """



    client: ApiClientV2



    @classmethod

    def from_env(cls) -> "BaseCollectorV2":

        """

        Упрощённый конструктор:

        - использует ApiClientV2, который сам читает конфигурацию из .env

        """

        api_client = ApiClientV2()

        return cls(client=api_client)



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





# -------------------------------------------------------------------

# РЕКЛАМА — AdsCollectorV2

# -------------------------------------------------------------------





@dataclass

class AdsCollectorV2(BaseCollectorV2):
    """
    Сборщик рекламной статистики из нового единого API.

    Ожидаемый endpoint backend'а:
        GET /ads

    Каждая строка содержит агрегированную статистику кампании:
    advertId, campaign_id, nmId, views, clicks, orders, revenue, spent (+ производные метрики).
    """

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
        params: Dict[str, Any] = {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        }

        if nm_ids is not None:
            params["nm_ids"] = ",".join(str(x) for x in nm_ids)

        if campaign_ids is not None:
            params["campaign_ids"] = ",".join(str(x) for x in campaign_ids)

        if placement:
            params["placement"] = placement

        raw = self.client.get_ads(params=params)
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
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _normalize_row(cls, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        advert_id = cls._safe_int(row.get("advertId") or row.get("campaign_id") or row.get("advert_id"))
        if advert_id <= 0:
            return None

        nm_value = row.get("nmId") or row.get("nm_id") or row.get("item_id")
        nm_id = cls._safe_int(nm_value) if nm_value is not None else None

        views = cls._safe_float(row.get("views") or row.get("impressions"))
        clicks = cls._safe_float(row.get("clicks"))
        orders = cls._safe_float(row.get("orders"))
        spent = cls._safe_float(row.get("spent") or row.get("spend") or row.get("cost"))
        revenue = cls._safe_float(row.get("revenue"))

        ctr = (clicks / views * 100.0) if views > 0 else 0.0
        cpc = (spent / clicks) if clicks > 0 else 0.0
        cpo = (spent / orders) if orders > 0 else 0.0

        return {
            "advertId": advert_id,
            "campaign_id": advert_id,
            "nmId": nm_id,
            "views": views,
            "clicks": clicks,
            "orders": orders,
            "revenue": revenue,
            "spent": spent,
            "ctr": row.get("ctr", ctr),
            "cpc": row.get("cpc", cpc),
            "cpo": row.get("cpo", cpo),
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





# -------------------------------------------------------------------

# ПОИСКОВЫЕ ЗАПРОСЫ — SearchQueriesCollectorV2

# -------------------------------------------------------------------





@dataclass

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



    def fetch_search_queries(

        self,

        date_from: datetime.date,

        date_to: datetime.date,

        nm_ids: Optional[Iterable[int]] = None,

        queries: Optional[Iterable[str]] = None,

    ) -> List[Dict[str, Any]]:

        params: Dict[str, Any] = {

            "date_from": date_from.isoformat(),

            "date_to": date_to.isoformat(),

        }



        if nm_ids is not None:

            params["nm_ids"] = ",".join(str(x) for x in nm_ids)

        if queries is not None:

            params["queries"] = "|".join(q for q in queries)



        raw = self.client.get_search_queries(params=params)

        return self._ensure_rows(raw)





# -------------------------------------------------------------------

# ВОРОНКА ПРОДАЖ — SalesFunnelCollectorV2

# -------------------------------------------------------------------





@dataclass

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



    def fetch_sales_funnel(

        self,

        date_from: datetime.date,

        date_to: datetime.date,

        nm_ids: Optional[Iterable[int]] = None,

    ) -> List[Dict[str, Any]]:

        params: Dict[str, Any] = {

            "date_from": date_from.isoformat(),

            "date_to": date_to.isoformat(),

        }



        if nm_ids is not None:

            params["nm_ids"] = ",".join(str(x) for x in nm_ids)



        raw = self.client.get_sales_funnel(params=params)
        return self._ensure_rows(raw)

    @staticmethod
    def _ensure_rows(raw: Any) -> List[Dict[str, Any]]:
        """
        Приводим ответ backend_v2 (/sales-funnel) к списку строк
        с учётом формата analytics v3 (products/cards).
        """
        if isinstance(raw, dict):
            inner = raw.get("data", raw)
            if isinstance(inner, dict):
                rows = inner.get("products") or inner.get("cards") or []
            elif isinstance(inner, list):
                rows = inner
            else:
                rows = []
        elif isinstance(raw, list):
            rows = raw
        else:
            rows = []

        return [row for row in rows if isinstance(row, dict)]


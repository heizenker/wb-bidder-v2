from __future__ import annotations

import datetime
from typing import Any, Iterable, List, Dict

from wb_bidder.core.client import WildberriesClient


class AdsCollector:
    """
    Сборщик рекламной статистики WB.
    Работает через WildberriesClient.
    """

    def __init__(self, client: WildberriesClient | None = None):
        self.client = client or WildberriesClient.from_env()

    # --------------------------------------------------------------
    # Основной метод
    # --------------------------------------------------------------

    def collect_campaign_stats(
        self,
        campaign_ids: Iterable[int],
        days: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Собрать статистику по списку кампаний за N дней.

        Возвращает массив объектов:
        {
            "advertId": ...,
            "date": "YYYY-MM-DD",
            "views": ...,
            "clicks": ...,
            "spend": ...,
            "orders": ...,
            "cr": ...,
            "cpo": ...,
        }
        """

        campaign_ids = list(campaign_ids)
        if not campaign_ids:
            return []

        date_to = datetime.date.today()
        date_from = date_to - datetime.timedelta(days=days)

        raw = self.client.get_campaign_stats(
            advert_ids=campaign_ids,
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
        )

        return self._normalize_fullstats(raw)

    # --------------------------------------------------------------
    # Нормализация ответа WB
    # --------------------------------------------------------------

    def _normalize_fullstats(self, raw: Any) -> List[Dict[str, Any]]:
        """
        WB возвращает жесть — вложенные структуры.
        Превращаем в плоский массив строк.
        """

        if not isinstance(raw, list):
            return []

        result: List[Dict[str, Any]] = []

        for campaign in raw:
            advert_id = campaign.get("advertId") or campaign.get("adverId")

            stats = campaign.get("stats", [])
            if not isinstance(stats, list):
                continue

            for row in stats:
                day = row.get("date")

                # NB: WB иногда отдаёт дату с временем → обрезаем
                if isinstance(day, str) and "T" in day:
                    day = day.split("T")[0]

                obj = {
                    "advertId": advert_id,
                    "date": day,
                    "views": row.get("views", 0),
                    "clicks": row.get("clicks", 0),
                    "spend": row.get("sum", 0.0),
                    "orders": row.get("orders", 0),
                }

                # производные
                clicks = obj["clicks"]
                orders = obj["orders"]
                spend = obj["spend"]

                obj["cr"] = (orders / clicks * 100) if clicks > 0 else 0.0
                obj["cpo"] = (spend / orders) if orders > 0 else None

                result.append(obj)

        return result


# --------------------------------------------------------------
# Мини-тест (можно временно запускать вручную)
# --------------------------------------------------------------

if __name__ == "__main__":
    client = WildberriesClient.from_env()
    collector = AdsCollector(client)

    # Пример: собрать по первым 1–3 РК
    campaigns = client.get_campaigns()
    ids = [c.get("advertId") or c.get("id") for c in campaigns][:3]

    print("CAMPAIGNS:", ids)

    data = collector.collect_campaign_stats(ids, days=3)

    for row in data[:10]:
        print(row)


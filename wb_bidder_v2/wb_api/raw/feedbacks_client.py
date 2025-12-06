from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wb_bidder_v2.wb_api.client import WildberriesClient
from wb_bidder_v2.adapters.storage.raw_store import save_raw

FEEDBACKS_URL = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"


@dataclass
class FeedbacksRawClient:
    client: WildberriesClient

    @classmethod
    def from_env(cls) -> "FeedbacksRawClient":
        return cls(client=WildberriesClient.from_env())

    def fetch_feedbacks(
        self,
        *,
        nm_id: int,
        is_answered: bool = False,
        take: int = 100,
        skip: int = 0,
        order: str = "dateDesc",
    ) -> Any:
        params = {
            "nmId": int(nm_id),
            "isAnswered": str(bool(is_answered)).lower(),
            "take": take,
            "skip": skip,
            "order": order,
        }
        response = self.client.get(
            FEEDBACKS_URL,
            params=params,
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        save_raw("feedbacks", data)
        return data


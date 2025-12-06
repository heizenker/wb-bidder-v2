from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Any

from wb_bidder_v2.wb_api.client import WildberriesClient
from wb_bidder_v2.adapters.storage.raw_store import save_raw


@dataclass
class AdsRawClient:
    client: WildberriesClient

    @classmethod
    def from_env(cls) -> "AdsRawClient":
        return cls(client=WildberriesClient.from_env())

    def fetch_fullstats(
        self,
        *,
        campaign_ids: Iterable[int],
        date_from: str,
        date_to: str,
        version: str = "v3",
    ) -> Any:
        ids_list = [int(x) for x in campaign_ids if int(x) > 0]
        if not ids_list:
            raise ValueError("campaign_ids must contain at least one positive integer")

        ids_param = ",".join(str(i) for i in ids_list)
        response = self.client.get(
            f"/adv/{version}/fullstats",
            params={"ids": ids_param, "beginDate": date_from, "endDate": date_to},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        save_raw("ads", data)
        return data


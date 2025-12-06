from __future__ import annotations

from typing import Any, Dict, Optional, List

from wb_bidder_v2.wb_api.api_client_v2 import ApiClientV2
from wb_bidder_v2.wb_api.client import WildberriesClient
from wb_bidder_v2.adapters.state_store import (
    state_store,
    record_command_result,
    update_from_campaigns_api,
)


def _client() -> WildberriesClient:
    return WildberriesClient.from_env()


def _campaigns_from_api() -> list[dict[str, Any]]:
    return ApiClientV2().get_campaigns()


def get_current_state(campaign_id: int) -> Dict[str, Any]:
    """
    Читает фактическое состояние кампании напрямую из WB.
    """
    client = _client()
    campaigns = _campaigns_from_api()
    campaign_data = _find_campaign(campaigns, campaign_id)
    bids_payload = client.get_bids(campaign_id)
    current_bid = _extract_bid_value(bids_payload)
    return {
        "campaign_id": campaign_id,
        "status": (campaign_data or {}).get("status") or (campaign_data or {}).get("state"),
        "current_bid": current_bid,
    }


def verify_change(campaign_id: int, desired_state: Dict[str, Any]) -> bool:
    """
    Перечитывает состояние и убеждается, что оно соответствует ожиданиям.
    """
    state = get_current_state(campaign_id)

    desired_status = desired_state.get("status")
    if desired_status is not None:
        actual_status = (state.get("status") or "").lower()
        if actual_status != str(desired_status).lower():
            return False

    if "bid" in desired_state:
        actual_bid = state.get("current_bid")
        desired_bid = desired_state["bid"]
        if actual_bid is None:
            return False
        if abs(float(actual_bid) - float(desired_bid)) > 0.5:
            return False

    return True


def pull_campaign_mapping() -> None:
    """
    Load campaign list from WB and persist mapping in state_store.
    """
    campaigns_payload = _campaigns_from_api()
    update_from_campaigns_api({"campaigns": campaigns_payload})


def cache_command_result(campaign_id: int, *, status: str | None = None, bid: int | None = None) -> None:
    """
    Cache confirmed command execution to state_store.
    """
    record_command_result(campaign_id, status=status, bid=bid)


def _find_campaign(campaigns: Any, campaign_id: int) -> Optional[Dict[str, Any]]:
    if isinstance(campaigns, dict):
        campaigns = campaigns.get("adverts") or campaigns.get("campaigns")
    if not isinstance(campaigns, list):
        return None
    for campaign in campaigns:
        if not isinstance(campaign, dict):
            continue
        raw_id = (
            campaign.get("advertId")
            or campaign.get("advert_id")
            or campaign.get("campaign_id")
            or campaign.get("id")
        )
        try:
            if int(raw_id) == campaign_id:
                return campaign
        except (TypeError, ValueError):
            continue
    return None


def _extract_bid_value(payload: Any) -> Optional[float]:
    """
    Ищет текущее значение ставки в структуре ответа WB.
    """
    if payload is None:
        return None
    candidates = []

    def _collect(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in {"bid", "currentBid", "price"}:
                    try:
                        candidates.append(float(value))
                    except (TypeError, ValueError):
                        pass
                else:
                    _collect(value)
        elif isinstance(obj, list):
            for item in obj:
                _collect(item)

    _collect(payload)
    if not candidates:
        return None
    # Берём последнее значение как актуальное
    return candidates[-1]


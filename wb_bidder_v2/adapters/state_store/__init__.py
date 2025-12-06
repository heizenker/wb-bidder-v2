from __future__ import annotations

from typing import Any, Dict, List

from .state_store import (
    load_state,
    save_state,
    lookup_nm_by_campaign,
    dump_items,
    update_from_campaigns_api,
    STATE_FILE,
)


def get_campaign_ids() -> List[int]:
    """
    Return a sorted list of all known campaign identifiers.
    """
    state = load_state()
    campaigns = state.get("campaigns", {})
    return sorted(int(cid) for cid in campaigns.keys())


def get_nm_ids() -> List[int]:
    """
    Return a sorted list of all known nmId entries.
    """
    state = load_state()
    items = state.get("items", {})
    return sorted(int(nm) for nm in items.keys())


def record_command_result(campaign_id: int, *, status: str | None = None, bid: int | None = None) -> None:
    """
    Persist the latest confirmed status/bid for the specified campaign.
    """
    state = load_state()
    campaigns: Dict[str, Any] = state.setdefault("campaigns", {})
    entry = campaigns.setdefault(str(campaign_id), {})
    if status is not None:
        entry["status"] = status
    if bid is not None:
        entry["current_bid"] = bid
    campaigns[str(campaign_id)] = entry
    save_state(state)


__all__ = [
    "STATE_FILE",
    "get_campaign_ids",
    "get_nm_ids",
    "record_command_result",
    "lookup_nm_by_campaign",
    "dump_items",
    "update_from_campaigns_api",
    "load_state",
    "save_state",
]


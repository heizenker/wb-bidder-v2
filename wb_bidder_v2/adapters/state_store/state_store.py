from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Tuple


STATE_FILE = Path(__file__).resolve().parent / "state.json"

_DEFAULT_STATE: Dict[str, Any] = {
    "campaigns": {},  # campaign_id -> {"nm_id": int, "last_seen": iso}
    "items": {},  # nm_id -> {"campaign_ids": [int], "last_seen": iso}
    "queries": {},  # nm_id -> list[str]
}


def load_state() -> Dict[str, Any]:
    """
    Load the current bidder state from disk.
    """
    if not STATE_FILE.exists():
        return copy.deepcopy(_DEFAULT_STATE)
    try:
        with STATE_FILE.open("r", encoding="utf-8") as fp:
            raw_state = json.load(fp)
    except json.JSONDecodeError:
        return copy.deepcopy(_DEFAULT_STATE)

    # Ensure all required top-level keys exist
    state = copy.deepcopy(_DEFAULT_STATE)
    state.update(raw_state)
    return state


def save_state(state: Dict[str, Any]) -> None:
    """
    Persist bidder state atomically.
    """
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = STATE_FILE.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as fp:
        json.dump(state, fp, ensure_ascii=False, indent=2, sort_keys=True)
    tmp_path.replace(STATE_FILE)


def update_campaign_mapping(raw_ads_payload: Any) -> None:
    """
    Extract campaignId ↔ nmId pairs from raw /ads payload and update state.
    """
    pairs = list(_extract_pairs_from_ads_payload(raw_ads_payload))
    if not pairs:
        return

    state = load_state()
    for campaign_id, nm_id in pairs:
        _register_campaign_pair(state, campaign_id, nm_id)
    save_state(state)


def update_from_campaigns_api(payload: Any) -> None:
    """
    Consume normalized /campaigns payload produced by backend_v2 and
    refresh the campaign mapping.
    """
    campaigns = payload
    if isinstance(payload, dict):
        campaigns = payload.get("campaigns") or []

    if not isinstance(campaigns, Iterable):
        return

    state = load_state()
    for campaign in campaigns:
        if not isinstance(campaign, dict):
            continue
        campaign_id = _safe_int(
            campaign.get("campaign_id")
            or campaign.get("advertId")
            or campaign.get("advert_id")
            or campaign.get("id")
        )
        nm_id = _safe_int(campaign.get("item_id") or campaign.get("nm_id") or campaign.get("nmId"))
        if campaign_id > 0 and nm_id > 0:
            _register_campaign_pair(state, campaign_id, nm_id)
    save_state(state)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_pairs_from_ads_payload(payload: Any) -> Iterator[Tuple[int, int]]:
    """
    Walk through raw /ads payload (list, dict, or {"wb_raw": ...}) and
    yield (campaign_id, nm_id).
    """
    entries = payload
    if isinstance(payload, dict) and "wb_raw" in payload:
        entries = payload["wb_raw"]

    if isinstance(entries, dict):
        # WB can return {"adverts": [...]} or {"items": [...]}
        nested = entries.get("adverts") or entries.get("items")
        if isinstance(nested, list):
            entries = nested

    if not isinstance(entries, Iterable):
        return

    for campaign in entries:
        if not isinstance(campaign, dict):
            continue
        campaign_id = _safe_int(
            campaign.get("advertId") or campaign.get("advert_id") or campaign.get("campaign_id") or campaign.get("id")
        )
        nm_id = _extract_nm_id_from_campaign(campaign)
        if campaign_id > 0 and nm_id > 0:
            yield campaign_id, nm_id


def _extract_nm_id_from_campaign(campaign: Dict[str, Any]) -> int:
    """
    Try multiple known locations for nmId inside WB campaign structures.
    """
    nm_candidates = [
        campaign.get("nmId"),
        campaign.get("nm_id"),
        campaign.get("nm"),
        campaign.get("item_id"),
        campaign.get("nmID"),
    ]
    for candidate in nm_candidates:
        nm = _safe_int(candidate)
        if nm > 0:
            return nm

    # Nested params list
    params = campaign.get("params")
    if isinstance(params, list):
        for param in params:
            if not isinstance(param, dict):
                continue
            nm = _safe_int(param.get("nm") or param.get("nmId") or param.get("nm_id"))
            if nm > 0:
                return nm

    # Nested apps/nms blocks
    apps = campaign.get("apps")
    if isinstance(apps, list):
        for app in apps:
            if not isinstance(app, dict):
                continue
            nms = app.get("nms")
            if isinstance(nms, list):
                for nm_block in nms:
                    if not isinstance(nm_block, dict):
                        continue
                    nm = _safe_int(nm_block.get("nm") or nm_block.get("nmId") or nm_block.get("nm_id"))
                    if nm > 0:
                        return nm

    return 0


def _register_campaign_pair(state: Dict[str, Any], campaign_id: int, nm_id: int) -> None:
    """
    Update both campaign and item indexes with the provided ids.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    campaign_key = str(campaign_id)
    item_key = str(nm_id)

    campaign_entry = state.setdefault("campaigns", {}).setdefault(campaign_key, {})
    campaign_entry.update({"nm_id": nm_id, "last_seen": timestamp})

    item_entry = state.setdefault("items", {}).setdefault(item_key, {"campaign_ids": [], "last_seen": timestamp})
    if campaign_id not in item_entry.setdefault("campaign_ids", []):
        item_entry["campaign_ids"].append(campaign_id)
    item_entry["last_seen"] = timestamp


def lookup_nm_by_campaign(campaign_id: Any) -> Optional[int]:
    try:
        cid = int(campaign_id)
    except (TypeError, ValueError):
        return None
    state = load_state()
    entry = state.get("campaigns", {}).get(str(cid))
    if not entry:
        return None
    nm_id = entry.get("nm_id")
    try:
        return int(nm_id)
    except (TypeError, ValueError):
        return None


def dump_items() -> List[Dict[str, Any]]:
    """
    Return a normalized list of items from state_store.
    """
    state = load_state()
    items: List[Dict[str, Any]] = []
    for nm_key, entry in state.get("items", {}).items():
        try:
            nm_id = int(nm_key)
        except (TypeError, ValueError):
            continue
        campaign_ids = entry.get("campaign_ids") or []
        normalized_campaigns: List[int] = []
        for cid in campaign_ids:
            try:
                normalized_campaigns.append(int(cid))
            except (TypeError, ValueError):
                continue
        items.append(
            {
                "nm_id": nm_id,
                "campaign_ids": normalized_campaigns,
                "raw": entry,
            }
        )
    return items


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


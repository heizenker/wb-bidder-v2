from __future__ import annotations

from typing import Dict, List, Mapping, Any


def _extract_nm_id(row: dict) -> int | None:
    """
    Пытается достать nm_id из строки с разными вариантами ключей.
    """
    candidates = [
        "nmId",
        "nm_id",
        "nm",
        "itemNmId",
        "subjectNmId",
    ]
    for key in candidates:
        value = row.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return None


def join_search_and_funnel(
    search_rows: List[dict],
    funnel_rows: List[dict],
    campaign_to_item: Mapping[Any, Any] | None = None,
) -> Dict[int, Dict[str, List[dict]]]:
    """
    Склеивает поисковые запросы и воронку по nm_id.
    """
    result: Dict[int, Dict[str, List[dict]]] = {}

    def _nm_from_mapping(row: dict) -> int | None:
        if not campaign_to_item:
            return None
        campaign_id = (
            row.get("campaign_id")
            or row.get("campaignId")
            or row.get("advertId")
            or row.get("advert_id")
        )
        if campaign_id is None:
            return None
        try:
            return int(campaign_to_item.get(str(campaign_id)) or campaign_to_item.get(campaign_id))
        except (TypeError, ValueError):
            return None

    for row in search_rows:
        nm_id = _extract_nm_id(row) or _nm_from_mapping(row)
        if nm_id is None:
            continue
        bucket = result.setdefault(nm_id, {"search": [], "funnel": []})
        bucket["search"].append(row)

    for row in funnel_rows:
        nm_id = _extract_nm_id(row) or _nm_from_mapping(row)
        if nm_id is None:
            continue
        bucket = result.setdefault(nm_id, {"search": [], "funnel": []})
        bucket["funnel"].append(row)

    return result


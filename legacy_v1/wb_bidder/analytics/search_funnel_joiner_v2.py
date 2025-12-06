from __future__ import annotations

from typing import Dict, List


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
) -> Dict[int, Dict[str, List[dict]]]:
    """
    Склеивает поисковые запросы и воронку по nm_id.
    """
    result: Dict[int, Dict[str, List[dict]]] = {}

    for row in search_rows:
        nm_id = _extract_nm_id(row)
        if nm_id is None:
            continue
        bucket = result.setdefault(nm_id, {"search": [], "funnel": []})
        bucket["search"].append(row)

    for row in funnel_rows:
        nm_id = _extract_nm_id(row)
        if nm_id is None:
            continue
        bucket = result.setdefault(nm_id, {"search": [], "funnel": []})
        bucket["funnel"].append(row)

    return result


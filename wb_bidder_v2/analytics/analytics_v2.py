from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import logging

from wb_bidder_v2.analytics.cpo_v2 import CPOContext, decide_bid

logger = logging.getLogger(__name__)


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


@dataclass
class CombinedAnalyzerV2:
    """
    Pure analytics helper that accepts already collected rows (ads, queries, funnel)
    or collector-like objects that expose fetch_* methods.
    """

    ads_source: Any
    queries_source: Any
    funnel_source: Any

    def _ensure_rows(
        self,
        source: Any,
        loader_name: str,
        date_from: Optional[datetime.date],
        date_to: Optional[datetime.date],
        nm_ids: Optional[List[int]],
    ) -> List[Dict[str, Any]]:
        if isinstance(source, list):
            return source
        if source is None:
            return []

        loader = getattr(source, loader_name, None)
        if callable(loader):
            if date_from is None or date_to is None:
                raise ValueError("date_from/date_to are required when using collectors")
            kwargs: Dict[str, Any] = {
                "date_from": date_from,
                "date_to": date_to,
                "nm_ids": nm_ids,
            }
            if loader_name == "fetch_ads":
                kwargs.update({"campaign_ids": None, "placement": None})
            if loader_name == "fetch_search_queries":
                kwargs["queries"] = None
            return loader(**kwargs)

        raise TypeError(f"Unsupported analytics source for {loader_name}")

    def load_all(
        self,
        date_from: Optional[datetime.date],
        date_to: Optional[datetime.date],
        nm_ids: Optional[List[int]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        ads_rows = self._ensure_rows(self.ads_source, "fetch_ads", date_from, date_to, nm_ids)
        query_rows = self._ensure_rows(
            self.queries_source,
            "fetch_search_queries",
            date_from,
            date_to,
            nm_ids,
        )
        funnel_rows = self._ensure_rows(
            self.funnel_source,
            "fetch_sales_funnel",
            date_from,
            date_to,
            nm_ids,
        )
        return {"ads": ads_rows, "queries": query_rows, "funnel": funnel_rows}

    @staticmethod
    def enrich_row(row: Dict[str, Any]) -> Dict[str, Any]:
        impressions = safe_int(row.get("impressions") or row.get("views"))
        clicks = safe_int(row.get("clicks"))
        cost = safe_float(row.get("cost") or row.get("spend") or row.get("spent"))
        orders = safe_int(row.get("orders"))
        revenue = safe_float(row.get("revenue"))

        row["impressions"] = impressions
        row["views"] = impressions
        row["clicks"] = clicks
        row["orders"] = orders
        row["cost"] = cost
        row["spend"] = cost
        row["spent"] = cost
        row["ctr"] = (clicks / impressions * 100.0) if impressions > 0 else 0.0
        row["cpc"] = (cost / clicks) if clicks > 0 else 0.0
        row["cr"] = (orders / clicks * 100.0) if clicks > 0 else 0.0
        row["cpo"] = (cost / orders) if orders > 0 else None
        row["roas"] = (revenue / cost) if cost > 0 else 0.0
        return row

    @staticmethod
    def group_by_nm(rows: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
        grouped: Dict[int, List[Dict[str, Any]]] = {}
        for row in rows:
            nm_value = row.get("nm_id") or row.get("nmId") or row.get("item_id")
            try:
                nm = int(nm_value)
            except (TypeError, ValueError):
                logger.warning("Analytics group_by_nm: skipping row without nmId")
                continue
            grouped.setdefault(nm, []).append(row)
        return grouped

    @staticmethod
    def aggregate(rows: List[Dict[str, Any]]) -> Dict[str, float]:
        total = {"impressions": 0, "clicks": 0, "cost": 0.0, "orders": 0, "revenue": 0.0}
        for row in rows:
            total["impressions"] += safe_int(row.get("impressions") or row.get("views"))
            total["clicks"] += safe_int(row.get("clicks"))
            total["cost"] += safe_float(row.get("cost") or row.get("spend") or row.get("spent"))
            total["orders"] += safe_int(row.get("orders"))
            total["revenue"] += safe_float(row.get("revenue"))

        imp = total["impressions"]
        clk = total["clicks"]
        cost = total["cost"]
        orders = total["orders"]
        revenue = total["revenue"]

        return {
            **total,
            "ctr": (clk / imp * 100.0) if imp > 0 else 0.0,
            "cpc": (cost / clk) if clk > 0 else 0.0,
            "cr": (orders / clk * 100.0) if clk > 0 else 0.0,
            "cpo": (cost / orders) if orders > 0 else None,
            "spend": cost,
            "roas": (revenue / cost) if cost > 0 else 0.0,
        }

    def build_report(
        self,
        date_from: Optional[datetime.date] = None,
        date_to: Optional[datetime.date] = None,
        nm_ids: Optional[List[int]] = None,
    ) -> Dict[int, Dict[str, Any]]:
        raw = self.load_all(date_from, date_to, nm_ids)
        ads_grouped = self.group_by_nm(raw["ads"])
        queries_grouped = self.group_by_nm(raw["queries"])
        funnel_grouped = self.group_by_nm(raw["funnel"])

        result: Dict[int, Dict[str, Any]] = {}
        for nm in sorted(set(ads_grouped) | set(queries_grouped) | set(funnel_grouped)):
            nm_ads = [self.enrich_row(row) for row in ads_grouped.get(nm, [])]
            nm_queries = [self.enrich_row(row) for row in queries_grouped.get(nm, [])]
            nm_funnel = [self.enrich_row(row) for row in funnel_grouped.get(nm, [])]
            result[nm] = {
                "ads": {"rows": nm_ads, "agg": self.aggregate(nm_ads)},
                "queries": {"rows": nm_queries, "agg": self.aggregate(nm_queries)},
                "funnel": {"rows": nm_funnel, "agg": self.aggregate(nm_funnel)},
            }
        return result


class CPOModuleV2:
    """
    CPO decision helper that works on aggregated analytics rows.
    """

    def __init__(
        self,
        target_cpo: float = 300.0,
        min_clicks: int = 20,
        min_orders: int = 2,
        step_up_pct: float = 0.15,
        step_down_pct: float = 0.15,
        dry_run: bool = True,
    ) -> None:
        self.target_cpo = target_cpo
        self.min_clicks = min_clicks
        self.min_orders = min_orders
        self.step_up_pct = step_up_pct
        self.step_down_pct = step_down_pct
        self.dry_run = dry_run

    def analyze_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        ctx = CPOContext(
            item_id=item_data["item_id"],
            clicks=item_data.get("clicks", 0),
            orders=item_data.get("orders", 0),
            spent=item_data.get("spent", 0.0),
            revenue=item_data.get("revenue", 0.0),
            current_bid=item_data.get("current_bid", 10.0),
            target_cpo=self.target_cpo,
            min_clicks=self.min_clicks,
            min_orders=self.min_orders,
            step_up_pct=self.step_up_pct,
            step_down_pct=self.step_down_pct,
            dry_run=self.dry_run,
        )
        return decide_bid(ctx).as_dict()

    def analyze_many(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.analyze_item(item) for item in items]


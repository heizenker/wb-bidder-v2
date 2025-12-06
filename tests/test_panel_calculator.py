from __future__ import annotations

import datetime as dt

from wb_bidder_v2.collectors_v2.ads_collector import AdsCollectorV2
from wb_bidder_v2.panel import PanelSnapshot, build_panel_snapshot


def test_build_panel_snapshot_basic():
    ads_rows = [
        {
            "advertId": 101,
            "nmId": 111,
            "views": 100,
            "clicks": 10,
            "orders": 2,
            "spent": 400.0,
        },
        {
            "advertId": 102,
            "nmId": 222,
            "views": 200,
            "clicks": 20,
            "orders": 5,
            "spent": 500.0,
        },
    ]
    queries_rows = [
        {"nmId": 111, "query": "socks", "impressions": 50, "clicks": 5, "orders": 1, "spend": 50.0},
        {"nmId": 222, "query": "gloves", "impressions": 100, "clicks": 10, "orders": 2, "spend": 70.0},
    ]
    funnel_rows = [
        {"nmId": 111, "views": 500, "orders": 30, "buyouts": 25},
        {"nmId": 222, "views": 200, "orders": 20, "buyouts": 15},
    ]

    snapshot = build_panel_snapshot(
        ads_rows=ads_rows,
        query_rows=queries_rows,
        funnel_rows=funnel_rows,
    )

    assert isinstance(snapshot, PanelSnapshot)
    assert len(snapshot.items) == 2
    item = snapshot.find(111)
    assert item is not None
    assert item.ads.aggregate["impressions"] >= 100
    assert item.queries.rows[0]["query"] == "socks"
    assert item.funnel.aggregate["orders"] >= 30


def test_panel_snapshot_empty_sections():
    snapshot = build_panel_snapshot(ads_rows=[], query_rows=[], funnel_rows=[])
    assert isinstance(snapshot, PanelSnapshot)
    assert snapshot.items == []


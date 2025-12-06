from __future__ import annotations

import datetime as dt
import logging

import pytest

from wb_bidder_v2.adapters.storage import raw_store
from wb_bidder_v2.collectors_v2.ads_collector import AdsCollectorV2
from wb_bidder_v2.collectors_v2.sales_funnel_collector import SalesFunnelCollectorV2
from wb_bidder_v2.collectors_v2.search_queries_collector import SearchQueriesCollectorV2


@pytest.fixture(autouse=True)
def _temp_raw_dir(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    monkeypatch.setattr(raw_store, "RAW_BASE_DIR", raw_dir)
    return raw_dir


def test_collectors_read_from_raw(tmp_path, caplog):
    date_from = dt.date(2025, 1, 1)
    date_to = dt.date(2025, 1, 2)

    caplog.set_level(logging.WARNING)

    ads_payload = {
        "wb_raw": [
            {
                "advertId": 123,
                "stats": [
                    {
                        "date": "2025-01-01T00:00:00Z",
                        "views": 100,
                        "clicks": 10,
                        "sum": 500,
                        "orders": 5,
                        "apps": [{"nms": [{"nm": 555555}]}],
                    }
                ],
            },
            {
                "advertId": 124,
                "stats": [
                    {
                        "date": "2025-01-01T00:00:00Z",
                        "views": 50,
                        "clicks": 5,
                        "sum": 200,
                        "orders": 1,
                    }
                ],
            },
        ]
    }
    raw_store.save_raw("ads", ads_payload)

    funnel_payload = {
        "data": {
            "products": [
                {
                    "nmId": 555555,
                    "date": "2025-01-01",
                    "views": 1000,
                    "productViews": 400,
                    "cartAdds": 50,
                    "orders": 20,
                    "buyouts": 15,
                },
                {
                    "campaignId": 888000,
                    "views": 10,
                },
            ]
        }
    }
    raw_store.save_raw("sales_funnel", funnel_payload)

    search_payload = {
        "data": [
            {
                "nmId": 555555,
                "query": "socks",
                "impressions": 1000,
                "clicks": 30,
                "orders": 4,
                "revenue": 700.0,
            },
            {
                "campaignId": 777000,
                "query": "missing nm",
                "impressions": 10,
            },
        ]
    }
    raw_store.save_raw("search_report", search_payload)

    ads_rows = AdsCollectorV2.from_env().fetch_ads(
        date_from=date_from,
        date_to=date_to,
    )
    funnel_rows = SalesFunnelCollectorV2.from_env().fetch_sales_funnel(
        date_from=date_from,
        date_to=date_to,
    )
    search_rows = SearchQueriesCollectorV2.from_env().fetch_search_queries(
        date_from=date_from,
        date_to=date_to,
    )

    assert ads_rows and all("nmId" in row and row["nmId"] != 0 for row in ads_rows)
    assert funnel_rows and all("nmId" in row and row["nmId"] != 0 for row in funnel_rows)
    assert search_rows and all("nmId" in row and row["nmId"] != 0 for row in search_rows)

    assert ads_rows[0]["date"]
    assert "addToCart" in funnel_rows[0] and "cr" in funnel_rows[0]
    assert search_rows[0]["query"] == "socks" and "ctr" in search_rows[0]

    assert any("ADS collector: campaign without nmId" in msg for msg in caplog.messages)
    assert any("Sales funnel row without nmId" in msg for msg in caplog.messages)
    assert any("Search queries row with campaignId" in msg for msg in caplog.messages)


from __future__ import annotations

from wb_bidder_v2.bidder.bidder_v2 import BidderV2


def test_bidder_generates_set_bid_command():
    config = [
        {
            "advert_id": 1,
            "name": "test campaign",
            "min_bid": 50,
            "max_bid": 500,
            "base_bid": 100,
            "target_cpo": 200,
        }
    ]
    rules = {
        "min_clicks": 1,
        "min_orders": 1,
        "step_up_pct": 0.10,
        "step_down_pct": 0.10,
        "cpo_tolerance_pct": 0.10,
    }
    bidder = BidderV2.from_config(config, rules)

    ads_rows = [
        {
            "advertId": 1,
            "views": 1000,
            "clicks": 100,
            "orders": 10,
            "spent": 500.0,
            "current_bid": 100,
        }
    ]

    commands = bidder.generate_commands(
        normalized_ads=ads_rows,
        sales_funnel=[],
        search_queries=[],
    )

    assert commands, "Bidder should produce commands"
    cmd = commands[0]
    assert cmd["type"] == "set_bid"
    assert cmd["campaignId"] == 1
    assert "bid" in cmd


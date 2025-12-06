from __future__ import annotations

import json
from pathlib import Path

from wb_bidder_v2.adapters.state_store import (
    load_state,
    save_state,
    update_campaign_mapping,
    get_campaign_ids,
    get_nm_ids,
)


def test_state_store_flow(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr("wb_bidder_v2.adapters.state_store.state_store.STATE_FILE", state_file)

    fake_ads_payload = {
        "wb_raw": [
            {
                "advertId": 101,
                "nmId": 555001,
            },
            {
                "advertId": 102,
                "nm_id": 555002,
            },
            {
                "advertId": 103,
                "campaign_id": 103,
                "params": [{"nm": 555003}],
            },
        ]
    }

    save_state({"campaigns": {}, "items": {}, "queries": {}})

    update_campaign_mapping(fake_ads_payload)

    assert set(get_campaign_ids()) == {101, 102, 103}
    assert set(get_nm_ids()) == {555001, 555002, 555003}


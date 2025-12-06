from __future__ import annotations

import datetime as dt

from wb_bidder_v2.workflows.utils import collect_full_cycle
from wb_bidder_v2.adapters.state_store import load_state, save_state


def test_collect_full_cycle(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr("wb_bidder_v2.adapters.state_store.state_store.STATE_FILE", state_file)
    save_state({"campaigns": {}, "items": {}, "queries": {}})

    date_from = dt.date(2025, 1, 1)
    date_to = dt.date(2025, 1, 2)

    def fake_bootstrap():
        state = load_state()
        state["campaigns"]["101"] = {"nm_id": 555001, "last_seen": "2025-01-01T00:00:00Z"}
        state["items"]["555001"] = {"campaign_ids": [101], "last_seen": "2025-01-01T00:00:00Z"}
        save_state(state)
        return False

    monkeypatch.setattr("wb_bidder_v2.workflows.utils.bootstrap_state_from_campaigns", fake_bootstrap)
    monkeypatch.setattr("wb_bidder_v2.workflows.utils.refresh_raw_data", lambda **_: None)

    collect_full_cycle(date_from=date_from, date_to=date_to)

    assert load_state()["campaigns"]


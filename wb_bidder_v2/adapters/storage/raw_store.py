from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RAW_BASE_DIR = Path("raw")


def _ensure_section_dir(section: str) -> Path:
    section_path = RAW_BASE_DIR / section
    section_path.mkdir(parents=True, exist_ok=True)
    return section_path


def save_raw(section: str, data: Any) -> Path:
    """
    Persist raw JSON payload under raw/<section>/<timestamp>.json.
    """
    section_path = _ensure_section_dir(section)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    file_path = section_path / f"{timestamp}.json"
    with file_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    return file_path


def load_latest(section: str) -> Any:
    """
    Load the most recent raw payload for the given section.
    """
    section_path = _ensure_section_dir(section)
    files = sorted(section_path.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No raw snapshots found for section '{section}'.")
    latest = files[-1]
    with latest.open("r", encoding="utf-8") as fh:
        return json.load(fh)


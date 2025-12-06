from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

ADVERT_API_BASE = "https://advert-api.wildberries.ru"
SELLER_ANALYTICS_API_BASE = "https://seller-analytics-api.wildberries.ru"
FEEDBACKS_API_BASE = "https://feedbacks-api.wildberries.ru"


ENDPOINTS: List[Dict[str, Any]] = [
    {
        "method": "GET",
        "url": f"{ADVERT_API_BASE}/adv/v3/fullstats",
        "label": "/adv/v3/fullstats",
    },
    {
        "method": "GET",
        "url": f"{ADVERT_API_BASE}/adv/v1/campaigns",
        "label": "/adv/v1/campaigns",
    },
    {
        "method": "GET",
        "url": f"{ADVERT_API_BASE}/adv/v1/adverts",
        "label": "/adv/v1/adverts",
    },
    {
        "method": "POST",
        "url": f"{SELLER_ANALYTICS_API_BASE}/api/v2/search-report/report",
        "label": "/api/v2/search-report/report",
    },
    {
        "method": "POST",
        "url": f"{SELLER_ANALYTICS_API_BASE}/api/analytics/v3/sales-funnel/products",
        "label": "/api/analytics/v3/sales-funnel/products",
    },
    {
        "method": "GET",
        "url": f"{FEEDBACKS_API_BASE}/api/v1/feedbacks",
        "label": "/api/v1/feedbacks",
    },
]


class ApiInspectorClient:
    """Минимальный HTTP-клиент для прямых запросов к WB API."""

    def __init__(self, *, timeout: float = 30.0) -> None:
        token = os.environ.get("WB_API_TOKEN")
        if not token or not token.strip():
            raise RuntimeError("Переменная окружения WB_API_TOKEN отсутствует или пуста.")
        self.token: str = token.strip()
        self.timeout = timeout
        self.base_url = SELLER_ANALYTICS_API_BASE.rstrip("/")

    def request(self, method: str, url: str, **kwargs) -> dict:
        import logging
        import requests

        logger = logging.getLogger(__name__)

        headers = kwargs.setdefault("headers", {})
        headers.setdefault("Authorization", self.token)
        response = requests.request(method, url, timeout=self.timeout, **kwargs)

        try:
            response.raise_for_status()
        except requests.HTTPError:
            body = response.text
            logger.error(
                "API inspector HTTP error: %s %s -> %s; body=%s",
                method,
                url,
                response.status_code,
                body,
            )
            print("\n=== API inspector error ===")
            print(f"{method} {url} -> {response.status_code}")
            print(body)
            print("=== END error body ===\n")
            raise

        try:
            return response.json()
        except ValueError:
            return {"status_code": response.status_code, "body": response.text}

    def fetch_sales_funnel(self, days: int) -> dict:
        """
        Загружает воронку продаж за N дней через POST /api/analytics/v3/sales-funnel/products
        и сохраняет RAW в raw/sales_funnel/<timestamp>.json
        """
        from datetime import date, timedelta

        today = date.today()
        current_end = today
        current_start = current_end - timedelta(days=days - 1)

        past_end = current_start - timedelta(days=1)
        past_start = past_end - timedelta(days=days - 1)

        url = f"{self.base_url}/api/analytics/v3/sales-funnel/products"
        payload = {
            "selectedPeriod": {
                "start": current_start.isoformat(),
                "end": current_end.isoformat(),
            },
            "pastPeriod": {
                "start": past_start.isoformat(),
                "end": past_end.isoformat(),
            },
            "nmIds": [],
            "brandNames": [],
            "subjectIds": [],
            "tagIds": [],
            "skipDeletedNm": True,
            "orderBy": {
                "field": "openCard",
                "mode": "asc",
            },
            "limit": 1000,
            "offset": 0,
        }

        data = self.request("POST", url, json=payload)
        self._save_raw("sales_funnel", data)
        return data

    def fetch_search_queries(self, days: int) -> dict:
        """
        Загружает поисковые запросы через POST /api/v2/search-report/report
        и сохраняет RAW в raw/search_report/<timestamp>.json
        """
        from datetime import date, timedelta

        today = date.today()
        current_end = today
        current_start = current_end - timedelta(days=days - 1)

        past_end = current_start - timedelta(days=1)
        past_start = past_end - timedelta(days=days - 1)

        url = f"{self.base_url}/api/v2/search-report/report"
        payload = {
            "currentPeriod": {
                "start": current_start.isoformat(),
                "end": current_end.isoformat(),
            },
            "pastPeriod": {
                "start": past_start.isoformat(),
                "end": past_end.isoformat(),
            },
            "nmIds": [],
            "subjectIds": [],
            "brandNames": [],
            "tagIds": [],
            "positionCluster": "all",
            "orderBy": {
                "field": "openCard",
                "mode": "asc",
            },
            "includeSubstitutedSKUs": True,
            "includeSearchTexts": True,
            "limit": 1000,
            "offset": 0,
        }

        data = self.request("POST", url, json=payload)
        self._save_raw("search_report", data)
        return data

    def _save_raw(self, section: str, data: Any) -> Path:
        base = Path("raw") / section
        base.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        file_path = base / f"{timestamp}.json"
        with file_path.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        return file_path



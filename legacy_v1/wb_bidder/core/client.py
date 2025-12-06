from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

import logging
import time

import requests

from wb_bidder.core.auth import load_token

# Base domain for the official Wildberries advert API
DEFAULT_API_BASE_URL = "https://advert-api.wildberries.ru"

logger = logging.getLogger(__name__)


@dataclass
class WildberriesClient:
    """
    Lightweight helper around the Wildberries advert API.

    It keeps token handling in one place and offers thin wrappers over
    requests.* plus a couple of convenience methods for advert APIs.
    """

    token: str
    api_base_url: str = DEFAULT_API_BASE_URL

    # ------------------------------------------------------------------ #
    # Low-level HTTP helpers
    # ------------------------------------------------------------------ #

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": self.token}

    @classmethod
    def from_env(cls, api_base_url: str = DEFAULT_API_BASE_URL) -> "WildberriesClient":
        return cls(token=load_token(), api_base_url=api_base_url)

    def _make_url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.api_base_url.rstrip('/')}/{path.lstrip('/')}"

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        max_attempts: int = 3,
        retry_delay: float = 10.0,
        error_delay: float = 5.0,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Send request with retry logic for network errors and 429 responses.
        """

        last_exc: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.request(method=method, url=url, **kwargs)
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning(
                    "WB request error (%s %s): %s (attempt %s/%s). Waiting %.1fs.",
                    method,
                    url,
                    exc,
                    attempt,
                    max_attempts,
                    error_delay,
                )
                if attempt == max_attempts:
                    raise
                time.sleep(error_delay)
                continue

            if response.status_code == 429:
                headers = response.headers or {}
                retry_after = headers.get("X-Ratelimit-Retry") or headers.get("Retry-After")
                reset_after = headers.get("X-Ratelimit-Reset")
                limit = headers.get("X-Ratelimit-Limit")
                remaining = headers.get("X-Ratelimit-Remaining")

                sleep_seconds = retry_delay
                for candidate in (retry_after, reset_after):
                    if candidate:
                        try:
                            sleep_seconds = max(1.0, float(candidate))
                            break
                        except (TypeError, ValueError):
                            continue

                logger.warning(
                    "WB API 429 Too Many Requests: retry in %.1fs (attempt %s/%s, limit=%s, remaining=%s, reset=%s)",
                    sleep_seconds,
                    attempt,
                    max_attempts,
                    limit,
                    remaining,
                    reset_after,
                )

                if attempt == max_attempts:
                    return response

                time.sleep(sleep_seconds)
                continue

            return response

        assert last_exc is not None
        raise last_exc

    def get(
        self,
        path: str,
        params: Optional[Mapping[str, Any]] = None,
        timeout: float = 10.0,
    ) -> requests.Response:
        return self._request_with_retry(
            "GET",
            self._make_url(path),
            headers=self.headers,
            params=params,
            timeout=timeout,
        )

    def post(
        self,
        path: str,
        json: Optional[Mapping[str, Any]] = None,
        timeout: float = 10.0,
    ) -> requests.Response:
        return self._request_with_retry(
            "POST",
            self._make_url(path),
            headers=self.headers,
            json=json,
            timeout=timeout,
        )

    def patch(
        self,
        path: str,
        json: Optional[Mapping[str, Any]] = None,
        timeout: float = 10.0,
    ) -> requests.Response:
        return self._request_with_retry(
            "PATCH",
            self._make_url(path),
            headers=self.headers,
            json=json,
            timeout=timeout,
        )

    # ------------------------------------------------------------------ #
    # Promotion API helpers
    # ------------------------------------------------------------------ #

    def get_campaigns(self) -> list[dict[str, Any]]:
        resp = self.get("/adv/v0/adverts")
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("adverts"), list):
            return data["adverts"]
        return []

    def get_campaign_stats(
        self,
        advert_ids: Iterable[int],
        date_from: str,
        date_to: str,
        version: str = "v3",
    ) -> Any:
        ids_str = ",".join(str(i) for i in advert_ids)
        if not ids_str:
            return []

        resp = self.get(
            f"/adv/{version}/fullstats",
            params={"ids": ids_str, "beginDate": date_from, "endDate": date_to},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()

    def get_bids(
        self,
        advert_id: int,
        placement: Optional[str] = None,
        timeout: float = 10.0,
    ) -> Any:
        params: dict[str, Any] = {"advertId": advert_id}
        if placement:
            params["placement"] = placement
        resp = self.get("/adv/v0/auction/bids", params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def set_bids(
        self,
        advert_id: int,
        bids: Iterable[Mapping[str, Any]],
        placement: Optional[str] = None,
        timeout: float = 10.0,
    ) -> requests.Response:
        payload: dict[str, Any] = {
            "advertId": advert_id,
            "bids": list(bids),
        }
        if placement:
            payload["placement"] = placement
        resp = self.patch("/adv/v0/auction/bids", json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp


    # ------------------------------------------------------------------ #
    # Feedbacks API helpers
    # ------------------------------------------------------------------ #

    FEEDBACKS_BASE_URL = "https://feedbacks-api.wildberries.ru"

    def get_feedbacks(
        self,
        article_id: int,
        is_answered: bool = False,
        take: int = 100,
        skip: int = 0,
        order: str = "dateDesc",
        timeout: float = 10.0,
    ) -> list[dict[str, Any]]:
        """
        Fetch feedback list for a given nmId.
        """
        params = {
            "isAnswered": str(is_answered).lower(),
            "nmId": article_id,
            "take": take,
            "skip": skip,
            "order": order,
        }

        url = f"{self.FEEDBACKS_BASE_URL}/api/v1/feedbacks"
        resp = self.get(url, params=params, timeout=timeout)
        resp.raise_for_status()

        data = resp.json()
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            return data["data"]
        if isinstance(data, list):
            return data
        return []

    def reply_feedback(
        self,
        feedback_id: str,
        text: str,
        timeout: float = 10.0,
    ) -> requests.Response:
        """
        Send reply to a feedback.
        """
        url = f"{self.FEEDBACKS_BASE_URL}/api/v1/feedbacks/answer"
        payload = {"id": feedback_id, "text": text}
        resp = self.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp

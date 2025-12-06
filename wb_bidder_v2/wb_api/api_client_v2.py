from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, List, Mapping, Optional
import time

import requests

from wb_bidder_v2.core.auth import load_token, load_api_base_url

# Резервный токен (если нет в окружении и load_token() ничего не вернул)
DEFAULT_API_V2_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjUwOTA0djEiLCJ0eXAiOiJKV1QifQ.eyJhY2MiOjEsImVudCI6MSwiZXhwIjoxNzgwMTg1MjgxLCJpZCI6IjAxOWFjZjc3LTFjNzktNzFhOS1iNzgzLWFmYTdjOTc4M2NhYyIsImlpZCI6MTMyMDE5NTUsIm9pZCI6MTM5OTgyLCJzIjoxNjEyNiwic2lkIjoiMzNiZTI5MGEtNDBkNS00ZWIwLWJjZTQtNGM4MjM5YWNiYmNjIiwidCI6ZmFsc2UsInVpZCI6MTMyMDE5NTV9.qB2W6iuaxvLjAJwZvx-vbAwOciEQe-5LutvhXQISv_p9teta3HrvbEadIRR4Bui6bLQQLSLmwSqwR-hS-0zvag"

logger = logging.getLogger(__name__)

# Базовый URL для НОВОГО локального backend_v2
WB_API_V2_BASE_URL = load_api_base_url()
WB_ADVERT_API_BASE_URL = "https://advert-api.wildberries.ru"


@dataclass
class ApiClientV2:
    """
    Клиент для ЕДИНОГО нового API, который отдаёт:

      - рекламу
      - поисковые запросы
      - воронку продаж
      - автоответы

    ВАЖНО:
      - НЕ ходит на старые WB endpoints (advert-api.wildberries.ru и т.п.)
      - Работает только через твой новый backend.

    Авторизация:
      - По умолчанию берём токен из:
          1) переменной окружения WB_API_V2_TOKEN
          2) если нет — используем load_token()
      - Токен кладём в заголовок Authorization: Bearer <token>.
    """

    base_url: Optional[str] = None
    api_token: Optional[str] = None
    timeout: int = 120  # было 30, увеличили до 120, чтобы не было ReadTimeout(30)

    def __post_init__(self) -> None:
        # Базовый URL
        if self.base_url:
            self.base_url = self.base_url.rstrip("/")
        else:
            self.base_url = WB_API_V2_BASE_URL.rstrip("/")

        # Токен для доступа к backend_v2 (он уже ходит на WB)
        if self.api_token is None:
            self.api_token = os.getenv("WB_API_V2_TOKEN") or load_token()
        if not self.api_token:
            # Как крайний вариант — хардкоженный токен
            self.api_token = DEFAULT_API_V2_TOKEN
        self.advert_base_url = WB_ADVERT_API_BASE_URL.rstrip("/")
        self.wb_token = (
            os.getenv("WB_API_TOKEN")
            or os.getenv("WB_TOKEN")
            or load_token()
        )

    @property
    def headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/json",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    def _build_url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Optional[Any] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        """
        Базовый запрос к локальному backend_v2.
        """
        # Собираем полный URL
        url = f"{self.base_url.rstrip('/')}{path}"

        # Вычисляем таймаут (используем поле timeout, которое теперь 120)
        effective_timeout = timeout or self.timeout

        # Заголовки
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_token:
            # Для backend_v2 мы передаём токен как есть (как было в первом варианте)
            headers["Authorization"] = self.api_token

        try:
            response = requests.request(
                method,
                url,
                params=params,
                json=json,
                headers=headers,
                timeout=effective_timeout,
            )
        except requests.RequestException as exc:
            logger.error(
                "API v2 request error: %s %s params=%r json=%r exc=%r",
                method,
                url,
                params,
                json,
                exc,
            )
            raise

        if response.status_code >= 400:
            logger.error(
                "API v2 bad response: %s %s -> %s %s; body=%s",
                method,
                url,
                response.status_code,
                response.reason,
                response.text,
            )
            response.raise_for_status()

        try:
            return response.json()
        except ValueError:
            return response.text

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Optional[Any] = None,
        headers: Optional[Mapping[str, str]] = None,
        timeout: Optional[int] = None,
        max_attempts: int = 3,
        retry_delay: float = 5.0,
    ) -> Any:
        """
        Универсальный запрос с повторными попытками для внешних API.
        """
        last_exc: Optional[Exception] = None
        effective_timeout = timeout or self.timeout

        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=headers,
                    timeout=effective_timeout,
                )
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning(
                    "API request error (%s %s): %s (attempt %s/%s)",
                    method,
                    url,
                    exc,
                    attempt,
                    max_attempts,
                )
                if attempt == max_attempts:
                    raise
                time.sleep(retry_delay)
                continue

            if response.status_code == 429 and attempt < max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = retry_delay
                if retry_after:
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        pass
                logger.warning(
                    "API response 429 (%s %s). Retrying in %.1fs (attempt %s/%s)",
                    method,
                    url,
                    delay,
                    attempt,
                    max_attempts,
                )
                time.sleep(delay)
                continue

            if response.status_code >= 400:
                logger.error(
                    "API external error: %s %s -> %s %s; body=%s",
                    method,
                    url,
                    response.status_code,
                    response.reason,
                    response.text,
                )
                response.raise_for_status()

            try:
                return response.json()
            except ValueError:
                return response.text

        if last_exc:
            raise last_exc
        raise RuntimeError("Unknown error during request")

    def get_ads(self, params: Optional[Mapping[str, Any]] = None) -> Any:
        return self.request("GET", "/ads", params=params)

    def get_search_queries(self, params: Optional[Mapping[str, Any]] = None) -> Any:
        return self.request("GET", "/search-queries", params=params)

    def get_sales_funnel(self, params: Optional[Mapping[str, Any]] = None) -> Any:
        print("DEBUG CLIENT PARAMS:", params)
        return self.request("GET", "/sales-funnel", params=params)

    def get_auto_replies(self, params: Optional[Mapping[str, Any]] = None) -> Any:
        return self.request("GET", "/auto-replies", params=params)

    def get_campaigns(self) -> List[dict[str, Any]]:
        """
        Получить список всех кампаний через WB /adv/v1/promotion/count.
        """
        if not self.wb_token:
            logger.error("WB /adv/v1/promotion/count: отсутствует WB_API_TOKEN.")
            return []

        url = f"{self.advert_base_url}/adv/v1/promotion/count"
        headers = {"Authorization": self.wb_token}

        try:
            response = self._request_with_retry(
                "GET",
                url,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.HTTPError as exc:
            body = ""
            if exc.response is not None:
                body = exc.response.text
            logger.error(
                "WB /adv/v1/promotion/count HTTP error: %s; body=%s",
                exc,
                body,
            )
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error("WB /adv/v1/promotion/count failed: %s", exc)
            return []

        adverts = response.get("adverts") if isinstance(response, dict) else None
        if not isinstance(adverts, list):
            logger.warning("WB /adv/v1/promotion/count unexpected payload: %s", response)
            return []

        flattened: List[dict[str, Any]] = []
        for block in adverts:
            if not isinstance(block, dict):
                continue
            advert_list = block.get("advert_list")
            if not isinstance(advert_list, list):
                continue
            block_type = block.get("type")
            block_status = block.get("status")
            for entry in advert_list:
                if not isinstance(entry, dict):
                    continue
                advert_id = entry.get("advertId")
                if advert_id is None:
                    continue
                flattened.append(
                    {
                        "advertId": advert_id,
                        "type": block_type,
                        "status": block_status,
                        "changeTime": entry.get("changeTime"),
                    }
                )

        return flattened


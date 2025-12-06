from __future__ import annotations

import datetime as dt
import logging
from typing import List

from wb_bidder_v2.adapters.state_store import (
    get_campaign_ids,
    get_nm_ids,
    state_store,
    update_from_campaigns_api,
)
from wb_bidder_v2.collectors_v2.ads_collector import AdsCollectorV2
from wb_bidder_v2.collectors_v2.sales_funnel_collector import SalesFunnelCollectorV2
from wb_bidder_v2.collectors_v2.search_queries_collector import SearchQueriesCollectorV2
from wb_bidder_v2.wb_api.api_client_v2 import ApiClientV2
from wb_bidder_v2.wb_api.raw.ads_client import AdsRawClient
from wb_bidder_v2.wb_api.raw.sales_funnel_client import SalesFunnelRawClient
from wb_bidder_v2.wb_api.raw.search_report_client import SearchReportRawClient

logger = logging.getLogger(__name__)


def bootstrap_state_from_campaigns() -> bool:
    """
    Ensure the state store knows about existing campaigns/nmIds.
    Returns True if bootstrap performed.
    """
    if get_campaign_ids():
        return False

    client = ApiClientV2()
    campaigns_payload = client.get_campaigns()
    update_from_campaigns_api({"campaigns": campaigns_payload})
    return True


def refresh_raw_data(*, date_from: dt.date, date_to: dt.date) -> None:
    """
    Refresh RAW snapshots for ads, sales-funnel, and search-report using
    campaign/nm lists stored in the state store.
    """
    date_from_str = date_from.isoformat()
    date_to_str = date_to.isoformat()

    campaign_ids = get_campaign_ids()
    nm_ids = get_nm_ids()

    if campaign_ids:
        ads_payload = AdsRawClient.from_env().fetch_fullstats(
            campaign_ids=campaign_ids,
            date_from=date_from_str,
            date_to=date_to_str,
        )
        state_store.update_campaign_mapping(ads_payload)
        # Campaign mapping may have introduced new nmIds
        nm_ids = get_nm_ids()

    if nm_ids:
        SalesFunnelRawClient.from_env().fetch_sales_funnel(
            nm_ids=nm_ids,
            date_from=date_from_str,
            date_to=date_to_str,
        )
        SearchReportRawClient.from_env().fetch_search_report(
            nm_ids=nm_ids,
            date_from=date_from_str,
            date_to=date_to_str,
        )


def collect_full_cycle(*, date_from: dt.date, date_to: dt.date) -> dict[str, list[dict[str, object]]]:
    """
    Full refresh workflow: сначала пытаемся обновить state из кампаний,
    но даже при ошибке WB продолжаем собирать RAW.
    """
    try:
        bootstrap_state_from_campaigns()
    except Exception:
        # Если WB вернул ошибку по /campaigns, не роняем весь цикл,
        # а всё равно обновляем RAW-данные.
        pass
    refresh_raw_data(date_from=date_from, date_to=date_to)
    ads_rows = _safe_collect(
        lambda: AdsCollectorV2.from_env().fetch_ads(
            date_from=date_from,
            date_to=date_to,
            campaign_ids=None,
            nm_ids=None,
            placement=None,
        )
    )
    funnel_rows = _safe_collect(
        lambda: SalesFunnelCollectorV2.from_env().fetch_sales_funnel(
            date_from=date_from,
            date_to=date_to,
            nm_ids=None,
        )
    )
    query_rows = _safe_collect(
        lambda: SearchQueriesCollectorV2.from_env().fetch_search_queries(
            date_from=date_from,
            date_to=date_to,
            nm_ids=None,
            queries=None,
        )
    )
    return {"ads": ads_rows, "funnel": funnel_rows, "queries": query_rows}


def _safe_collect(func):
    try:
        return func()
    except FileNotFoundError:
        logger.warning("collect_full_cycle: RAW snapshot is missing, returning empty dataset.")
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warning("collect_full_cycle: collector failed (%s), returning empty dataset.", exc)
        return []


# Backwards-compatible helpers for existing workflows
def get_controlled_campaign_ids() -> List[int]:
    return get_campaign_ids()


def get_controlled_nm_ids() -> List[int]:
    return get_nm_ids()


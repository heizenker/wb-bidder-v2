from __future__ import annotations

import datetime
import logging
from typing import List, Dict, Any

from wb_bidder_v2.collectors_v2.ads_collector import AdsCollectorV2
from wb_bidder_v2.collectors_v2.sales_funnel_collector import SalesFunnelCollectorV2
from wb_bidder_v2.collectors_v2.search_queries_collector import SearchQueriesCollectorV2
from wb_bidder_v2.config import CONTROLLED_ITEMS, BIDDING_RULES
from wb_bidder_v2.bidder.bidder_v2 import BidderV2
from wb_bidder_v2.backend_v2.backend_v2 import (
    set_bid_command,
    enable_campaign_command,
    disable_campaign_command,
)
from wb_bidder_v2.adapters.state_store import record_command_result, dump_items
from wb_bidder_v2.workflows.utils import (
    bootstrap_state_from_campaigns,
    collect_full_cycle,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def collect_normalized_data(
    *,
    date_from: datetime.date,
    date_to: datetime.date,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    ads = AdsCollectorV2.from_env().fetch_ads(
        date_from=date_from,
        date_to=date_to,
        campaign_ids=None,
        nm_ids=None,
        placement=None,
    )
    funnel = SalesFunnelCollectorV2.from_env().fetch_sales_funnel(
        date_from=date_from,
        date_to=date_to,
        nm_ids=None,
    )
    queries = SearchQueriesCollectorV2.from_env().fetch_search_queries(
        date_from=date_from,
        date_to=date_to,
        nm_ids=None,
        queries=None,
    )
    return ads, funnel, queries


def execute_command(command: Dict[str, Any]) -> bool:
    cmd_type = command.get("type")
    if cmd_type == "set_bid":
        result = set_bid_command(command["campaignId"], command["bid"])
    elif cmd_type == "enable_campaign":
        result = enable_campaign_command(command["campaignId"])
    elif cmd_type == "disable_campaign":
        result = disable_campaign_command(command["campaignId"])
    else:
        logger.warning("Неизвестная команда: %s", command)
        return False

    success = result.get("success", False)
    if success:
        logger.info("Команда %s выполнена успешно: %s", cmd_type, result)
        if cmd_type == "set_bid":
            record_command_result(command["campaignId"], bid=command["bid"])
        elif cmd_type == "enable_campaign":
            record_command_result(command["campaignId"], status="enabled")
        elif cmd_type == "disable_campaign":
            record_command_result(command["campaignId"], status="disabled")
    else:
        logger.error("Команда %s завершилась ошибкой: %s", cmd_type, result)
    return success


def main() -> None:
    logger.info("Старт workflow run_bidder")
    date_to = datetime.date.today()
    date_from = date_to - datetime.timedelta(days=6)

    bootstrap_state_from_campaigns()
    collect_full_cycle(date_from=date_from, date_to=date_to)

    ads, funnel, queries = collect_normalized_data(date_from=date_from, date_to=date_to)

    bidder = BidderV2.from_state(bidding_rules=BIDDING_RULES, defaults=CONTROLLED_ITEMS[0] if CONTROLLED_ITEMS else {})
    commands = bidder.generate_commands(
        normalized_ads=ads,
        sales_funnel=funnel,
        search_queries=queries,
    )

    if not commands:
        logger.info("Команды для исполнения отсутствуют")
        return

    logger.info("Получено команд: %s", len(commands))
    for command in commands:
        execute_command(command)


if __name__ == "__main__":
    main()


from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from wb_bidder_v2.adapters.state_store import dump_items


@dataclass
class ControlledItemConfig:
    """Конфигурация объявления для биддера."""

    nm_id: int
    campaign_ids: List[int]
    name: str
    min_bid: int
    max_bid: int
    base_bid: int
    target_cpo: Optional[float] = None

@dataclass
class ControlledItemState:
    """Промежуточное состояние объявления в рамках расчёта."""

    config: ControlledItemConfig
    stats: Optional[Dict[str, float]] = None
    current_bid: Optional[int] = None
    target_bid: Optional[int] = None


class BidderV2:
    """
    Чистый расчётный слой.

    На вход получает нормализованные данные analytics-слоя и возвращает
    список команд ({type, campaignId, ...}) без побочных эффектов.
    """

    def __init__(
        self,
        items: Sequence[ControlledItemConfig],
        bidding_rules: Dict[str, Any],
    ) -> None:
        self.items: List[ControlledItemConfig] = list(items)
        self.bidding_rules = bidding_rules

    @classmethod
    def from_state(
        cls,
        *,
        bidding_rules: Dict[str, Any],
        defaults: Dict[str, Any],
    ) -> BidderV2:
        """
        Build bidder items dynamically from state_store.
        `defaults` should contain min/max/base bid settings (e.g. from config).
        """
        items: List[ControlledItemConfig] = []
        for entry in dump_items():
            nm_id = entry["nm_id"]
            campaign_ids = entry["campaign_ids"]
            if not campaign_ids:
                continue
            cfg = ControlledItemConfig(
                nm_id=nm_id,
                campaign_ids=campaign_ids,
                name=defaults.get("name_template", "nm_{nm}").format(nm=nm_id),
                min_bid=defaults.get("min_bid", 100),
                max_bid=defaults.get("max_bid", 2000),
                base_bid=defaults.get("base_bid", defaults.get("min_bid", 100)),
                target_cpo=defaults.get("target_cpo"),
            )
            items.append(cfg)
        return cls(items=items, bidding_rules=bidding_rules)

    def generate_commands(
        self,
        normalized_ads: Iterable[Dict[str, Any]],
        sales_funnel: Iterable[Dict[str, Any]] | None = None,
        search_queries: Iterable[Dict[str, Any]] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает список команд на изменение кампаний.
        Пока используется только статистика рекламы, но интерфейс поддерживает
        передачу воронки и поисковых запросов для будущих расширений.
        """
        del sales_funnel, search_queries  # пока не используются

        stats_by_nm = self._aggregate_nm_stats(list(normalized_ads))

        commands: List[Dict[str, Any]] = []
        for item in self.items:
            stats_entry = stats_by_nm.get(item.nm_id)
            state = ControlledItemState(
                config=item,
                stats=stats_entry["metrics"] if stats_entry else None,
                current_bid=self._extract_current_bid(
                    stats_entry["campaign_bids"] if stats_entry else {},
                    item.base_bid,
                ),
            )
            self._compute_target_bid_for_state(state)
            if not state.stats:
                for campaign_id in item.campaign_ids:
                    commands.append({"type": "disable_campaign", "campaignId": campaign_id})
                continue

            for campaign_id in item.campaign_ids:
                commands.append({"type": "enable_campaign", "campaignId": campaign_id})
                campaign_current_bid = None
                if stats_entry:
                    campaign_current_bid = stats_entry["campaign_bids"].get(campaign_id)
                if state.target_bid is None:
                    continue
                if campaign_current_bid is not None and int(campaign_current_bid) == int(state.target_bid):
                    continue
                commands.append(
                    {
                        "type": "set_bid",
                        "campaignId": campaign_id,
                        "bid": int(state.target_bid),
                    }
                )

        return commands

    def _extract_current_bid(self, bids: Dict[int, Any], fallback: int) -> int:
        if not bids:
            return fallback
        for value in bids.values():
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    continue
        return fallback

    def _aggregate_nm_stats(self, ads_rows: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        result: Dict[int, Dict[str, Any]] = {}
        for row in ads_rows:
            nm_value = row.get("nmId") or row.get("nm_id") or row.get("item_id")
            try:
                nm_id = int(nm_value)
            except (TypeError, ValueError):
                continue
            bucket = result.setdefault(
                nm_id,
                {
                    "metrics": {
                        "nm_id": nm_id,
                        "views": 0.0,
                        "clicks": 0.0,
                        "spent": 0.0,
                        "orders": 0.0,
                        "revenue": 0.0,
                    },
                    "campaign_bids": {},
                },
            )
            metrics = bucket["metrics"]
            metrics["views"] += float(row.get("views", 0))
            metrics["clicks"] += float(row.get("clicks", 0))
            metrics["spent"] += float(row.get("spent", row.get("spend", 0)))
            metrics["orders"] += float(row.get("orders", 0))
            metrics["revenue"] += float(row.get("revenue", 0))
            campaign_id = row.get("advertId") or row.get("campaign_id") or row.get("advert_id")
            if campaign_id is not None:
                try:
                    bucket["campaign_bids"][int(campaign_id)] = row.get("current_bid")
                except (TypeError, ValueError):
                    pass
        for entry in result.values():
            metrics = entry["metrics"]
            clicks = metrics["clicks"]
            orders = metrics["orders"]
            spent = metrics["spent"]
            metrics["cpc"] = spent / clicks if clicks > 0 else 0.0
            metrics["cpo"] = spent / orders if orders > 0 else 0.0
        return result

    def _compute_target_bid_for_state(self, state: ControlledItemState) -> None:
        cfg = state.config
        stats = state.stats
        target_cpo = cfg.target_cpo
        if not stats or target_cpo is None:
            state.target_bid = cfg.base_bid
            return

        clicks = stats.get("clicks", 0.0)
        orders = stats.get("orders", 0.0)
        cpo = stats.get("cpo", 0.0)

        min_clicks = self.bidding_rules.get("min_clicks", 20)
        min_orders = self.bidding_rules.get("min_orders", 2)
        step_up_pct = self.bidding_rules.get("step_up_pct", 0.15)
        step_down_pct = self.bidding_rules.get("step_down_pct", 0.15)
        tolerance_pct = self.bidding_rules.get("cpo_tolerance_pct", 0.20)

        if clicks < min_clicks or orders < min_orders:
            state.target_bid = cfg.base_bid
            return

        low_threshold = target_cpo * (1 - tolerance_pct)
        high_threshold = target_cpo * (1 + tolerance_pct)

        current_bid = state.current_bid if state.current_bid is not None else cfg.base_bid

        if cpo < low_threshold:
            new_bid = current_bid * (1.0 + step_up_pct)
        elif cpo > high_threshold:
            new_bid = current_bid * (1.0 - step_down_pct)
        else:
            new_bid = current_bid

        new_bid = int(round(new_bid))
        new_bid = max(cfg.min_bid, min(cfg.max_bid, new_bid))
        state.target_bid = new_bid
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from typing import Iterable, List, Optional

from wb_bidder_v2.collectors_v2.ads_collector import AdsCollectorV2
from wb_bidder_v2.collectors_v2.sales_funnel_collector import SalesFunnelCollectorV2
from wb_bidder_v2.collectors_v2.search_queries_collector import SearchQueriesCollectorV2
from wb_bidder_v2.panel import PanelSnapshot, build_panel_snapshot
from wb_bidder_v2.workflows.utils import (
    collect_full_cycle,
    get_controlled_nm_ids,
)


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WB-BIDDER v2 read-only analytics panel",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Количество дней в окне анализа (>=1). По умолчанию 7.",
    )
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help="Не запускать collect_full_cycle (использовать уже собранный RAW).",
    )
    parser.add_argument(
        "--nm-ids",
        type=str,
        default="",
        help="Список nmId через запятую для фильтрации панели. "
        "Если не задано — используются известные state_store nmId.",
    )
    parser.add_argument(
        "--output",
        choices=("table", "json"),
        default="table",
        help="Формат вывода. table (по умолчанию) или json.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="Ограничить количество отображаемых nmId (0 = без ограничения).",
    )
    return parser.parse_args(argv)


def _parse_nm_ids(raw: str) -> Optional[List[int]]:
    if not raw:
        return None
    result: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = int(part)
        except ValueError:
            raise ValueError(f"Неверный nmId: {part!r}") from None
        if value > 0:
            result.append(value)
    return result or None


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _aggregate_has_values(aggregate: dict) -> bool:
    metric_keys = ("impressions", "clicks", "orders", "spend", "revenue")
    for key in metric_keys:
        if _safe_float(aggregate.get(key)):
            return True
    return False


def _section_has_data(block_data: dict) -> bool:
    rows = block_data.get("rows") or []
    if rows:
        return True
    aggregate = block_data.get("aggregate") or {}
    return _aggregate_has_values(aggregate)


def _format_value(value: object, *, decimals: int | None = None) -> str:
    if value is None:
        return "—"
    try:
        if decimals is not None:
            return f"{float(value):.{decimals}f}"
        return str(int(value))
    except (TypeError, ValueError):
        return "—"


def _format_section(name: str, block_data: dict) -> str:
    aggregate = block_data.get("aggregate") or {}
    rows = block_data.get("rows") or []
    if not rows and not _aggregate_has_values(aggregate):
        return f"{name}: —"

    section_lines = [
        f"{name}: "
        f"impr={_safe_int(aggregate.get('impressions'))} | "
        f"clicks={_safe_int(aggregate.get('clicks'))} | "
        f"orders={_safe_int(aggregate.get('orders'))} | "
        f"spend={_format_value(aggregate.get('spend'), decimals=2)} | "
        f"ctr={_format_value(aggregate.get('ctr'), decimals=2)}% | "
        f"cpo={_format_value(aggregate.get('cpo'), decimals=2)}"
    ]
    if name == "queries":
        top_queries = sorted(
            rows,
            key=lambda row: _safe_int(row.get("orders")),
            reverse=True,
        )[:3]
        for query_row in top_queries:
            section_lines.append(
                f"    • {query_row.get('query', '—')} → "
                f"impr={_safe_int(query_row.get('views') or query_row.get('impressions'))}, "
                f"clicks={_safe_int(query_row.get('clicks'))}, "
                f"orders={_safe_int(query_row.get('orders'))}, "
                f"spent={_safe_float(query_row.get('spent') or query_row.get('spend')):.2f}"
            )
    return "\n".join(section_lines)


def _print_table(snapshot: PanelSnapshot, max_items: int) -> None:
    printable = []
    for item in snapshot.items:
        data = item.as_dict()
        if any(
            (
                _section_has_data(data["ads"]),
                _section_has_data(data["queries"]),
                _section_has_data(data["funnel"]),
            )
        ):
            printable.append(data)

    if not printable:
        print("Нет данных за выбранный период.")
        return

    if max_items > 0:
        printable = printable[:max_items]

    for data in printable:
        print(f"\n=== nmId {data['nm_id']} ===")
        print(_format_section("ads", data["ads"]))
        print(_format_section("queries", data["queries"]))
        print(_format_section("funnel", data["funnel"]))
    print()


def _silence_internal_warnings() -> None:
    logging.basicConfig(level=logging.ERROR)
    logging.getLogger("wb_bidder_v2.collectors_v2.ads_collector").setLevel(logging.ERROR)


def main(argv: Optional[Iterable[str]] = None) -> int:
    _silence_internal_warnings()
    args = _parse_args(argv)
    if args.days < 1:
        print("Ошибка: --days должен быть >= 1", file=sys.stderr)
        return 2

    try:
        nm_ids = _parse_nm_ids(args.nm_ids)
    except ValueError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2

    if nm_ids is None:
        nm_ids = get_controlled_nm_ids() or None

    date_to = dt.date.today()
    date_from = date_to - dt.timedelta(days=args.days - 1)

    if not args.skip_refresh:
        collect_full_cycle(date_from=date_from, date_to=date_to)

    ads_rows = AdsCollectorV2.from_env().fetch_ads(
        date_from=date_from,
        date_to=date_to,
        campaign_ids=None,
        nm_ids=nm_ids,
        placement=None,
    )
    funnel_rows = SalesFunnelCollectorV2.from_env().fetch_sales_funnel(
        date_from=date_from,
        date_to=date_to,
        nm_ids=nm_ids,
    )
    query_rows = SearchQueriesCollectorV2.from_env().fetch_search_queries(
        date_from=date_from,
        date_to=date_to,
        nm_ids=nm_ids,
        queries=None,
    )

    snapshot = build_panel_snapshot(
        ads_rows=ads_rows,
        query_rows=query_rows,
        funnel_rows=funnel_rows,
    )

    if args.output == "json":
        print(json.dumps(snapshot.as_dict(), ensure_ascii=False, indent=2))
    else:
        _print_table(snapshot, args.max_items)
    return 0


if __name__ == "__main__":
    sys.exit(main())


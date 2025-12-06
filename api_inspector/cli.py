from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Iterable

from .client import ApiInspectorClient, ENDPOINTS


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WB API raw inspector",
    )
    subparsers = parser.add_subparsers(dest="command")

    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Число дней для дат (по умолчанию 7).",
    )

    funnel_parser = subparsers.add_parser("funnel", help="Сохранить RAW sales-funnel")
    funnel_parser.add_argument("--days", type=int, default=7)

    queries_parser = subparsers.add_parser("queries", help="Сохранить RAW search-report")
    queries_parser.add_argument("--days", type=int, default=7)

    return parser.parse_args(argv)


def print_block(method: str, url: str, payload: Any) -> None:
    divider = "=" * 10
    print(f"{divider} {method.upper()} {url} {divider}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print()


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    client = ApiInspectorClient()

    if args.command == "funnel":
        data = client.fetch_sales_funnel(days=args.days)
        print_block("GET", "sales-funnel/raw", data)
        return 0

    if args.command == "queries":
        data = client.fetch_search_queries(days=args.days)
        print_block("POST", "search-report/raw", data)
        return 0

    for endpoint in ENDPOINTS:
        method = endpoint["method"]
        url = endpoint["url"]
        try:
            response = client.request(method, url)
            print_block(method, url, response)
        except Exception as exc:  # noqa: BLE001
            print_block(method, url, {"error": str(exc)})

    return 0


if __name__ == "__main__":
    sys.exit(main())

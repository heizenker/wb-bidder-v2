from __future__ import annotations



import argparse

import datetime

import os

from typing import Any, Dict, List, Optional



from wb_bidder_v2.collectors_v2.ads_collector import AdsCollectorV2
from wb_bidder_v2.collectors_v2.search_queries_collector import SearchQueriesCollectorV2
from wb_bidder_v2.collectors_v2.sales_funnel_collector import SalesFunnelCollectorV2
from wb_bidder_v2.analytics.analytics_v2 import CombinedAnalyzerV2
from wb_bidder_v2.core.auth import load_api_base_url
from wb_bidder_v2.config import CONTROLLED_ITEMS





# -------------------------------------------------------------

#   ХЕЛПЕРЫ ФОРМАТИРОВАНИЯ

# -------------------------------------------------------------





def fmt_money(v: float) -> str:

    return f"{v:,.2f}".replace(",", " ").replace(".00", "")





def fmt_int(v: int) -> str:

    return f"{v:,}".replace(",", " ")





def fmt_pct(v: float) -> str:

    return f"{v:.2f}%"





def fmt_roas(v: float) -> str:

    return f"{v:.2f}x"





# -------------------------------------------------------------

#   ПАРСИНГ ПАРАМЕТРОВ ЗАПУСКА

# -------------------------------------------------------------





def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(

        description="WB-Bidder v2 — full_analysis (анализ через новый единый API, без изменения ставок)."

    )



    parser.add_argument(

        "--date-from",

        type=str,

        help="Начальная дата в формате YYYY-MM-DD. По умолчанию 7 дней назад (включительно).",

    )

    parser.add_argument(

        "--date-to",

        type=str,

        help="Конечная дата в формате YYYY-MM-DD. По умолчанию вчера (включительно).",

    )

    parser.add_argument(

        "--nm-ids",

        type=str,

        help="Список nm_id через запятую. Если не указан, берём все, что вернёт API.",

    )



    return parser.parse_args()





def resolve_dates(args: argparse.Namespace) -> tuple[datetime.date, datetime.date]:

    today = datetime.date.today()

    default_to = today - datetime.timedelta(days=1)

    default_from = default_to - datetime.timedelta(days=6)



    if args.date_from:

        date_from = datetime.date.fromisoformat(args.date_from)

    else:

        date_from = default_from



    if args.date_to:

        date_to = datetime.date.fromisoformat(args.date_to)

    else:

        date_to = default_to



    return date_from, date_to





def parse_nm_ids(value: Optional[str]) -> Optional[List[int]]:

    if not value:

        return None

    parts = [p.strip() for p in value.split(",") if p.strip()]

    ids: List[int] = []

    for p in parts:

        try:

            ids.append(int(p))

        except ValueError:

            continue

    return ids or None





# -------------------------------------------------------------

#   ОСНОВНОЙ ПАЙПЛАЙН

# -------------------------------------------------------------





def build_text_report(

    date_from: datetime.date,

    date_to: datetime.date,

    report: Dict[int, Dict[str, Any]],

) -> str:

    lines: List[str] = []



    lines.append("WB-BIDDER v2 — Сводный анализ (новый единый API)")

    lines.append("")

    lines.append(f"Период: {date_from.isoformat()} — {date_to.isoformat()}")

    lines.append("Режим: АНАЛИЗ (ставки НЕ меняются)")

    lines.append("=" * 80)

    lines.append("")



    if not report:

        lines.append("Нет данных от нового API за указанный период.")

        return "\n".join(lines)



    for nm, data in report.items():

        lines.append(f"NM ID: {nm}")

        lines.append("-" * 80)



        # --- Реклама ---

        ads_agg = data["ads"]["agg"]

        lines.append("Реклама (ads):")

        lines.append(

            f"  Показы: {fmt_int(int(ads_agg['impressions']))}, "

            f"Клики: {fmt_int(int(ads_agg['clicks']))}, "

            f"Заказы: {fmt_int(int(ads_agg['orders']))}"

        )

        lines.append(

            f"  Расход: {fmt_money(float(ads_agg['spend']))}, "

            f"Выручка: {fmt_money(float(ads_agg['revenue']))}"

        )

        lines.append(

            "  CTR: {ctr}, CPC: {cpc}, CPO: {cpo}, ROAS: {roas}".format(

                ctr=fmt_pct(float(ads_agg["ctr"])),

                cpc=fmt_money(float(ads_agg["cpc"])),

                cpo=fmt_money(float(ads_agg["cpo"])),

                roas=fmt_roas(float(ads_agg["roas"])),

            )

        )

        lines.append("")



        # --- Поисковые запросы ---

        q_agg = data["queries"]["agg"]

        lines.append("Поисковые запросы (search-queries):")

        lines.append(

            f"  Показы: {fmt_int(int(q_agg['impressions']))}, "

            f"Клики: {fmt_int(int(q_agg['clicks']))}, "

            f"Заказы: {fmt_int(int(q_agg['orders']))}"

        )

        lines.append(

            f"  Расход: {fmt_money(float(q_agg['spend']))}, "

            f"Выручка: {fmt_money(float(q_agg['revenue']))}"

        )

        lines.append(

            "  CTR: {ctr}, CPC: {cpc}, CPO: {cpo}, ROAS: {roas}".format(

                ctr=fmt_pct(float(q_agg["ctr"])),

                cpc=fmt_money(float(q_agg["cpc"])),

                cpo=fmt_money(float(q_agg["cpo"])),

                roas=fmt_roas(float(q_agg["roas"])),

            )

        )

        lines.append("")



        # --- Воронка ---

        f_agg = data["funnel"]["agg"]

        lines.append("Воронка продаж (sales-funnel):")

        lines.append(

            f"  Просмотры карточки: {fmt_int(int(f_agg['impressions']))}, "

            f"Клики: {fmt_int(int(f_agg['clicks']))}, "

            f"Заказы: {fmt_int(int(f_agg['orders']))}"

        )

        lines.append(

            f"  Выручка (по воронке): {fmt_money(float(f_agg['revenue']))}"

        )

        lines.append(

            "  CTR: {ctr}, CR: {cr}, CPO: {cpo}".format(

                ctr=fmt_pct(float(f_agg["ctr"])),

                cr=fmt_pct(float(f_agg["cr"])),

                cpo=fmt_money(float(f_agg["cpo"])),

            )

        )

        lines.append("")

        lines.append("=" * 80)

        lines.append("")



    return "\n".join(lines)





def main() -> None:

    args = parse_args()

    date_from, date_to = resolve_dates(args)

    nm_ids = parse_nm_ids(args.nm_ids)



    # Если новый единый API ещё не подключен — даём внятное сообщение и выходим.

    base_url = (load_api_base_url() or "").strip()

    if not base_url:

        print(

            "WB-BIDDER v2: в .env не задан WB_API_V2_BASE_URL.\n"

            "Новый единый API ещё не подключён.\n"

            "Когда backend будет готов, пропиши строку WB_API_V2_BASE_URL=<url> в .env,\n"

            "например:\n"

            "  WB_API_V2_BASE_URL=https://your-backend/api\n"

            "и перезапусти: python full_analysis.py"

        )

        return



    # Создаём коллекторы v2 (работают через ApiClientV2 и новый единый API)

    ads_collector = AdsCollectorV2.from_env()

    queries_collector = SearchQueriesCollectorV2.from_env()

    funnel_collector = SalesFunnelCollectorV2.from_env()



    analyzer = CombinedAnalyzerV2(

        ads=ads_collector,

        queries=queries_collector,

        funnel=funnel_collector,

    )



    report = analyzer.build_report(date_from, date_to, nm_ids=nm_ids)

    text = build_text_report(date_from, date_to, report)



    # Пишем на экран

    print(text)



    # Сохраняем в файл

    out_path = os.path.join(os.path.dirname(__file__), "full_report.txt")

    with open(out_path, "w", encoding="utf-8") as f:

        f.write(text)





if __name__ == "__main__":

    main()

from wb_bidder_v2.analytics.analytics_v2 import CPOModuleV2





def run_cpo_analysis_v2(collected_data: list[dict]):

    """

    collected_data — список словарей формата:

    {

        "item_id": int,

        "clicks": int,

        "orders": int,

        "spent": float,

        "revenue": float,

        "current_bid": float

    }

    """

    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода в консоль Windows
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("\n=== CPO v2 ANALYSIS (DRY-RUN) ===")



    cpo = CPOModuleV2(

        target_cpo=300.0,     # потом вытащим в config.py

        min_clicks=20,

        min_orders=2,

        step_up_pct=0.15,

        step_down_pct=0.15,

        dry_run=True,         # ставки не отправляем

    )



    decisions = cpo.analyze_many(collected_data)



    for d in decisions:

        print(

            f"[{d['item_id']}] {d['action'].upper()} "

            f"bid: {d['old_bid']} -> {d['new_bid']} | {d['reason']}"

        )



    print("=== END CPO v2 ===\n")



    return decisions



from datetime import datetime, timedelta





def collect_stats_for_cpo(days: int = 7):

    """

    Собирает данные рекламы и воронки продаж за указанный период.

    Возвращает список item_data, готовый для передачи в CPO v2.

    """



    date_to = datetime.utcnow().date()

    date_from = date_to - timedelta(days=days)



    ads_collector = AdsCollectorV2.from_env()

    funnel_collector = SalesFunnelCollectorV2.from_env()



    print(f"\nСбор рекламной статистики за {days} дней...")

    # Извлекаем campaign_id из CONTROLLED_ITEMS (новый формат)
    # Поддерживаем оба формата для обратной совместимости
    campaign_ids = []
    for item in CONTROLLED_ITEMS:
        campaign_id = item.get("campaign_id") or item.get("advert_id")
        if campaign_id:
            campaign_ids.append(campaign_id)

    ads_rows = ads_collector.fetch_ads(

        date_from=date_from,

        date_to=date_to,

        nm_ids=None,

        campaign_ids=campaign_ids if campaign_ids else None,

        placement=None,

    )



    print("Сбор воронки продаж...")

    funnel_rows = funnel_collector.fetch_sales_funnel(

        date_from=date_from,

        date_to=date_to,

        nm_ids=None,

    )



    # Создаём маппинг campaign_id -> item_id из CONTROLLED_ITEMS
    campaign_to_item = {}
    for item in CONTROLLED_ITEMS:
        campaign_id = item.get("campaign_id") or item.get("advert_id")
        item_id = item.get("item_id") or item.get("nm_id")
        if campaign_id and item_id:
            campaign_to_item[campaign_id] = item_id
    
    # Преобразуем в dict по nm_id (или item_id для совместимости)
    ads_map = {}

    for row in ads_rows:
        campaign_id_raw = row.get("campaign_id") or row.get("advertId") or row.get("advert_id")
        campaign_id: Optional[int]
        try:
            campaign_id = int(campaign_id_raw) if campaign_id_raw is not None else None
        except (TypeError, ValueError):
            campaign_id = None
        item_id = row.get("item_id") or row.get("nm_id") or row.get("nmId")

        if not item_id and campaign_id:
            item_id = campaign_to_item.get(campaign_id)

        if not item_id and isinstance(row.get("nms"), list) and row["nms"]:
            first_nm = row["nms"][0]
            if isinstance(first_nm, dict):
                item_id = first_nm.get("nm") or first_nm.get("nmId") or first_nm.get("nm_id")

        if not item_id:
            continue

        clicks = float(row.get("clicks", 0))
        orders = float(row.get("orders", 0))
        spent = float(row.get("spent", row.get("spend", 0)) or 0.0)
        revenue = float(row.get("revenue", 0.0))

        if item_id in ads_map:
            existing = ads_map[item_id]
            existing["clicks"] += clicks
            existing["orders"] += orders
            existing["spent"] += spent
            existing["revenue"] += revenue
            if campaign_id and not existing.get("campaign_id"):
                existing["campaign_id"] = campaign_id
        else:
            ads_map[item_id] = {
                "item_id": item_id,
                "campaign_id": campaign_id,
                "clicks": clicks,
                "orders": orders,
                "spent": spent,
                "revenue": revenue,
                "current_bid": row.get("cpc", 0.0) or row.get("bid", 0.0),
            }

    

    funnel_map = {}

    for row in funnel_rows:

        item_id = row.get("item_id") or row.get("nm_id") or row.get("nmId")

        if item_id:

            funnel_map[item_id] = row



    merged = []



    for item_id, ads in ads_map.items():

        funnel = funnel_map.get(item_id, {})

        orders_value = ads.get("orders", 0)
        if not orders_value:
            orders_value = funnel.get("orders", 0)

        merged.append(

            {

                "item_id": item_id,

                "campaign_id": ads.get("campaign_id"),

                "clicks": ads.get("clicks", 0),

                "orders": orders_value,

                "spent": ads.get("spent", 0.0),

                "revenue": funnel.get("revenue", funnel.get("purchased_revenue", 0.0)),

                "current_bid": ads.get("current_bid", 10.0),

            }

        )



    print(f"Получено {len(merged)} товаров для CPO анализа.")

    return merged


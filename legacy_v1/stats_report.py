import csv
from datetime import date, datetime, timedelta
from collections import defaultdict

STATS_FILE = "stats.csv"      # наш файл со статистикой
DAYS_BACK = 30                # за сколько дней смотреть (можешь менять)

def parse_float(x: str) -> float:
    x = (x or "").strip().replace(" ", "").replace(",", ".")
    if not x:
        return 0.0
    try:
        return float(x)
    except ValueError:
        return 0.0

def parse_int(x: str) -> int:
    x = (x or "").strip().replace(" ", "")
    if not x:
        return 0
    try:
        return int(float(x))
    except ValueError:
        return 0

def read_stats(filename: str, days_back: int):
    """Читаем stats.csv и агрегируем по advert_id за последние N дней."""
    cutoff = date.today() - timedelta(days=days_back)
    data = defaultdict(lambda: {
        "views": 0,
        "clicks": 0,
        "cost": 0.0,
        "orders": 0,
        "revenue": 0.0,
    })

    with open(filename, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader, None)  # пропускаем заголовок

        for row in reader:
            if len(row) < 7:
                continue

            try:
                day = datetime.strptime(row[0], "%Y-%m-%d").date()
            except ValueError:
                # вдруг в начале старый формат, просто пропустим
                continue

            if day < cutoff:
                continue

            advert_id = parse_int(row[1])
            views    = parse_int(row[2])
            clicks   = parse_int(row[3])
            cost     = parse_float(row[4])
            orders   = parse_int(row[5])
            revenue  = parse_float(row[6])

            agg = data[advert_id]
            agg["views"]   += views
            agg["clicks"]  += clicks
            agg["cost"]    += cost
            agg["orders"]  += orders
            agg["revenue"] += revenue

    return data, cutoff

def calc_metrics(agg):
    views   = agg["views"]
    clicks  = agg["clicks"]
    cost    = agg["cost"]
    orders  = agg["orders"]
    revenue = agg["revenue"]

    ctr = (clicks / views * 100) if views > 0 else 0.0
    cr  = (orders / clicks * 100) if clicks > 0 else 0.0
    drr = (cost / revenue * 100) if revenue > 0 else 0.0
    cpo = (cost / orders) if orders > 0 else 0.0

    return ctr, cr, drr, cpo

def print_report(data, cutoff):
    print(f"Сводка по кампаниям за период с {cutoff} по {date.today()} (включительно)\n")
    print("advert_id | показы | клики | расход | заказы | выручка | CPO | DRR% | CTR% | CR%")
    print("-" * 90)

    total = {
        "views": 0, "clicks": 0, "cost": 0.0, "orders": 0, "revenue": 0.0
    }

    for advert_id in sorted(data.keys()):
        agg = data[advert_id]
        ctr, cr, drr, cpo = calc_metrics(agg)

        total["views"]   += agg["views"]
        total["clicks"]  += agg["clicks"]
        total["cost"]    += agg["cost"]
        total["orders"]  += agg["orders"]
        total["revenue"] += agg["revenue"]

        print(
            f"{advert_id:8d} | "
            f"{agg['views']:6d} | "
            f"{agg['clicks']:5d} | "
            f"{agg['cost']:7.0f} | "
            f"{agg['orders']:6d} | "
            f"{agg['revenue']:7.0f} | "
            f"{cpo:6.1f} | "
            f"{drr:5.1f} | "
            f"{ctr:5.1f} | "
            f"{cr:5.1f}"
        )

    # Итоги по всем кампаниям
    print("-" * 90)
    ctr, cr, drr, cpo = calc_metrics(total)
    print(
        f"{'ВСЕ':8} | "
        f"{total['views']:6d} | "
        f"{total['clicks']:5d} | "
        f"{total['cost']:7.0f} | "
        f"{total['orders']:6d} | "
        f"{total['revenue']:7.0f} | "
        f"{cpo:6.1f} | "
        f"{drr:5.1f} | "
        f"{ctr:5.1f} | "
        f"{cr:5.1f}"
    )

if __name__ == "__main__":
    data, cutoff = read_stats(STATS_FILE, DAYS_BACK)
    if not data:
        print("Нет данных в stats.csv за выбранный период.")
    else:
        print_report(data, cutoff)

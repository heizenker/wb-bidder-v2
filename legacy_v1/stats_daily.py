import csv
from datetime import datetime, date, timedelta

STATS_FILE = "stats.csv"
DAYS_BACK = 30   # можно менять

def parse_float(x):
    try:
        return float(x.replace(",", "."))
    except:
        return 0.0

def parse_int(x):
    try:
        return int(float(x))
    except:
        return 0

def read_stats_daily(filename, days_back):
    cutoff = date.today() - timedelta(days=days_back)
    rows = []

    with open(filename, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader, None)

        for row in reader:
            if len(row) < 7:
                continue

            try:
                day = datetime.strptime(row[0], "%Y-%m-%d").date()
            except:
                continue

            if day < cutoff:
                continue

            advert_id = parse_int(row[1])
            views     = parse_int(row[2])
            clicks    = parse_int(row[3])
            cost      = parse_float(row[4])
            orders    = parse_int(row[5])
            revenue   = parse_float(row[6])

            ctr = (clicks / views * 100) if views > 0 else 0
            cr  = (orders / clicks * 100) if clicks > 0 else 0
            drr = (cost / revenue * 100) if revenue > 0 else 0
            cpo = (cost / orders) if orders > 0 else 0

            rows.append([
                str(day),
                advert_id,
                views,
                clicks,
                round(cost, 2),
                orders,
                round(revenue, 2),
                round(cpo, 2),
                round(drr, 2),
                round(ctr, 2),
                round(cr, 2),
            ])

    return rows

def print_daily(rows):
    print("Дата       | advert_id | показы | клики | расход | заказы | выручка | CPO | DRR% | CTR% | CR%")
    print("-" * 110)

    rows.sort(key=lambda r: (r[1], r[0]))  # сортировка: по кампании, затем по дате

    for r in rows:
        print(f"{r[0]} | {r[1]:9} | {r[2]:6} | {r[3]:5} | {r[4]:7} | {r[5]:6} | {r[6]:7} | {r[7]:5} | {r[8]:5} | {r[9]:5} | {r[10]:5}")

if __name__ == "__main__":
    rows = read_stats_daily(STATS_FILE, DAYS_BACK)
    if not rows:
        print("Нет строк за выбранный период.")
    else:
        print_daily(rows)

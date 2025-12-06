import csv
from datetime import datetime, timedelta


def load_stats(filename="stats.csv"):
    """Читаем stats.csv и возвращаем список словарей по дням."""
    data = []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            header = next(reader, None)  # пропускаем заголовок

            for row in reader:
                # Ожидаем формат:
                # 0: date, 1: advert_id, 2: views, 3: clicks,
                # 4: cost, 5: orders, 6: revenue, 7: ctr, 8: cpc, 9: cr
                if len(row) < 7:
                    continue
                try:
                    day = datetime.strptime(row[0], "%Y-%m-%d").date()
                    advert_id = int(row[1])
                    views = int(row[2] or 0)
                    clicks = int(row[3] or 0)
                    cost = float((row[4] or "0").replace(",", "."))
                    orders = int(row[5] or 0)
                    revenue = float((row[6] or "0").replace(",", "."))

                    data.append(
                        {
                            "date": day,
                            "advert_id": advert_id,
                            "views": views,
                            "clicks": clicks,
                            "cost": cost,
                            "orders": orders,
                            "revenue": revenue,
                        }
                    )
                except Exception:
                    # если в строке мусор — просто пропускаем
                    continue
    except FileNotFoundError:
        print("Файл stats.csv не найден. Сначала запусти stats_logger.py.")
    return data


def analyze_last_days(days=7):
    """Берём последние N дней из stats.csv и считаем итоги."""
    data = load_stats()
    if not data:
        print("В stats.csv нет данных.")
        return

    # сортируем по дате и берём последние N записей
    data.sort(key=lambda x: x["date"])
    last_data = data[-days:] if len(data) >= days else data

    total_cost = sum(d["cost"] for d in last_data)
    total_clicks = sum(d["clicks"] for d in last_data)
    total_orders = sum(d["orders"] for d in last_data)

    avg_cpc = total_cost / total_clicks if total_clicks else 0
    avg_cpo = total_cost / total_orders if total_orders else 0

    print(f"\n===== Итоги за последние {len(last_data)} дней =====")
    print(f"Расходы: {round(total_cost, 2)} ₽")
    print(f"Клики: {total_clicks}")
    print(f"Заказы: {total_orders}")
    print(f"Средний CPC: {round(avg_cpc, 2)} ₽")
    print(f"Средний CPO (цена заказа): {round(avg_cpo, 2)} ₽" if total_orders else "Заказов не было")

    print("\n===== По дням =====")
    for d in last_data:
        cpo = d["cost"] / d["orders"] if d["orders"] else 0
        print(
            d["date"].strftime("%Y-%m-%d"),
            f"| клики: {d['clicks']}",
            f"| заказы: {d['orders']}",
            f"| расход: {round(d['cost'], 2)} ₽",
            f"| CPO: {round(cpo, 2)} ₽" if d["orders"] else "| CPO: —",
        )

    print("\n====================================\n")

def get_stats_last_days_by_advert(days=3, filename="stats.csv"):
    """
    Для бидера: берём последние N дней из stats.csv и считаем
    по каждому advert_id сумму кликов, заказов, расхода и выручки.

    Возвращает словарь:
    {
        advert_id: {
            "clicks": ...,
            "orders": ...,
            "cost": ...,
            "revenue": ...,
        },
        ...
    }
    """
    data = load_stats(filename)
    if not data:
        return {}

    # Берём самую свежую дату в файле и отсчитываем days назад
    latest_date = max(d["date"] for d in data)
    cutoff = latest_date - timedelta(days=days - 1)

    # Фильтруем записи по дате
    filtered = [d for d in data if d["date"] >= cutoff]

    stats = {}

    for d in filtered:
        advert_id = d["advert_id"]
        if advert_id not in stats:
            stats[advert_id] = {
                "clicks": 0,
                "orders": 0,
                "cost": 0.0,
                "revenue": 0.0,
            }

        stats[advert_id]["clicks"] += d["clicks"]
        stats[advert_id]["orders"] += d["orders"]
        stats[advert_id]["cost"] += d["cost"]
        stats[advert_id]["revenue"] += d["revenue"]

    return stats

if __name__ == "__main__":
    # можно поменять 7 на 14/30, если хочешь другой период
    analyze_last_days(7)

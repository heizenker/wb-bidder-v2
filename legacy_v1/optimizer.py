import csv
from datetime import datetime
import re

from config import USE_CPO_V2
from wb_bidder.analytics.cpo_optimizer import (
    CPOConfig,
    StatPoint,
    adjust_bid_by_cpo,
)

CONFIG_FILE = "config.py"
STATS_FILE = "stats.csv"

MIN_BID = 400
MAX_BID = 2000

TARGET_CPO = 170     # целевой CPO
DAYS = 3             # анализ последних 3 дней


def load_last_days_stats():
    """Читаем stats.csv и берем последние DAYS дней."""
    data = []

    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            next(reader, None)

            for row in reader:
                try:
                    day = datetime.strptime(row[0], "%Y-%m-%d").date()
                    click_value = (row[3] or "0").replace(",", ".")
                    clicks = int(float(click_value))
                    cost = float(row[4].replace(",", "."))
                    orders = int(row[5])
                    data.append(
                        {
                            "date": day,
                            "clicks": clicks,
                            "cost": cost,
                            "orders": orders,
                        }
                    )
                except:
                    continue

        data.sort(key=lambda x: x["date"])
        return data[-DAYS:]

    except FileNotFoundError:
        print("stats.csv не найден")
        return []


def calculate_avg_cpo(days_data):
    total_cost = sum(d["cost"] for d in days_data)
    total_orders = sum(d["orders"] for d in days_data)
    return total_cost / total_orders if total_orders else 999999


def update_config(target_bid):
    """Обновляем target_bid в config.py"""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = re.sub(
        r"target_bid\s*=\s*\d+",
        f"target_bid = {int(target_bid)}",
        content
    )

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"Новая target_bid = {target_bid}")


def compute_new_bid_cpo_v2(
    *,
    current_bid: float,
    total_clicks: int,
    total_orders: int,
    total_cost: float,
    target_cpo: float,
    min_clicks: int,
    min_orders: int,
    step_up_pct: float,
    step_down_pct: float,
    max_raise_pct: float = 0.5,
    max_cut_pct: float = 0.5,
) -> float:
    """
    Обёртка над adjust_bid_by_cpo из wb_bidder.analytics.cpo_optimizer.

    ВАЖНО:
    - Старая логика ставок остаётся нетронутой.
    - Эта функция пока НЕ используется ботом (будет подключена позже).
    """

    stats = StatPoint(
        clicks=int(total_clicks),
        orders=int(total_orders),
        cost=float(total_cost),
    )

    config = CPOConfig(
        target_cpo=float(target_cpo),
        min_clicks=int(min_clicks),
        min_orders=int(min_orders),
        step_up_pct=float(step_up_pct),
        step_down_pct=float(step_down_pct),
        max_raise_pct=float(max_raise_pct),
        max_cut_pct=float(max_cut_pct),
    )

    new_bid = adjust_bid_by_cpo(
        current_bid=float(current_bid),
        stats_points=[stats],
        config=config,
    )
    return float(new_bid)


def main():
    days = load_last_days_stats()
    if not days:
        print("Нет данных для анализа.")
        return

    avg_cpo = calculate_avg_cpo(days)
    print(f"Средний CPO за {DAYS} дней: {round(avg_cpo, 2)} ₽")

    # Получаем текущий target_bid
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r"target_bid\s*=\s*(\d+)", content)
    target_bid = int(m.group(1)) if m else 800

    # Логика изменения ставки
    if USE_CPO_V2:
        total_clicks = sum(d.get("clicks", 0) for d in days)
        total_orders = sum(d.get("orders", 0) for d in days)
        total_cost = sum(d.get("cost", 0.0) for d in days)

        target_bid = compute_new_bid_cpo_v2(
            current_bid=target_bid,
            total_clicks=total_clicks,
            total_orders=total_orders,
            total_cost=total_cost,
            target_cpo=TARGET_CPO,
            min_clicks=20,
            min_orders=2,
            step_up_pct=0.15,
            step_down_pct=0.15,
        )
    else:
        if avg_cpo < 120:
            target_bid += 100
        elif 120 <= avg_cpo <= 180:
            pass
        elif 180 < avg_cpo <= 250:
            target_bid -= 100
        else:
            target_bid -= 250

    # Ограничиваем ставку рамками
    target_bid = max(MIN_BID, min(MAX_BID, target_bid))

    update_config(target_bid)


if __name__ == "__main__":
    main()

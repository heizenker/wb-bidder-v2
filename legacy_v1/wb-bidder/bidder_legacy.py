import time
import csv
from datetime import datetime, timedelta, date

import requests

from config import CONTROLLED_ITEMS, CHECK_INTERVAL_SEC
from wb_bidder.core.auth import load_token

# ===== КОНСТАНТЫ =====

API_URL = "https://advert-api.wildberries.ru/adv/v0/auction/bids"
STATS_FILE = "stats.csv"
DEFAULT_LOOKBACK_DAYS = 7


def parse_date(date_str: str) -> date:
    """
    Парсим дату из формата YYYY-MM-DD (как в stats.csv).
    """
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def safe_int(value) -> int:
    """
    Безопасное преобразование в int, если пусто или None — 0.
    """
    if value in ("", None):
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def safe_float(value) -> float:
    """
    Безопасное преобразование в float, если пусто или None — 0.0.
    """
    if value in ("", None):
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def load_stats_from_csv(filename: str = STATS_FILE) -> list[dict]:
    """
    Читаем stats.csv и возвращаем список словарей.
    Ожидаем формат строк:
    date;advert_id;views;clicks;cost;orders;revenue;ctr;cpc;cpo
    """
    rows: list[dict] = []

    try:
        with open(filename, "r", encoding="utf-8") as f:
            reader = csv.DictReader(
                f,
                delimiter=";",
                fieldnames=[
                    "date",
                    "advert_id",
                    "views",
                    "clicks",
                    "cost",
                    "orders",
                    "revenue",
                    "ctr",
                    "cpc",
                    "cpo",
                ],
            )
            for row in reader:
                # Пропускаем пустые строки
                if not row["date"]:
                    continue

                rows.append(
                    {
                        "date": parse_date(row["date"]),
                        "advert_id": safe_int(row["advert_id"]),
                        "views": safe_int(row["views"]),
                        "clicks": safe_int(row["clicks"]),
                        "cost": safe_float(row["cost"]),
                        "orders": safe_int(row["orders"]),
                        "revenue": safe_float(row["revenue"]),
                        "ctr": safe_float(row["ctr"]),
                        "cpc": safe_float(row["cpc"]),
                        "cpo": safe_float(row["cpo"]),
                    }
                )
    except FileNotFoundError:
        print(f"[WARN] Файл {filename} не найден, стата не будет.")
    except Exception as e:
        print(f"[ERROR] Ошибка при чтении {filename}: {e}")

    return rows


def aggregate_stats_for_advert(
    rows: list[dict], advert_id: int, days: int = DEFAULT_LOOKBACK_DAYS
) -> dict:
    """
    Агрегируем статистику за последние `days` дней для конкретного advert_id.
    """
    today = date.today()
    cutoff = today - timedelta(days=days - 1)

    total_views = 0
    total_clicks = 0
    total_cost = 0.0
    total_orders = 0
    total_revenue = 0.0

    latest_cpo = None

    for r in rows:
        if r["advert_id"] != advert_id:
            continue
        if r["date"] < cutoff:
            continue

        total_views += r["views"]
        total_clicks += r["clicks"]
        total_cost += r["cost"]
        total_orders += r["orders"]
        total_revenue += r["revenue"]

        # запоминаем последний CPO по дате
        if latest_cpo is None or r["date"] >= cutoff:
            latest_cpo = r["cpo"]

    if total_clicks > 0:
        avg_cpc = total_cost / total_clicks
    else:
        avg_cpc = 0.0

    if total_orders > 0:
        avg_cpo = total_cost / total_orders
    else:
        avg_cpo = 0.0

    return {
        "views": total_views,
        "clicks": total_clicks,
        "cost": total_cost,
        "orders": total_orders,
        "revenue": total_revenue,
        "avg_cpc": avg_cpc,
        "avg_cpo": avg_cpo,
        "latest_cpo": latest_cpo,
    }


def build_items_from_config() -> list[dict]:
    """
    Строим список рекламных объектов (items) из CONTROLLED_ITEMS в config.py.
    """
    items: list[dict] = []
    for entry in CONTROLLED_ITEMS:
        item = {
            "advert_id": entry["advert_id"],
            "name": entry.get("name", f"advert_{entry['advert_id']}"),
            "min_bid": entry["min_bid"],
            "max_bid": entry["max_bid"],
            "base_bid": entry.get("base_bid", entry["min_bid"]),
            "target_cpo": entry.get("target_cpo"),
            "target_bid": entry.get("base_bid", entry["min_bid"]),
        }
        items.append(item)
    return items


def fetch_current_bids(token: str, advert_ids: list[int]) -> dict[int, int]:
    """
    Получаем текущие ставки с WB API для списка advert_ids.
    Возвращаем словарь {advert_id: current_bid}.
    """
    headers = {"Authorization": token}
    payload = {"advertIds": advert_ids}

    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[ERROR] Ошибка при запросе текущих ставок: {e}")
        return {}

    result: dict[int, int] = {}
    for row in data.get("adverts", []):
        aid = row.get("advertId")
        bid = row.get("bid")
        if aid is not None and bid is not None:
            result[int(aid)] = int(bid)
    return result


def apply_current_bids_to_items(items: list[dict], bids: dict[int, int]) -> None:
    """
    Проставляем текущие ставки (current_bid) в items.
    """
    for item in items:
        aid = item["advert_id"]
        if aid in bids:
            item["current_bid"] = bids[aid]
        else:
            item["current_bid"] = item.get("base_bid", item["min_bid"])


def analyze_item_and_update_target_bid(item: dict, stats: dict | None) -> None:
    """
    Обновляем item["target_bid"] на основе CPO и настроек в config.py.
    """
    min_bid = item["min_bid"]
    max_bid = item["max_bid"]
    base_bid = item.get("base_bid", min_bid)
    target_cpo = item.get("target_cpo")  # целевой CPO (руб/заказ)

    current_target = item.get("target_bid", base_bid)

    # Если нет настроек по CPO или нет статы – держим базу
    if not target_cpo or not stats:
        item["target_bid"] = base_bid
        return

    last_cpo = stats.get("cpo")
    if not last_cpo:
        item["target_bid"] = base_bid
        return

    # Допуски относительно целевого CPO
    low_threshold = target_cpo * 0.8   # CPO сильно лучше цели – можно добавить ставку
    high_threshold = target_cpo * 1.2  # CPO хуже цели – надо поджать

    new_target = current_target

    if last_cpo < low_threshold:
        new_target = min(current_target * 1.10, max_bid)
    elif last_cpo > high_threshold:
        new_target = max(current_target * 0.90, min_bid)
    else:
        new_target = current_target

    new_target = int(round(new_target))
    if new_target < min_bid:
        new_target = min_bid
    if new_target > max_bid:
        new_target = max_bid

    item["target_bid"] = new_target

    last_cpo_str = f"{last_cpo:.2f}" if last_cpo is not None else "-"
    print(
        f"[advert {item['advert_id']}] "
        f"target_cpo={target_cpo} | last_cpo={last_cpo_str} | "
        f"target_bid={item['target_bid']}"
    )


# ===== РАСЧЁТ ФАКТИЧЕСКОЙ СТАВКИ (bid) =====


def calc_bid(item: dict) -> int:
    """
    Returns the bid to send to WB, respecting min/max and working hours.
    """
    if is_allowed_time():
        bid = item.get("target_bid", item.get("base_bid", item["min_bid"]))
    else:
        bid = item["min_bid"]

    if bid < item["min_bid"]:
        bid = item["min_bid"]
    if bid > item["max_bid"]:
        bid = item["max_bid"]

    return int(bid)


def is_allowed_time() -> bool:
    """
    Заглушка: здесь можно реализовать логику "рабочих часов".
    Пока всегда True.
    """
    return True


# ===== ФОРМИРОВАНИЕ payload ДЛЯ WB =====


def build_bids_payload(items: list[dict]) -> list[dict]:
    """
    Список ставок для отправки в WB:
    [
      {"advertId": ..., "bid": ...},
      ...
    ]
    """
    payload = []
    for item in items:
        bid = calc_bid(item)
        payload.append({"advertId": item["advert_id"], "bid": bid})
    return payload


def send_bids_to_wb(token: str, bids_payload: list[dict]) -> None:
    """
    Отправляем ставки в WB API.
    """
    headers = {"Authorization": token}
    try:
        resp = requests.post(API_URL, json=bids_payload, headers=headers, timeout=30)
        resp.raise_for_status()
        print(f"[OK] Отправлены ставки для {len(bids_payload)} объявлений.")
    except requests.RequestException as e:
        print(f"[ERROR] Ошибка при отправке ставок: {e}")


# ===== ОСНОВНОЙ ЦИКЛ =====


def one_pass():
    """
    Один проход биддера:
      1. Читаем конфиг
      2. Читаем stats.csv
      3. Для каждого объявления считаем агрегаты
      4. Обновляем target_bid
      5. Формируем bid и отправляем
    """
    print("\n==== НОВЫЙ ПРОХОД ====")
    token = load_token()
    items = build_items_from_config()

    raw_stats = load_stats_from_csv()

    for item in items:
        advert_id = item["advert_id"]
        stats = aggregate_stats_for_advert(raw_stats, advert_id, DEFAULT_LOOKBACK_DAYS)
        cpo = stats.get("avg_cpo", 0.0)

        print(
            f"[advert {advert_id}] views={stats['views']} "
            f"clicks={stats['clicks']} cost={stats['cost']:.2f} "
            f"orders={stats['orders']} avg_cpo={cpo:.2f}"
        )

        analyze_item_and_update_target_bid(item, {"cpo": cpo})

    advert_ids = [item["advert_id"] for item in items]
    current_bids = fetch_current_bids(token, advert_ids)
    apply_current_bids_to_items(items, current_bids)

    bids_payload = build_bids_payload(items)
    send_bids_to_wb(token, bids_payload)


def main_loop():
    print("Автобидер WB запущен.")
    print(f"Интервал проверки: {CHECK_INTERVAL_SEC} секунд.\n")

    while True:
        one_pass()
        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("Остановлено с клавиатуры (Ctrl+C).")
PY\n","explanation":"Create the new bidder_legacy.py file with the provided content."}>>


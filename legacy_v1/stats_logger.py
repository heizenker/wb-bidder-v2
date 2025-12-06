import os
import csv
import time
from datetime import date, timedelta

import requests

from wb_bidder.core.auth import load_token, build_headers
from wb_bidder.collectors.stats_collector import StatRecord


# ===== НАСТРОЙКИ =====


# ID рекламных кампаний, по которым тянем стату
ADVERT_IDS = [29731520, 30467700, 30535614, 30467498, 29709658]


# Сколько дней назад смотреть (для надёжности пока 14, позже можно увеличить)
DAYS_BACK = 14


# Имя файла со статистикой
STATS_FILE = "stats.csv"


def ensure_csv_header() -> None:
    """Создаём stats.csv с заголовком, если его ещё нет."""
    if not os.path.exists(STATS_FILE):
        with open(STATS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(
                [
                    "date",
                    "advert_id",
                    "views",
                    "clicks",
                    "cost",
                    "orders",
                    "revenue",
                    "ctr",
                    "cpc",
                    "cr",
                ]
            )


def fetch_fullstats_for_advert(token: str, advert_id: int):
    """
    Тянем статистику по одной РК через /adv/v3/fullstats.
    Возвращаем «сырой» ответ WB (список кампаний с days внутри).
    """
    end_date = date.today()
    begin_date = end_date - timedelta(days=DAYS_BACK - 1)

    params = {
        "ids": str(advert_id),
        "beginDate": begin_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
    }

    url = "https://advert-api.wildberries.ru/adv/v3/fullstats"
    headers = build_headers(token)

    print(
        f"\nЗапрашиваем статистику {begin_date} — {end_date} по кампании: {advert_id}"
    )

    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
        except Exception as e:
            print("Ошибка при запросе к WB:", repr(e))
            time.sleep(10)
            continue

        print("Код ответа WB:", resp.status_code)

        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception as e:
                print("Не удалось разобрать JSON:", repr(e))
                print("Сырый ответ:", resp.text[:500])
                return []

            # Иногда WB присылает один объект, иногда список — выровняем к списку
            if isinstance(data, dict):
                data = [data]
            return data

        # Лимит запросов
        if resp.status_code == 429:
            print("WB вернул 429 (лимит запросов). Ждём и пробуем ещё раз...")
            time.sleep(60)
            continue

        # Прочие ошибки
        print("Неуспешный статус от WB:", resp.status_code, resp.text[:500])
        time.sleep(10)

    print("Не удалось получить данные по кампании", advert_id)
    return []


def flatten_stats(raw_data):
    """
    Превращаем «сырые» данные WB (список кампаний с days) в плоский список StatRecord.
    """
    flat: list[StatRecord] = []

    for campaign in raw_data:
        advert_id = campaign.get("advertId")
        days = campaign.get("days") or []
        for day in days:
            dt = day.get("date")
            views = day.get("views", 0)
            clicks = day.get("clicks", 0)
            cost = day.get("sum", 0.0)
            orders = day.get("orders", 0)
            revenue = day.get("sum_price", 0.0)

            record = StatRecord(
                date=dt[:10] if isinstance(dt, str) else "",
                advert_id=advert_id,
                views=views,
                clicks=clicks,
                cost=cost,
                orders=orders,
                revenue=revenue,
            )
            flat.append(record)

    return flat


def append_stats(raw_data) -> None:
    """
    Принимает «сырые» данные WB по нескольким РК,
    превращает в StatRecord и пишет в stats.csv.
    """
    ensure_csv_header()

    all_records = flatten_stats(raw_data)

    if not all_records:
        print("Нет данных для записи в CSV.")
        return

    with open(STATS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        for rec in all_records:
            writer.writerow(
                [
                    rec.date,
                    rec.advert_id,
                    rec.views,
                    rec.clicks,
                    rec.cost,
                    rec.orders,
                    rec.revenue,
                    rec.ctr,
                    rec.cpc,
                    rec.cr,
                ]
            )

    print(f"Записано строк в {STATS_FILE}: {len(all_records)}")


def main() -> None:
    token = load_token()

    all_data = []
    for advert_id in ADVERT_IDS:
        data = fetch_fullstats_for_advert(token, advert_id)
        if data:
            all_data.extend(data)

        # Небольшая пауза между кампаниями, чтобы не ловить 429
        time.sleep(2)

    if not all_data:
        print("Не удалось получить ни одной строки статистики.")
    else:
        append_stats(all_data)


if __name__ == "__main__":
    main()

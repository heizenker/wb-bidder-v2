from __future__ import annotations

from datetime import date, timedelta

import requests

from wb_bidder_v2.core.auth import load_token, build_headers

# Базовый endpoint старого рекламного API для fullstats
API_URL = "https://advert-api.wildberries.ru/adv/v3/fullstats"

# ВРЕМЕННО: одна тестовая кампания, чтобы руками проверять ответ WB.
# При необходимости можно подставлять любой другой ID.
ADVERT_ID = 30467498  # авто черные


def build_params(advert_id: int) -> dict[str, str]:
    """Собираем параметры запроса под /adv/v3/fullstats.

    WB ожидает:
    - ids: строка с ID кампании (можно несколько через запятую)
    - beginDate, endDate: YYYY-MM-DD
    """
    end_date = date.today()
    begin_date = end_date - timedelta(days=7)

    return {
        "ids": str(advert_id),
        "beginDate": begin_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
    }


def debug_fullstats(advert_id: int) -> None:
    """Минимальный скрипт для проверки fullstats по одной кампании.

    ВАЖНО:
    - Токен берём через wb_bidder_v2.core.auth.load_token (кавычки срезаются там).
    - В заголовке Authorization передаём сам токен БЕЗ Bearer.
    - Печатаем все ключевые данные, чтобы в случае ошибки сразу увидеть причину.
    """
    token = load_token()
    headers = build_headers(token)
    params = build_params(advert_id)

    print("=== DEBUG FULLSTATS V3 ===")
    print(f"API_URL: {API_URL}")
    print(f"ADVERT_ID: {advert_id}")
    print(f"WB_TOKEN length: {len(token)}")
    print(f"HEADERS: {headers}")
    print(f"PARAMS: {params}")

    resp = requests.get(API_URL, headers=headers, params=params, timeout=30)

    print("HTTP статус:", resp.status_code)
    print("RAW headers от WB:", resp.headers)

    # Пробуем вывести JSON, если это JSON; иначе — текст как есть.
    try:
        data = resp.json()
        print("Ответ WB (JSON):")
        print(data)
    except ValueError:
        print("Ответ WB (TEXT):")
        print(resp.text)


if __name__ == "__main__":
    debug_fullstats(ADVERT_ID)

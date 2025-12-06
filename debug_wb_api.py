"""ШАГ А: Проверка прямого запроса к WB API для получения статистики."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from wb_bidder_v2.core.auth import load_token
from wb_bidder_v2.wb_api.client import WildberriesClient
from wb_bidder_v2.config import CONTROLLED_ITEMS


def get_test_campaign_id():
    """Получить тестовый campaign_id из controlled_items.json или config.py."""
    # Пробуем controlled_items.json
    controlled_file = Path("controlled_items.json")
    if controlled_file.exists():
        try:
            with controlled_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    # Ищем ACTIVE или просто первый
                    for item in data:
                        if item.get("status") == "ACTIVE":
                            return item.get("campaign_id")
                    return data[0].get("campaign_id")
        except Exception as e:
            print(f"Ошибка чтения controlled_items.json: {e}")
    
    # Если не получилось, берём из текущей конфигурации
    if CONTROLLED_ITEMS:
        item = CONTROLLED_ITEMS[0]
        return item.get("advert_id") or item.get("campaign_id")
    
    # Дефолт из debug_fullstats.py
    return 29731520


def test_wb_api_direct():
    """Тестирует прямой запрос к WB API для получения статистики."""
    print("=" * 80)
    print("ШАГ А: Прямой запрос к WB API")
    print("=" * 80)
    
    # Используем WildberriesClient (как в старом коде)
    try:
        client = WildberriesClient.from_env()
        print(f"\n[OK] WildberriesClient создан")
    except Exception as e:
        print(f"\n[ERROR] Не удалось создать WildberriesClient: {e}")
        return None
    
    # Получаем campaign_id
    campaign_id = get_test_campaign_id()
    print(f"\n[INFO] Используем campaign_id: {campaign_id}")
    
    # Формируем даты
    end_date = date.today() - timedelta(days=1)  # Вчера
    begin_date = end_date - timedelta(days=6)     # 7 дней назад (включая вчера)
    
    date_from = begin_date.strftime("%Y-%m-%d")
    date_to = end_date.strftime("%Y-%m-%d")
    
    print(f"\n[INFO] Период: {date_from} - {date_to}")
    
    # Формируем запрос (как в старом коде)
    url = "https://advert-api.wildberries.ru/adv/v3/fullstats"
    params = {
        "ids": str(campaign_id),
        "beginDate": date_from,
        "endDate": date_to,
    }
    
    print(f"\n[REQUEST]")
    print(f"  URL: {url}")
    print(f"  Method: GET")
    print(f"  Params: {params}")
    print(f"  Headers: Authorization: <TOKEN> (скрыт)")
    
    # Используем метод клиента (как в старом коде)
    try:
        data = client.get_campaign_stats(
            advert_ids=[campaign_id],
            date_from=date_from,
            date_to=date_to,
            version="v3"
        )
        
        print(f"\n[RESPONSE]")
        print(f"  Type: {type(data)}")
        print(f"  Direct response from client.get_campaign_stats()")
        
        # Анализируем структуру ответа
        print(f"\n[RESPONSE STRUCTURE]")
        print(f"  Type: {type(data)}")
        
        if isinstance(data, dict):
            print(f"  Keys: {list(data.keys())[:10]}")
            # Проверяем вложенные структуры
            if "adverts" in data:
                adverts = data["adverts"]
                print(f"  adverts type: {type(adverts)}, length: {len(adverts) if isinstance(adverts, list) else 'N/A'}")
            if "data" in data:
                data_part = data["data"]
                print(f"  data type: {type(data_part)}")
        elif isinstance(data, list):
            print(f"  List length: {len(data)}")
            if data:
                print(f"  First item type: {type(data[0])}")
                if isinstance(data[0], dict):
                    print(f"  First item keys: {list(data[0].keys())[:10]}")
        
        # Показываем пример данных (без чувствительной информации)
        print(f"\n[EXAMPLE DATA]")
        if isinstance(data, list) and data:
            example = data[0]
            if isinstance(example, dict):
                # Показываем только безопасные поля
                safe_keys = ["advertId", "id", "date", "days", "type", "status"]
                example_safe = {k: v for k, v in example.items() if k in safe_keys}
                print(f"  First item (safe fields): {json.dumps(example_safe, indent=2, ensure_ascii=False)[:500]}")
        elif isinstance(data, dict):
            # Показываем структуру верхнего уровня
            print(f"  Top-level structure: {json.dumps({k: type(v).__name__ for k, v in list(data.items())[:5]}, indent=2)}")
        
        # Подсчитываем количество записей
        record_count = 0
        if isinstance(data, list):
            record_count = len(data)
        elif isinstance(data, dict):
            if "adverts" in data and isinstance(data["adverts"], list):
                record_count = len(data["adverts"])
            elif "data" in data:
                if isinstance(data["data"], list):
                    record_count = len(data["data"])
                elif isinstance(data["data"], dict) and "stats" in data["data"]:
                    if isinstance(data["data"]["stats"], list):
                        record_count = len(data["data"]["stats"])
        
        print(f"\n[SUMMARY]")
        print(f"  Records found: {record_count}")
        
        if record_count == 0:
            print(f"\n[WARNING] Ответ пустой! Проверяем структуру...")
            if isinstance(data, dict):
                structure = {}
                for k, v in list(data.items())[:10]:
                    if isinstance(v, (dict, list)):
                        v_type = f"{type(v).__name__}({len(v)})"
                    else:
                        v_type = type(v).__name__
                    structure[k] = v_type
                print(f"  Full response structure: {json.dumps(structure, indent=2)}")
            else:
                print(f"  Response is not a dict: {type(data)}")
        else:
            print(f"\n[SUCCESS] Получено {record_count} записей!")
        
        return data
        
    except Exception as e:
        print(f"\n[ERROR] Exception: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = test_wb_api_direct()
    if result:
        print("\n" + "=" * 80)
        print("ШАГ А ЗАВЕРШЁН: WB API вернул данные")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("ШАГ А ПРОВАЛЕН: WB API вернул пустой ответ или ошибку")
        print("=" * 80)


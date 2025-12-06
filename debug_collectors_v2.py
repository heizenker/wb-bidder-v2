"""ШАГ C: Проверка коллекторов v2."""
from __future__ import annotations

from datetime import date, timedelta

from wb_bidder_v2.collectors_v2.ads_collector import AdsCollectorV2
from wb_bidder_v2.core.auth import load_api_base_url
from wb_bidder_v2.config import CONTROLLED_ITEMS


def test_collectors_v2():
    """Тестирует AdsCollectorV2.fetch_ads()."""
    print("=" * 80)
    print("ШАГ C: Проверка коллекторов v2")
    print("=" * 80)
    
    # Показываем текущий базовый URL
    base_url = load_api_base_url()
    print(f"\n[INFO] WB_API_V2_BASE_URL: {base_url}")
    
    # Получаем campaign_id из config.py
    campaign_id = None
    if CONTROLLED_ITEMS:
        item = CONTROLLED_ITEMS[0]
        campaign_id = item.get("advert_id") or item.get("campaign_id")
    if not campaign_id:
        campaign_id = 29731520  # Дефолт
    
    print(f"\n[INFO] Используем campaign_id: {campaign_id}")
    
    # Формируем даты
    date_to = date.today() - timedelta(days=1)
    date_from = date_to - timedelta(days=6)
    
    print(f"\n[INFO] Период: {date_from} - {date_to}")
    
    # Создаём коллектор
    try:
        collector = AdsCollectorV2.from_env()
        print(f"\n[OK] AdsCollectorV2 создан")
    except Exception as e:
        print(f"\n[ERROR] Не удалось создать AdsCollectorV2: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # Вызываем fetch_ads
    print(f"\n[REQUEST] Вызываем fetch_ads...")
    try:
        rows = collector.fetch_ads(
            date_from=date_from,
            date_to=date_to,
            nm_ids=None,
            campaign_ids=[campaign_id],
            placement=None,
        )
        
        print(f"\n[RESPONSE]")
        print(f"  Type: {type(rows)}")
        print(f"  Length: {len(rows)}")
        
        if rows:
            print(f"\n[SUCCESS] Получено {len(rows)} строк!")
            print(f"\n[EXAMPLE] Первая строка (первые 10 ключей):")
            first_row = rows[0]
            if isinstance(first_row, dict):
                for key in list(first_row.keys())[:10]:
                    value = first_row[key]
                    if isinstance(value, (dict, list)):
                        print(f"    {key}: {type(value).__name__}({len(value) if hasattr(value, '__len__') else '?'})")
                    else:
                        print(f"    {key}: {value}")
        else:
            print(f"\n[WARNING] Пустой ответ! Проверяем структуру...")
            # Попробуем получить сырой ответ
            try:
                raw = collector.client.get_ads(params={
                    "date_from": str(date_from),
                    "date_to": str(date_to),
                    "ids": str(campaign_id),
                })
                print(f"  Raw response type: {type(raw)}")
                if isinstance(raw, dict):
                    print(f"  Raw keys: {list(raw.keys())[:10]}")
                    if "wb_raw" in raw:
                        wb_raw = raw["wb_raw"]
                        print(f"  wb_raw type: {type(wb_raw)}")
                        if isinstance(wb_raw, list):
                            print(f"  wb_raw length: {len(wb_raw)}")
                        elif isinstance(wb_raw, dict):
                            print(f"  wb_raw keys: {list(wb_raw.keys())[:10]}")
            except Exception as e:
                print(f"  Error getting raw response: {e}")
        
        return rows
        
    except Exception as e:
        print(f"\n[ERROR] Exception: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = test_collectors_v2()
    if result and len(result) > 0:
        print("\n" + "=" * 80)
        print("ШАГ C ЗАВЕРШЁН: Коллекторы возвращают данные")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("ШАГ C ПРОВАЛЕН: Коллекторы возвращают пустой ответ")
        print("=" * 80)


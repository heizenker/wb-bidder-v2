"""ШАГ D: Проверка полного пути через collect_stats_for_cpo()."""
from __future__ import annotations

import json
from pathlib import Path

from full_analysis import collect_stats_for_cpo
from wb_bidder_v2.config import CONTROLLED_ITEMS


def test_pipeline():
    """Тестирует полный путь от WB API до collect_stats_for_cpo()."""
    print("=" * 80)
    print("ШАГ D: Полный путь через collect_stats_for_cpo()")
    print("=" * 80)
    
    # Получаем тестовый campaign_id
    campaign_id = None
    item_id = None
    
    # Пробуем controlled_items.json
    controlled_file = Path("controlled_items.json")
    if controlled_file.exists():
        try:
            with controlled_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    item = data[0]
                    campaign_id = item.get("campaign_id")
                    item_id = item.get("item_id")
        except Exception as e:
            print(f"[WARNING] Ошибка чтения controlled_items.json: {e}")
    
    # Если не получилось, берём из config.py
    if not campaign_id and CONTROLLED_ITEMS:
        item = CONTROLLED_ITEMS[0]
        campaign_id = item.get("advert_id") or item.get("campaign_id")
        item_id = item.get("nm_id") or item.get("item_id")
    
    if not campaign_id:
        campaign_id = 29731520
        item_id = 265104282
    
    print(f"\n[INFO] Тестовый campaign_id: {campaign_id}")
    print(f"[INFO] Тестовый item_id: {item_id}")
    
    # Проверяем CONTROLLED_ITEMS
    print(f"\n[INFO] CONTROLLED_ITEMS загружен: {len(CONTROLLED_ITEMS)} элементов")
    if CONTROLLED_ITEMS:
        first = CONTROLLED_ITEMS[0]
        print(
            "[INFO] Первый элемент: "
            f"campaign_id={first.get('campaign_id') or first.get('advert_id')}, "
            f"item_id={first.get('item_id') or first.get('nm_id')}"
        )
    
    # Запускаем collect_stats_for_cpo
    print(f"\n[REQUEST] Вызываем collect_stats_for_cpo(days=7)...")
    try:
        items = collect_stats_for_cpo(days=7)
        
        print(f"\n[RESPONSE]")
        print(f"  Type: {type(items)}")
        print(f"  Length: {len(items)}")
        
        if items:
            print(f"\n[SUCCESS] Получено {len(items)} элементов!")
            
            # Фильтруем по тестовому item_id
            filtered = [item for item in items if item.get("item_id") == item_id or item.get("item_id") == campaign_id]
            
            if filtered:
                print(f"\n[INFO] Найдено {len(filtered)} элементов для item_id={item_id}")
                print(f"\n[EXAMPLE] Первый элемент для тестового item_id:")
                example = filtered[0]
                for key in ["item_id", "clicks", "orders", "spent", "revenue", "current_bid"]:
                    if key in example:
                        print(f"    {key}: {example[key]}")
            else:
                print(f"\n[WARNING] Нет элементов для item_id={item_id}")
                print(f"[INFO] Показываем первые 3 элемента:")
                for i, item in enumerate(items[:3]):
                    print(f"  Item {i+1}: item_id={item.get('item_id')}, clicks={item.get('clicks')}, orders={item.get('orders')}, spent={item.get('spent')}")
        else:
            print(f"\n[WARNING] Пустой ответ от collect_stats_for_cpo()!")
            print(f"[INFO] Проверяем, что CONTROLLED_ITEMS не пустой...")
            print(f"  CONTROLLED_ITEMS length: {len(CONTROLLED_ITEMS)}")
            if CONTROLLED_ITEMS:
                print(f"  Первый элемент: {CONTROLLED_ITEMS[0]}")
        
        return items
        
    except Exception as e:
        print(f"\n[ERROR] Exception: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = test_pipeline()
    if result and len(result) > 0:
        print("\n" + "=" * 80)
        print("ШАГ D ЗАВЕРШЁН: collect_stats_for_cpo() возвращает данные")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("ШАГ D ПРОВАЛЕН: collect_stats_for_cpo() возвращает пустой ответ")
        print("=" * 80)


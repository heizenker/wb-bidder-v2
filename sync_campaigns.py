from __future__ import annotations

import json
from pathlib import Path
import requests

from wb_bidder_v2.core.auth import load_api_base_url

# Базовый URL backend_v2
BASE_URL = load_api_base_url().rstrip("/")


def fetch_campaigns(type_: int = 0) -> dict:
    """
    Получить список кампаний из backend_v2.
    
    Args:
        type_: Тип кампании (0 = все, 4 = поиск, 5 = автореклама, 6 = рекомендации)
    
    Returns:
        Словарь с полями: campaigns, item_to_campaign, campaign_to_item, total
    """
    url = f"{BASE_URL}/campaigns"
    params = {"type": type_}
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data


def build_controlled_items(data: dict) -> list[dict]:
    """
    Построить список контролируемых товаров из данных кампаний.
    
    Args:
        data: Словарь от backend_v2 с полями campaigns, campaign_to_item, etc.
    
    Returns:
        Список словарей с полями: item_id, campaign_id, name, type, status
    """
    # Backend_v2 уже нормализует кампании в нужный формат
    campaigns = data.get("campaigns", []) or []
    
    controlled = []
    seen = set()  # Для дедупликации по (item_id, campaign_id)
    
    for camp in campaigns:
        campaign_id = camp.get("campaign_id")
        item_id = camp.get("item_id")
        
        if not campaign_id:
            continue
        
        # Пропускаем кампании без item_id (они не могут быть контролируемыми)
        if not item_id:
            continue
        
        # Дедупликация
        key = (int(item_id), int(campaign_id))
        if key in seen:
            continue
        seen.add(key)
        
        controlled.append({
            "item_id": int(item_id),
            "campaign_id": int(campaign_id),
            "name": camp.get("name", ""),
            "type": camp.get("type"),
            "status": camp.get("status"),
        })
    
    return controlled


if __name__ == "__main__":
    # Получаем данные о кампаниях
    data = fetch_campaigns(type_=0)
    
    # Строим список контролируемых товаров
    controlled = build_controlled_items(data)
    
    # Определяем путь к файлу
    PROJECT_ROOT = Path(__file__).resolve().parent
    CONTROLLED_FILE = PROJECT_ROOT / "controlled_items.json"
    
    # Сохраняем в файл
    with CONTROLLED_FILE.open("w", encoding="utf-8") as f:
        json.dump(controlled, f, ensure_ascii=False, indent=2)
    
    print(f"Saved {len(controlled)} controlled items to {CONTROLLED_FILE}")


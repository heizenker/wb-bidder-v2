"""Сравнение v1 (эталонный fullstats) и v2 (через collect_stats_for_cpo)."""
from __future__ import annotations

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

from requests import HTTPError

from full_analysis import collect_stats_for_cpo
from wb_bidder_v2.collectors_v2.base import BaseCollectorV2
from wb_bidder_v2.collectors_v2.ads_collector import AdsCollectorV2 as AdsCollector
from wb_bidder_v2.wb_api.client import WildberriesClient
from wb_bidder_v2.wb_api.api_client_v2 import ApiClientV2
from wb_bidder_v2.config import CONTROLLED_ITEMS

CLIENT = WildberriesClient.from_env()

MAX_CAMPAIGNS = 5
MIN_ACTIVE = 3
THROTTLED_CAMPAIGNS: set[int] = set()


def ensure_stdout_utf8() -> None:
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


ensure_stdout_utf8()


def load_campaigns() -> List[Dict[str, Any]]:
    campaigns: List[Dict[str, Any]] = []

    controlled_file = Path("controlled_items.json")
    if controlled_file.exists():
        try:
            with controlled_file.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            campaigns.append(item)
        except Exception as exc:
            print(f"[WARNING] Не удалось прочитать controlled_items.json: {exc}")

    for item in CONTROLLED_ITEMS:
        if not isinstance(item, dict):
            continue
        campaign = {
            "campaign_id": item.get("campaign_id") or item.get("advert_id"),
            "item_id": item.get("item_id") or item.get("nm_id"),
            "name": item.get("name", ""),
            "status": item.get("status", "ACTIVE"),
        }
        if campaign["campaign_id"] and campaign["item_id"]:
            if not any(c.get("campaign_id") == campaign["campaign_id"] for c in campaigns):
                campaigns.append(campaign)

    active = [c for c in campaigns if c.get("status") == "ACTIVE"]
    return active or campaigns


def normalize_fullstats(raw: Any) -> List[Dict[str, Any]]:
    campaigns: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        campaigns = [c for c in raw if isinstance(c, dict)]
    elif isinstance(raw, dict):
        campaigns = [raw]
    else:
        return []

    rows: List[Dict[str, Any]] = []
    for campaign in campaigns:
        rows.extend(BaseCollectorV2._normalize_campaign_stats(campaign))
    return rows


def fetch_fullstats_direct(advert_id: int, days: int) -> Tuple[List[Dict[str, Any]], bool]:
    if advert_id in THROTTLED_CAMPAIGNS:
        return [], True
    date_to = date.today()
    date_from = date_to - timedelta(days=days - 1)
    try:
        data = CLIENT.get_campaign_stats(
            advert_ids=[advert_id],
            date_from=date_from.strftime("%Y-%m-%d"),
            date_to=date_to.strftime("%Y-%m-%d"),
            version="v3",
        )
    except HTTPError as exc:
        response = exc.response
        status_code = response.status_code if response else None
        if status_code == 429:
            print(f"[WARNING] Получен 429 для campaign_id={advert_id}. Помечаем кампанию как throttled и ждём 90с.")
            THROTTLED_CAMPAIGNS.add(advert_id)
            time.sleep(90)
            return [], True
        raise

    rows = normalize_fullstats(data)
    filtered = [row for row in rows if not advert_id or row.get("campaign_id") == advert_id]
    time.sleep(4)
    return filtered, False


def aggregate_metrics(rows: List[Dict[str, Any]]) -> Tuple[int, int, float]:
    clicks = sum(int(row.get("clicks", 0)) for row in rows)
    orders = sum(int(row.get("orders", 0)) for row in rows)
    spent = sum(float(row.get("spent", 0.0)) for row in rows)
    return clicks, orders, spent


def build_v2_index(days: int) -> Dict[int, List[Dict[str, Any]]]:
    collected = collect_stats_for_cpo(days=days)
    index: Dict[int, List[Dict[str, Any]]] = {}
    for entry in collected:
        campaign_id = entry.get("campaign_id")
        if campaign_id is None:
            continue
        index.setdefault(int(campaign_id), []).append(entry)
    return index


def aggregate_v2_rows(rows: List[Dict[str, Any]]) -> Tuple[int, int, float]:
    clicks = sum(int(row.get("clicks", 0)) for row in rows)
    orders = sum(int(row.get("orders", 0)) for row in rows)
    spent = sum(float(row.get("spent", 0.0)) for row in rows)
    return clicks, orders, spent


def select_active_campaigns(campaigns: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
    active: List[Dict[str, Any]] = []
    for idx, campaign in enumerate(campaigns, 1):
        campaign_id = campaign.get("campaign_id")
        if not campaign_id:
            continue
        if int(campaign_id) in THROTTLED_CAMPAIGNS:
            print(f"[INFO] campaign_id={campaign_id} пропущена (throttled)")
            continue
        try:
            rows, throttled = fetch_fullstats_direct(int(campaign_id), days)
            if throttled:
                continue
            clicks, _, _ = aggregate_metrics(rows)
            if clicks > 0:
                active.append(campaign)
                print(f"[INFO] campaign_id={campaign_id}: {clicks} clicks - ACTIVE")
            else:
                print(f"[INFO] campaign_id={campaign_id}: 0 clicks - SKIP")
        except HTTPError as exc:
            print(f"[WARNING] Не удалось загрузить campaign_id={campaign_id}: {exc}")
            continue
        if len(active) >= MIN_ACTIVE:
            break
    return active or campaigns[:MAX_CAMPAIGNS]


def compare_campaigns(campaigns: List[Dict[str, Any]], days: int) -> None:
    print("=" * 100)
    print(f"Тестирование {len(campaigns)} кампаний")
    print("=" * 100)
    print()

    v2_index = build_v2_index(days)

    ok_count = 0
    bug_count = 0

    for campaign in campaigns:
        raw_id = campaign.get("campaign_id")
        if raw_id is None:
            continue
        campaign_id = int(raw_id)
        item_id = campaign.get("item_id")
        name = campaign.get("name", "")

        if campaign_id in THROTTLED_CAMPAIGNS:
            print(f"[INFO] campaign_id={campaign_id} пропущена (throttled)")
            continue

        print(f"campaign_id={campaign_id}, item_id={item_id} {name}")

        v1_rows, throttled = fetch_fullstats_direct(campaign_id, days)
        if throttled:
            print(f"[INFO] campaign_id={campaign_id} пропущена из-за throttling")
            continue
        clicks_v1, orders_v1, spent_v1 = aggregate_metrics(v1_rows)
        print(f"  v1: clicks={clicks_v1}, orders={orders_v1}, spent={spent_v1:.2f}")

        v2_rows = v2_index.get(campaign_id, [])
        clicks_v2, orders_v2, spent_v2 = aggregate_v2_rows(v2_rows)
        print(f"  v2: clicks={clicks_v2}, orders={orders_v2}, spent={spent_v2:.2f}")

        if clicks_v1 == 0 and clicks_v2 == 0:
            status = "OK"
        else:
            clicks_diff = abs(clicks_v1 - clicks_v2)
            orders_diff = abs(orders_v1 - orders_v2)
            spent_diff = abs(spent_v1 - spent_v2)
            if clicks_diff <= 2 and orders_diff <= 1 and spent_diff <= 0.01:
                status = "OK"
            else:
                status = "BUG"

        print(f"  status={status}")
        print()

        if status == "OK":
            ok_count += 1
        else:
            bug_count += 1

        time.sleep(4)

    print("=" * 100)
    print(f"OK: {ok_count}")
    print(f"BUG: {bug_count}")
    print("=" * 100)


def main() -> None:
    campaigns = load_campaigns()
    if not campaigns:
        print("[ERROR] Нет кампаний для теста")
        return

    print(f"[INFO] Найдено {len(campaigns)} кампаний")
    selected = select_active_campaigns(campaigns, days=7)[:MAX_CAMPAIGNS]
    print(f"[INFO] Тестируем {len(selected)} кампаний")
    compare_campaigns(selected, days=7)


if __name__ == "__main__":
    main()


def get_test_campaigns(limit: int = 10) -> List[Dict[str, Any]]:
    """Получить список тестовых кампаний из controlled_items.json или конфигурации."""
    campaigns = []
    
    # Пробуем controlled_items.json
    controlled_file = Path("controlled_items.json")
    if controlled_file.exists():
        try:
            with controlled_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    campaigns.extend(data)
        except Exception as e:
            print(f"[WARNING] Ошибка чтения controlled_items.json: {e}")
    
    # Добавляем из конфигурации WB-BIDDER v2
    for item in CONTROLLED_ITEMS:
        campaign = {
            "campaign_id": item.get("advert_id") or item.get("campaign_id"),
            "item_id": item.get("nm_id") or item.get("item_id"),
            "name": item.get("name", ""),
            "type": item.get("type"),
            "status": item.get("status", "ACTIVE"),
        }
        if campaign["campaign_id"] and campaign["item_id"]:
            if not any(c.get("campaign_id") == campaign["campaign_id"] for c in campaigns):
                campaigns.append(campaign)
    
    # Фильтруем по статусу ACTIVE (если есть)
    active = [c for c in campaigns if c.get("status") == "ACTIVE"]
    if active:
        campaigns = active
    
    return campaigns


def filter_active_campaigns(campaigns: List[Dict[str, Any]], days: int = 7, min_clicks: int = 1) -> List[Dict[str, Any]]:
    """
    Отобрать активные кампании, где v1 видит ненулевую активность.
    
    Returns:
        Список кампаний с ненулевыми clicks за период
    """
    print(f"[INFO] Проверка активности {len(campaigns)} кампаний (min_clicks={min_clicks})...")
    active_campaigns = []
    
    client = WildberriesClient.from_env()
    api_client_v2 = ApiClientV2(base_url="http://127.0.0.1:8002")
    collector = AdsCollector(client=api_client_v2)
    date_to = date.today()
    date_from = date_to - timedelta(days=days - 1)
    
    for i, campaign in enumerate(campaigns, 1):
        campaign_id = campaign.get("campaign_id")
        if not campaign_id:
            continue
        
        try:
            # Быстрая проверка активности через v1
            data = collector.collect_campaign_stats(
                campaign_ids=[campaign_id],
                days=days
            )
            
            clicks_sum = sum(row.get("clicks", 0) for row in data)
            
            if clicks_sum >= min_clicks:
                active_campaigns.append(campaign)
                print(f"  [{i}/{len(campaigns)}] campaign_id={campaign_id}: {clicks_sum} clicks - ACTIVE")
            else:
                print(f"  [{i}/{len(campaigns)}] campaign_id={campaign_id}: {clicks_sum} clicks - SKIP")
            
            # Пауза между запросами
            if i < len(campaigns):
                time.sleep(2)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Too Many Requests" in error_str:
                print(f"  [{i}/{len(campaigns)}] campaign_id={campaign_id}: 429 (лимит) - включаем в тест")
                # При 429 включаем в тест (может быть временный лимит)
                active_campaigns.append(campaign)
                # Увеличиваем паузу после 429
                if i < len(campaigns):
                    time.sleep(5)
            else:
                print(f"  [{i}/{len(campaigns)}] campaign_id={campaign_id}: ERROR - {e}")
                # Включаем в тест даже при ошибке (может быть временная проблема)
                active_campaigns.append(campaign)
    
    print(f"[INFO] Отобрано {len(active_campaigns)} активных кампаний")
    return active_campaigns


def test_v1_direct(campaign_id: int, days: int = 7) -> Tuple[int, int, int, float, List[Dict[str, Any]]]:
    """
    Тест прямого запроса в стиле v1 (эталон).
    
    Returns:
        (count, clicks_sum, orders_sum, spent_sum, data) - агрегированные метрики и данные
    """
    try:
        client = WildberriesClient.from_env()
        api_client_v2 = ApiClientV2(base_url="http://127.0.0.1:8002")
        # Старый код использует date.today() как date_to (включая сегодня)
        date_to = date.today()
        date_from = date_to - timedelta(days=days - 1)
        
        # Используем старый коллектор v1
        collector = AdsCollector(client=api_client_v2)
        data = collector.collect_campaign_stats(
            campaign_ids=[campaign_id],
            days=days
        )
        
        # Агрегируем метрики
        clicks_sum = sum(row.get("clicks", 0) for row in data)
        orders_sum = sum(row.get("orders", 0) for row in data)
        spent_sum = sum(row.get("spend", 0.0) for row in data)
        
        return len(data), clicks_sum, orders_sum, spent_sum, data
    except Exception as e:
        print(f"[ERROR v1] Exception: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0, 0, 0.0, []


def test_v2_pipeline(item_id: int, campaign_id: int, days: int = 7) -> Tuple[int, int, int, float, List[Dict[str, Any]]]:
    """
    Тест полного пути v2 через collect_stats_for_cpo().
    
    Returns:
        (count, clicks_sum, orders_sum, spent_sum, data) - агрегированные метрики и данные
    """
    try:
        items = collect_stats_for_cpo(days=days)
        
        # Фильтруем по item_id или campaign_id
        filtered = [
            item for item in items
            if item.get("item_id") == item_id
            or item.get("item_id") == campaign_id
        ]
        
        # Агрегируем метрики
        clicks_sum = sum(item.get("clicks", 0) for item in filtered)
        orders_sum = sum(item.get("orders", 0) for item in filtered)
        spent_sum = sum(item.get("spent", 0.0) for item in filtered)
        
        return len(filtered), clicks_sum, orders_sum, spent_sum, filtered
    except Exception as e:
        print(f"[ERROR v2] Exception: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0, 0, 0.0, []


def compare_campaigns(campaigns: List[Dict[str, Any]], days: int = 7) -> Dict[str, Any]:
    """Сравнить v1 и v2 для списка кампаний."""
    results = []
    ok_count = 0
    bug_count = 0
    bug_campaigns = []
    
    print("=" * 100)
    print(f"Тестирование {len(campaigns)} кампаний")
    print("=" * 100)
    print()
    
    for i, campaign in enumerate(campaigns, 1):
        campaign_id = campaign.get("campaign_id")
        item_id = campaign.get("item_id")
        name = campaign.get("name", "")
        
        if not campaign_id:
            print(f"[{i}/{len(campaigns)}] SKIP: нет campaign_id")
            continue
        
        print(f"[{i}/{len(campaigns)}] Тестируем campaign_id={campaign_id}, item_id={item_id}")
        if name:
            print(f"  Название: {name}")
        
        # Тест v1 (эталон)
        print("  v1 (эталон): запрос...", end=" ", flush=True)
        n_v1, clicks_v1, orders_v1, spent_v1, data_v1 = test_v1_direct(campaign_id, days=days)
        print(f"clicks={clicks_v1}, orders={orders_v1}, spent={spent_v1:.2f}")
        
        # Задержка между запросами (чтобы избежать 429)
        if i < len(campaigns):
            time.sleep(3)
        
        # Тест v2 (полный путь)
        print("  v2 (pipeline): запрос...", end=" ", flush=True)
        n_v2, clicks_v2, orders_v2, spent_v2, data_v2 = test_v2_pipeline(item_id, campaign_id, days=days)
        print(f"clicks={clicks_v2}, orders={orders_v2}, spent={spent_v2:.2f}")
        
        # Задержка перед следующей кампанией
        if i < len(campaigns):
            time.sleep(3)
        
        # Определяем статус на основе сравнения агрегированных сумм
        # Допустимая погрешность: ±2 клика, ±1 заказ, ±0.01 руб
        clicks_diff = abs(clicks_v1 - clicks_v2)
        orders_diff = abs(orders_v1 - orders_v2)
        spent_diff = abs(spent_v1 - spent_v2)
        
        if clicks_v1 == 0 and clicks_v2 == 0:
            status = "OK"  # Обе пустые - WB реально не отдаёт данные
            ok_count += 1
        elif clicks_v1 > 0 and clicks_v2 > 0:
            # Обе видят данные - проверяем совпадение
            if clicks_diff <= 2 and orders_diff <= 1 and spent_diff <= 0.01:
                status = "OK"  # В пределах допустимой погрешности
                ok_count += 1
            else:
                status = "BUG"  # Значения сильно расходятся
                bug_count += 1
                bug_campaigns.append({
                    "campaign_id": campaign_id,
                    "item_id": item_id,
                    "name": name,
                    "v1": {"clicks": clicks_v1, "orders": orders_v1, "spent": spent_v1},
                    "v2": {"clicks": clicks_v2, "orders": orders_v2, "spent": spent_v2},
                    "diff": {"clicks": clicks_diff, "orders": orders_diff, "spent": spent_diff},
                    "data_v1_sample": data_v1[:2] if data_v1 else [],
                    "data_v2_sample": data_v2[:2] if data_v2 else [],
                })
        elif clicks_v1 > 0 and clicks_v2 == 0:
            status = "BUG"  # v1 видит, v2 теряет
            bug_count += 1
            bug_campaigns.append({
                "campaign_id": campaign_id,
                "item_id": item_id,
                "name": name,
                "v1": {"clicks": clicks_v1, "orders": orders_v1, "spent": spent_v1},
                "v2": {"clicks": clicks_v2, "orders": orders_v2, "spent": spent_v2},
                "diff": {"clicks": clicks_diff, "orders": orders_diff, "spent": spent_diff},
                "data_v1_sample": data_v1[:2] if data_v1 else [],
                "data_v2_sample": data_v2[:2] if data_v2 else [],
            })
        else:
            status = "WARN"  # v2 видит, а v1 нет (редкий случай)
            ok_count += 1
        
        # Выводим строку результата
        print(f"  Результат: item_id={item_id}, campaign_id={campaign_id} | "
              f"v1(clicks={clicks_v1}, orders={orders_v1}, spent={spent_v1:.2f}) | "
              f"v2(clicks={clicks_v2}, orders={orders_v2}, spent={spent_v2:.2f}) | "
              f"status={status}")
        if status == "BUG":
            print(f"    DIFF: clicks={clicks_diff}, orders={orders_diff}, spent={spent_diff:.2f}")
        print()
        
        results.append({
            "campaign_id": campaign_id,
            "item_id": item_id,
            "name": name,
            "n_v1": n_v1,
            "n_v2": n_v2,
            "status": status,
        })
    
    # Итоговая сводка
    print("=" * 100)
    print("ИТОГОВАЯ СВОДКА")
    print("=" * 100)
    print(f"Всего кампаний: {len(results)}")
    print(f"OK: {ok_count}")
    print(f"BUG: {bug_count}")
    print(f"WARN: {len(results) - ok_count - bug_count}")
    print()
    
    if bug_campaigns:
        print("Список BUG-кампаний (для отладки):")
        for bug in bug_campaigns:
            print(f"  - campaign_id={bug['campaign_id']}, item_id={bug['item_id']}, name={bug.get('name', '')}")
            print(f"    v1: clicks={bug['v1']['clicks']}, orders={bug['v1']['orders']}, spent={bug['v1']['spent']:.2f}")
            print(f"    v2: clicks={bug['v2']['clicks']}, orders={bug['v2']['orders']}, spent={bug['v2']['spent']:.2f}")
            print(f"    DIFF: clicks={bug['diff']['clicks']}, orders={bug['diff']['orders']}, spent={bug['diff']['spent']:.2f}")
            if bug.get('data_v1_sample'):
                print(f"    Пример данных v1: {json.dumps(bug['data_v1_sample'][0], indent=2, ensure_ascii=False)[:300]}...")
            if bug.get('data_v2_sample'):
                print(f"    Пример данных v2: {json.dumps(bug['data_v2_sample'][0], indent=2, ensure_ascii=False)[:300]}...")
        print()
    
    return {
        "results": results,
        "ok_count": ok_count,
        "bug_count": bug_count,
        "bug_campaigns": bug_campaigns,
    }


if __name__ == "__main__":
    print("=" * 100)
    print("ШАГ C: Проверка нескольких кампаний (v1 vs v2)")
    print("=" * 100)
    print()
    
    # Получаем список кампаний
    all_campaigns = get_test_campaigns()
    
    if not all_campaigns:
        print("[ERROR] Нет кампаний для тестирования!")
        print("Проверьте controlled_items.json и настройки WB-BIDDER v2")
        exit(1)
    
    print(f"[INFO] Найдено {len(all_campaigns)} кампаний")
    print()
    
    # Отбираем активные кампании (где v1 видит данные)
    # Сначала пробуем с min_clicks=1, если нет - используем min_clicks=0
    active_campaigns = filter_active_campaigns(all_campaigns, days=7, min_clicks=1)
    
    if not active_campaigns:
        print("[WARNING] Нет активных кампаний с min_clicks=1, пробуем min_clicks=0...")
        active_campaigns = filter_active_campaigns(all_campaigns, days=7, min_clicks=0)
    
    if not active_campaigns:
        print("[WARNING] Нет кампаний для тестирования, используем все доступные...")
        active_campaigns = all_campaigns
    
    # Ограничиваем количество для теста (чтобы избежать 429)
    test_campaigns = active_campaigns[:5]
    print(f"[INFO] Тестируем {len(test_campaigns)} активных кампаний")
    print()
    
    # Запускаем сравнение
    summary = compare_campaigns(test_campaigns, days=7)
    
    # Финальный статус
    print("=" * 100)
    if summary["bug_count"] == 0:
        print("[SUCCESS] Все кампании работают корректно!")
    else:
        print(f"[WARNING] Обнаружены проблемы: {summary['bug_count']} кампаний требуют отладки")
    print("=" * 100)


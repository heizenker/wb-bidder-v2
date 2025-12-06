from __future__ import annotations

import csv
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from wb_bidder.core.stats_utils import get_stats_path, read_stats_raw

NUM_FIELDS = ("clicks", "impressions", "orders", "cost", "revenue")
KEY_FIELDS = ("date", "advert_id", "query")


def normalize_stats() -> None:
    """
    Нормализует stats.csv:

    - группирует строки по (date, advert_id, query);
    - суммирует числовые поля (clicks, impressions, orders, cost, revenue);
    - перезаписывает stats.csv в агрегированном виде.

    ВАЖНО:
    - это отдельный утилитарный скрипт, который нужно запускать вручную;
    - рабочий код бота (bidder.py, stats_logger.py и т.п.) его НЕ использует.
    """
    path = get_stats_path()
    rows = read_stats_raw()

    if not rows:
        print(f"Файл stats.csv пустой или не найден: {path}")
        return

    grouped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    for row in rows:
        key = tuple(row.get(field, "") for field in KEY_FIELDS)

        if key not in grouped:
            # создаём базовую запись
            base = {field: row.get(field, "") for field in row.keys()}
            # числовые поля инициализируем нулями
            for nf in NUM_FIELDS:
                base[nf] = 0.0
            grouped[key] = base

        agg = grouped[key]

        # суммируем числовые поля
        for nf in NUM_FIELDS:
            raw_val = row.get(nf, "")
            if raw_val is None or raw_val == "":
                continue
            # заменяем запятую на точку и аккуратно конвертируем
            try:
                val = float(str(raw_val).replace(",", "."))
            except ValueError:
                continue
            agg[nf] = float(agg.get(nf, 0.0)) + val

    # подготавливаем список итоговых строк
    normalized_rows: List[Dict[str, Any]] = list(grouped.values())

    # определяем порядок полей по первой записи
    fieldnames = list(rows[0].keys())
    # гарантируем, что числовые поля есть в списке
    for nf in NUM_FIELDS:
        if nf not in fieldnames:
            fieldnames.append(nf)

    # перезаписываем файл
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for r in normalized_rows:
            out = {}
            for field in fieldnames:
                value = r.get(field, "")
                # приводим числовые поля к строке, убираем лишние .0
                if field in NUM_FIELDS and isinstance(value, (int, float)):
                    # cost/revenue оставляем с двумя знаками после запятой,
                    # остальные поля считаем целыми.
                    if field in ("cost", "revenue"):
                        out[field] = f"{float(value):.2f}"
                    else:
                        out[field] = str(int(round(float(value))))
                else:
                    out[field] = value
            writer.writerow(out)

    print(f"Нормализация завершена. Перезаписан файл: {path}")


if __name__ == "__main__":
    normalize_stats()


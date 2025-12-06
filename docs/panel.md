# Read-only панель (вариант B)

## Назначение

Панель предоставляет консольный способ посмотреть итоговую аналитику WB-BIDDER v2 без запуска bidder/backend/workflows. Она использует существующий pipeline RAW → collectors_v2 → analytics (`CombinedAnalyzerV2`) и остаётся read-only (не взаимодействует со state_store, WB API команд и т.п.).

## Как это работает

1. При необходимости вызывается `collect_full_cycle`, который обновляет RAW с помощью registered raw-клиентов.
2. Коллекторы `AdsCollectorV2`, `SalesFunnelCollectorV2`, `SearchQueriesCollectorV2` читают последние RAW-снапшоты.
3. `build_panel_snapshot` из `wb_bidder_v2.panel.calculator` агрегирует строки в единую структуру `PanelSnapshot`, собирая метрики по каждому `nm_id`.
4. CLI (`wb_bidder_v2.panel_cli`) выводит результаты в текстовом или JSON виде.

## Запуск CLI

```bash
python -m wb_bidder_v2.panel_cli --days 7
```

Опции:

- `--skip-refresh` — пропустить `collect_full_cycle`, использовать уже имеющийся RAW.
- `--nm-ids 123,456` — ограничить список артикулов.
- `--output json` — вывести результат в JSON (по умолчанию табличный вывод).
- `--max-items N` — показать только первые N товарных карточек.

## Формат вывода

Командный вывод выглядит так:

```
=== nmId 265104282 ===
ads: impr=1234 | clicks=120 | orders=5 | spend=3800.00 | ctr=9.73% | cpo=760.00
queries: impr=321 | clicks=25 | orders=2 | spend=500.00 | ctr=7.79% | cpo=250.00
    • socks warm → impr=200, clicks=15, orders=1, spent=300.00
funnel: impr=15000 | clicks=4200 | orders=350 | spend=0.00 | ctr=28.00% | cpo=0.00
```

В JSON-режиме возвращается массив `PanelSnapshot.as_dict()`, содержащий блоки `ads/queries/funnel` с полем `rows` (сырые строки) и `aggregate` (суммарные метрики).


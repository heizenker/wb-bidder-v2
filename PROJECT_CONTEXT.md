PROJECT CONTEXT — WB-BIDDER v2 (обновлённый, финальный)
======================================================
1. ЦЕЛЬ ПРОЕКТА

WB-BIDDER v2 — полностью новая система автоматизации рекламы Wildberries.
Система должна:

• Получать данные из одного WB API (ads, sales-funnel, search-report, feedbacks и т.д.).
• Сохранять сырьё в RAW-layer без изменений.
• Нормализовать всё в collectors_v2.
• Строить аналитику CTR/CR/CPC/CPO/ROAS/DRR.
• Автоматически управлять ставками и статусами кампаний с проверкой факта.
• Работать независимо от v1, иметь режимы full_analysis и run_bidder.

2. ПРАВИЛА ДЛЯ РАБОТЫ С ПРОЕКТОМ

• Один запрос → одна команда (для ChatGPT/Cursor).
• Никаких “найди/замени” вручную, всё через Cursor.
• Нельзя смешивать v1 и v2.
• Следуем архитектуре RAW → collectors → analytics → bidder → backend → workflows.

3. КЛЮЧЕВЫЕ ИДЕНТИФИКАТОРЫ

nmId — товар

campaignId — кампания

query — поисковый запрос

feedbackId — отзыв

Все collectors/analytics/bidder должны основываться только на них.

4. RAW-LAYERS (обязательный слой)

RAW должен:

Лежать в /raw/<section>/<timestamp>.json

Сохранять WB-ответы 1:1

Ничего не менять

Позволять REPLAY

Работать как источник данных для всех collectors

RAW-клиенты в wb_bidder_v2/wb_api/raw/*
RAW-store: adapters/storage/raw_store.py

wb_bidder_v2/

Структура:

wb_bidder_v2/
├─ core/
│  ├─ config/         # токены, настройки, rate-limits
│  ├─ logging/        # логирование, метрики, трассировка
│  ├─ utils/          # ретраи, пагинация, анти-DDOS
│  └─ models/         # dataclass/Pydantic модели
├─ wb_api/
│  ├─ auth.py         # токены, ротация токенов
│  ├─ session.py      # HTTP клиент, лимиты, backoff
│  └─ raw/            # зеркала WB API
│     ├─ ads_client.py
│     ├─ sales_funnel_client.py
│     ├─ search_report_client.py
│     ├─ feedbacks_client.py
│     └─ ...
├─ collectors_v2/
│  ├─ ads_collector.py
│  ├─ sales_funnel_collector.py
│  ├─ search_report_collector.py
│  ├─ feedbacks_collector.py
│  └─ base_collector.py
├─ analytics/
│  ├─ aggregations.py
│  ├─ metrics.py        # CTR, CR, CPC, CPO, ROAS, DRR
│  ├─ forecasting.py    # опционально
│  └─ health_checks.py
├─ bidder/
│  ├─ rules_engine.py   # правила ставок
│  ├─ optimizers.py     # расчёт ставок
│  ├─ campaign_controls.py   # on/off с проверкой результата
│  └─ state_store.py
├─ backend_v2/
│  ├─ api_client.py     # команды на WB (set_bid, toggle)
│  ├─ commands.py       # сервисные операции
│  └─ audit.py          # re-check фактического состояния WB
├─ workflows/
│  ├─ full_analysis.py
│  └─ run_bidder.py
├─ adapters/
│  ├─ storage/
│  │  ├─ raw_store.py
│  │  └─ warehouse.py
│  ├─ messaging.py
│  └─ scheduler.py
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ contract/        # тесты против сохранённых RAW-json
└─ docs/
   ├─ architecture.md
   ├─ collectors.md
   └─ bidder_policies.md

### ФАКТИЧЕСКАЯ СТРУКТУРА v2 (текущее состояние)

```
wb_bidder_v2/
├─ config.py
├─ __init__.py
├─ panel_cli.py
├─ adapters/
│  ├─ __init__.py
│  └─ storage/
│     ├─ raw_store.py
│     └─ __init__.py
├─ analytics/
│  ├─ analytics_v2.py
│  ├─ combined_cpo_analysis.py
│  ├─ cpo_optimizer.py
│  ├─ cpo_v2.py
│  ├─ sales_funnel.py
│  ├─ search_funnel_joiner_v2.py
│  ├─ search_queries.py
│  └─ __init__.py
├─ backend_v2/
│  ├─ backend_v2.py
│  └─ __init__.py
├─ bidder/
│  ├─ bidder_v2.py
│  ├─ campaign_controls.py
│  └─ __init__.py
├─ panel/
│  ├─ calculator.py
│  └─ __init__.py
├─ collectors_v2/
│  ├─ ads_collector.py
│  ├─ base.py
│  ├─ sales_funnel_collector.py
│  ├─ search_queries_collector.py   # адаптирован под новую структуру WB (data/groups/items)
│  └─ __init__.py
├─ core/
│  ├─ auth.py
│  ├─ sales_funnel_payload.py
│  ├─ stats_utils.py
│  ├─ __init__.py
│  ├─ config/__init__.py
│  ├─ logging/__init__.py
│  ├─ models/__init__.py
│  └─ utils/__init__.py
├─ tests/
│  ├─ __init__.py
│  └─ fixtures/
│     ├─ api_mock_v2.py
│     └─ __init__.py
├─ wb_api/
│  ├─ api_client_v2.py
│  ├─ client.py
│  ├─ session.py
│  ├─ __init__.py
│  └─ raw/
│     ├─ ads_client.py
│     ├─ feedbacks_client.py
│     ├─ sales_funnel_client.py
│     ├─ search_report_client.py
│     └─ __init__.py
└─ workflows/
   ├─ full_analysis.py
   ├─ run_bidder.py
   ├─ utils.py
   └─ __init__.py
```

```
tests/
├─ test_imports_v2.py
├─ test_panel_calculator.py
├─ __init__.py
└─ contract/
   ├─ test_bidder_commands.py
   ├─ test_collectors_from_raw.py
   └─ __init__.py
```

```
api_inspector/
├─ __init__.py
├─ __main__.py
├─ client.py
└─ cli.py
```

Эталонная структура — целевое будущее.  
Фактическая структура — текущее состояние и будет обновляться по мере выполнения задач в сторону эталона.

Основная логика:

RAW-layer → сырой WB JSON

collectors_v2 → нормализация

analytics → расчёты

bidder → команды (set_bid / enable / disable)

backend_v2 → API + верификация

workflows → orchestration

legacy_v1/ полностью изолирован

6. ВЫПОЛНЕННЫЕ МИЛСТОУНЫ

- Milestone 1–2: структура `wb_bidder_v2`, изоляция `legacy_v1`, перенос всех reusable-модулей.
- Milestone 3: создан RAW-layer (`raw_store`, raw-клиенты, `/raw/*`), collectors полностью читают из RAW.
- Milestone 4: `BidderV2` переведён на чистый расчёт, backend получил команды `set_bid/enable/disable` + verify.
- Milestone 5: добавлен `state_store`, `bootstrap_state_from_campaigns`, workflows используют `collect_full_cycle`, bidder работает через `from_state`.
- Milestone 6: backend `/campaigns` обновляет state, `/state` отдаёт текущее состояние, команды логируют факт через `cache_command_result`.
- Milestone 7: добавлены contract-тесты (`test_state_store_flow`, расширенный `test_collectors_from_raw`), smoke-тест workflow (`test_workflow_cycle`).
- Milestone 8: реализован read-only «калькулятор» (`wb_bidder_v2/panel/*`, `panel_cli.py`, `docs/panel.md`), добавлены unit-тесты `tests/test_panel_calculator.py`.
- Milestone 9: добавлен изолированный инспектор WB API (`api_inspector/*`) для вывода сырых JSON всех используемых эндпоинтов без привязки к bidder/RAW-пайплайну.

7. ТЕКУЩИЕ ПРОБЛЕМЫ/РИСКИ

- История с WB endpoint: `/adv/v0/adverts` и `/adv/v1/campaigns` устарели → заменены на `POST /adv/v0/campaign/search`, но требуется проверка реальных параметров (type/limit/offset).
- Все рабочие сервисы снова используют `/adv/v0/adverts` (через `ApiClientV2`/`WildberriesClient`); важно держать WB токен валидным и следить за лимитами.
- Backend `/campaigns` зависит от прямого вызова WB → при падении WB backend возвращает пустой список (надо рассмотреть кеш).
- `bootstrap_state_from_campaigns` всё ещё полагается на доступность WB; нет внутреннего fallback’а.
- `run_bidder` использует дефолтное правило из первого элемента `CONTROLLED_ITEMS` (в конфиге всё ещё захардкожены min/max/base); нужно вынести правила в config без списков advert_id.
- `generate_commands()` пока игнорирует `sales_funnel/search_queries`, решения принимаются только по рекламе.
- Нет pytest окружения → все тесты запускаются только вручную через smoke-команды.

8. ТЕКУЩЕЕ СОСТОЯНИЕ (коротко)

- RAW → collectors → analytics → bidder → backend → workflows работают, но требуют живого WB API и локального backend.
- `state_store` хранит `campaigns/items/queries`, обновляется из RAW `/ads` и `/campaigns`.
- `workflows` (`full_analysis`, `run_bidder`) перед запуском делают `bootstrap_state` + `collect_full_cycle`; при ошибке `/campaigns` цикл не падает.
- `backend_v2` предоставляет `/health`, `/state`, `/campaigns`, `/raw/*`, `/commands/*`; все команды фиксируются в `state_store`.
- Read-only панель (`panel_cli.py`) использует `collect_full_cycle`, `CombinedAnalyzerV2` и отображает агрегаты по рекламе/воронке/поисковым карточкам (без текста запросов — WB не отдаёт его в текущем API).

9. ТЕСТЫ / SMOKE-ПРОВЕРКИ (ручные)

- `python -c "from wb_bidder_v2.workflows.utils import bootstrap_state_from_campaigns; ..."`
- `python -c "... collect_full_cycle(...)"` — обновляет RAW.
- Коллекторы вручную через `python -c`.
- `python -c "... CombinedAnalyzerV2 ..."` — аналитика по `nmId`.
- `python -c "... BidderV2.from_state(...).generate_commands(...)"`.
- `python wb_bidder_v2/workflows/full_analysis.py`, `python wb_bidder_v2/workflows/run_bidder.py`.
- `python -m wb_bidder_v2.panel_cli --days 7` — read-only отчёт по товарам (таблица или `--output json`).
- `python -m api_inspector` — прямые запросы ко всем WB эндпоинтам с выводом полного сырого JSON.

10. ДОПОЛНИТЕЛЬНЫЕ ШАГИ (рекомендации)

- Вынести правила bidder’а в структуру без `CONTROLLED_ITEMS`.
- Подключить pytest (когда появится окружение).
- Добавить health/metrics, централизованное логирование.
- Доработать bidder: учитывать аналитические данные (funnel/search) и множественные кампании per `nmId`.

11. READ-ONLY ПАНЕЛЬ (вариант B)

- Новые модули: `wb_bidder_v2/panel/calculator.py` (формирует `PanelSnapshot` с помощью `CombinedAnalyzerV2`), `wb_bidder_v2/panel/__init__.py`, CLI `wb_bidder_v2/panel_cli.py`, документация `docs/panel.md`.
- Тестирование: `tests/test_panel_calculator.py` покрывает базовую агрегацию и работу с пустыми входами.
- Назначение: консольный «калькулятор» для быстрой аналитики по ads/queries/funnel без влияния на bidder/backend/state_store.

12. ДАЛЬНЕЙШИЙ ПЛАН

1. **Расширить панель**: добавить вывод дополнительных источников (feedbacks, future metrics) и фильтров (по датам, статусам кампаний).
2. **Интегрировать pytest**: запуск `pytest tests/test_panel_calculator.py` и существующих контрактных тестов в CI, покрыть CLI smoke-тестом.
3. **Доработать bidder/rules**: вынести конфигурацию правил ставок в отдельный модуль, научить `BidderV2.generate_commands()` использовать funnel/search метрики.
4. **Укрепить backend**: кеширование `/campaigns`, улучшение `bootstrap_state_from_campaigns` (fallback из state_store/RAW), health-метрики для read-only панели.
5. **Развивать api_inspector**: периодически синхронизировать набор эндпоинтов с wb_bidder_v2/wb_api/raw, добавлять параметры (date_from/date_to) и примеры ответов в документацию; сохранять свежие RAW (ads/funnel/queries) для панели/тестов.

13. API PROGRESS (ручные проверки)

- **Sales Funnel API**
  - Корректный payload/даты, WB отвечает; инспектор сохраняет RAW (`raw/sales_funnel/*`).
  - `SalesFunnelRawClient` + `sales_funnel_collector` парсят новую структуру (`data.products[].product/statistic`).
  - `panel_cli` отображает воронку по всем доступным `nmId`.

- **Search Queries API**
  - Инспектор сохраняет RAW (`raw/search_report/*`) по новому формату (`data.groups[].items[]`).
  - `search_queries_collector` нормализует карточки (nmId, shows, clicks, orders, ctr, rank) с fallback на legacy; тексты запросов WB не отдаёт, поэтому `query=None`.
  - panel_cli показывает секцию queries с метриками, если RAW успешно собран.

- **Общая система**
  - Реклама + воронка + search cards агрегируются и нормализуются правильно, nmId-маппинг рабочий.
  - `collect_full_cycle` возвращает `{"ads","funnel","queries"}`; panel_cli стабилен даже при частичных данных.

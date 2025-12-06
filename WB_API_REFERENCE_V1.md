# Эталон получения статистики из WB API (v1)

## Получение fullstats рекламы

### Эталонный метод (старый биддер v1)

**Файлы-источники:**
- `stats_logger.py::fetch_fullstats_for_advert()`
- `wb_bidder/collectors/ads_collector.py::collect_campaign_stats()`
- `wb_bidder/core/client.py::get_campaign_stats()`

### Параметры запроса

**URL:** `https://advert-api.wildberries.ru/adv/v3/fullstats`

**Метод:** `GET`

**Query параметры:**
```python
{
    "ids": "29731520,30467700",  # ID кампаний через запятую (строка)
    "beginDate": "2025-11-22",   # Начальная дата (YYYY-MM-DD)
    "endDate": "2025-11-28"      # Конечная дата (YYYY-MM-DD)
}
```

**Headers:**
```python
{
    "Authorization": "<WB_TOKEN>"  # Без Bearer, просто токен
}
```

### Структура ответа WB API

WB API возвращает **список кампаний** (может быть один объект, нормализуется к списку):

```json
[
  {
    "advertId": 29731520,
    "stats": [  // ВАЖНО: поле называется "stats", не "days"!
      {
        "date": "2025-11-25T00:00:00Z",
        "views": 1000,
        "clicks": 120,
        "sum": 345.67,
        "orders": 15
      },
      ...
    ],
    "days": [  // Иногда есть и "days" с более детальной структурой
      {
        "date": "2025-11-25T00:00:00Z",
        "apps": [
          {
            "appType": 32,
            "nms": [
              {
                "nm": 265104282,
                "clicks": 4,
                "orders": 1,
                ...
              }
            ],
            "clicks": 4,
            "orders": 1,
            ...
          }
        ],
        "clicks": 173,
        "orders": 32,
        ...
      }
    ]
  }
]
```

### Нормализация в старом коде

**Файл:** `wb_bidder/collectors/ads_collector.py::_normalize_fullstats()`

**Логика:**
1. Проверяет, что ответ - список
2. Для каждой кампании:
   - Извлекает `advertId`
   - Берет поле **`stats`** (не `days`!)
   - Для каждого дня в `stats`:
     - Создает плоскую запись с полями: `advertId`, `date`, `views`, `clicks`, `spend`, `orders`
     - Вычисляет производные: `cr`, `cpo`

**Важно:**
- Старый код использует поле **`stats`**, а не `days`
- Если `stats` нет или пусто, кампания пропускается
- Дата нормализуется: обрезается до YYYY-MM-DD если есть время

### Обработка ошибок

- **429 (Too Many Requests):** повтор через 40 секунд (до 3 попыток)
- **200:** парсинг JSON, нормализация к списку
- **Другие ошибки:** возврат пустого списка

### Пример успешного запроса

```python
from wb_bidder.core.client import WildberriesClient

client = WildberriesClient.from_env()
data = client.get_campaign_stats(
    advert_ids=[29731520],
    date_from="2025-11-22",
    date_to="2025-11-28",
    version="v3"
)
# data - это список кампаний с полем "stats"
```

### Ключевые отличия от текущего v2

1. **Поле данных:** v1 использует `stats`, v2 пытается использовать `days`
2. **Нормализация:** v1 разворачивает `stats` в плоский массив, v2 разворачивает `days`
3. **Структура:** v1 работает с простой структурой `stats[].date/clicks/orders`, v2 пытается извлечь из `days[].apps[].nms[]`


# Конфиг для WB-BIDDER v2

CONTROLLED_ITEMS = [
    {
        "advert_id": 29731520,      # ID рекламной кампании WB
        "nm_id": 265104282,        # НМ товара
        "placement": "search",     # search или recommendations
        "campaign_type": "search",  # тип кампании: search / auto (автореклама, полки)
        "min_bid": 400,
        "max_bid": 2000,
        "base_bid": 580,
        "target_bid": 580,
        "target_cpo": 160,
        "min_clicks": 20,
        "min_orders": 2,
        "step_up_pct": 0.15,
        "step_down_pct": 0.15,
        "lookback_days": 3,
    },
]

BIDDING_RULES = {
    "min_clicks": 20,
    "min_orders": 2,
    "step_up_pct": 0.15,
    "step_down_pct": 0.15,
    "cpo_tolerance_pct": 0.20,
}

CHECK_INTERVAL_SEC = 300  # раз в 5 минут проход
TIME_SHIFT_HOURS = 3      # локальное смещение относительно сервера
USE_CPO_V2: bool = False


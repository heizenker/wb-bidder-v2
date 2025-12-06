from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass
class CPOConfig:
    """
    Настройки CPO-оптимизации для одного товара / кампании.

    target_cpo: целевой CPO (руб. за заказ)
    min_clicks: минимальное кол-во кликов в окне, чтобы вообще трогать ставку
    min_orders: минимальное кол-во заказов в окне, чтобы считать CPO валидным
    step_up_pct: максимальный шаг увеличения ставки (доля, например 0.15 = +15%)
    step_down_pct: максимальный шаг уменьшения ставки (доля, например 0.15 = -15%)
    max_raise_pct: общий лимит на рост ставки за одно обновление (safety-кеп)
    max_cut_pct: общий лимит на снижение ставки за одно обновление
    """

    target_cpo: float
    min_clicks: int = 20
    min_orders: int = 2
    step_up_pct: float = 0.15
    step_down_pct: float = 0.15
    max_raise_pct: float = 0.5
    max_cut_pct: float = 0.5


@dataclass
class StatPoint:
    """
    Агрегированная статистика за период (обычно уже после фильтрации по lookback_days).

    clicks: клики за период
    orders: заказы за период
    cost: расходы на рекламу за период (в руб.)
    """

    clicks: int
    orders: int
    cost: float


def calculate_cpo(stats: StatPoint) -> Optional[float]:
    """
    Посчитать CPO (стоимость заказа) из агрегированной статистики.

    Возвращает:
        float  — если есть хотя бы один заказ
        None   — если заказов нет (CPO не определён)
    """
    if stats.orders <= 0:
        return None
    if stats.cost <= 0:
        # Формально можно вернуть 0, но для логики оптимизации
        # лучше считать, что CPO неопределён, если расходов нет.
        return None
    return stats.cost / stats.orders


def aggregate_stats(points: Iterable[StatPoint]) -> StatPoint:
    """
    Суммировать несколько StatPoint в один.

    Предполагается, что фильтрация по датам/lookback уже сделана снаружи.
    """
    clicks = 0
    orders = 0
    cost = 0.0
    for p in points:
        clicks += int(p.clicks)
        orders += int(p.orders)
        cost += float(p.cost)
    return StatPoint(clicks=clicks, orders=orders, cost=cost)


def adjust_bid_by_cpo(
    *,
    current_bid: float,
    stats_points: Iterable[StatPoint],
    config: CPOConfig,
) -> float:
    """
    Рассчитать новую ставку на основе CPO.

    Логика:
    1) Агрегируем статистику за окно (stats_points).
    2) Если кликов < min_clicks — НИЧЕГО НЕ ДЕЛАЕМ (возвращаем current_bid).
    3) Если заказов < min_orders — можно мягко повышать ставку (недостаточно данных).
    4) Если есть заказы:
        - считаем фактический CPO = cost / orders;
        - если CPO сильно ниже target → можно снижать ставку;
        - если CPO сильно выше target → повышаем ставку;
        - изменения ограничиваем step_up_pct/step_down_pct и
          доп. кепами max_raise_pct/max_cut_pct.

    ВАЖНО:
    - Функция не знает про lookback_days — считается, что сюда уже передали
      stats_points за нужный период.
    - Никаких сетевых запросов, только математика.
    """

    # Агрегируем окно
    window = aggregate_stats(stats_points)

    # Нет кликов — нет сигнала
    if window.clicks < config.min_clicks:
        return current_bid

    # Нет заказов — данных мало, аккуратно повышаем ставку
    if window.orders < config.min_orders:
        # Мягкий шаг вверх: половина от step_up_pct
        raw_step = config.step_up_pct * 0.5
        factor = 1.0 + raw_step
        # Ограничиваем общим лимитом роста
        max_factor = 1.0 + config.max_raise_pct
        factor = min(factor, max_factor)
        return max(current_bid * factor, 0.0)

    # Есть заказы → считаем CPO
    cpo = calculate_cpo(window)
    if cpo is None:
        # На всякий случай, если что-то пошло не так
        return current_bid

    # Относительное отклонение фактического CPO от целевого
    if config.target_cpo <= 0:
        # Без целевого CPO нечего оптимизировать
        return current_bid

    deviation = (cpo - config.target_cpo) / config.target_cpo

    # Если фактический CPO примерно в коридоре [-10%; +10%] к таргету — ставку не трогаем
    if -0.10 <= deviation <= 0.10:
        return current_bid

    # Если CPO сильно лучше таргета (ниже) — можно снижать ставку
    if deviation < 0:
        # чем сильнее ниже таргета, тем ближе к step_down_pct
        severity = min(abs(deviation), 1.0)  # 0..1
        raw_step = config.step_down_pct * severity
        factor = 1.0 - raw_step
        min_factor = 1.0 - config.max_cut_pct
        if factor < min_factor:
            factor = min_factor
        new_bid = current_bid * factor
        return max(new_bid, 0.0)

    # deviation > 0 → CPO хуже таргета, повышаем ставку
    severity = min(deviation, 1.0)  # 0..1
    raw_step = config.step_up_pct * severity
    factor = 1.0 + raw_step
    max_factor = 1.0 + config.max_raise_pct
    if factor > max_factor:
        factor = max_factor
    new_bid = current_bid * factor
    return max(new_bid, 0.0)

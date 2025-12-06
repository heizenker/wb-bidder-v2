from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from wb_bidder.core.client import WildberriesClient
from wb_bidder.core.stats_utils import read_stats_raw, append_stats_rows


@dataclass
class StatRecord:
    date: str
    advert_id: int
    views: int
    clicks: int
    cost: float
    orders: int
    revenue: float

    @property
    def ctr(self) -> float:
        if self.views == 0:
            return 0.0
        return round(self.clicks / self.views * 100, 2)

    @property
    def cpc(self) -> float:
        if self.clicks == 0:
            return 0.0
        return round(self.cost / self.clicks, 2)

    @property
    def cr(self) -> float:
        if self.clicks == 0:
            return 0.0
        return round(self.orders / self.clicks * 100, 2)


class StatsCollector:
    """
    Сборщик и писатель статистики.

    ВАЖНО: на этом шаге это только скелет.
    - Мы НЕ трогаем текущую логику stats_logger/stats_daily.
    - Ни один существующий модуль пока не использует StatsCollector.
    """

    def __init__(self, client: WildberriesClient | None = None) -> None:
        self.client = client  # клиент может быть None, пока мы не делаем реальные запросы

    # ==== ЧТЕНИЕ СТАРОЙ STATS.CSV ====

    def load_raw_stats(self) -> list[dict[str, str]]:
        """
        Загрузить текущий stats.csv в виде сырых строк.

        Пока просто проксируем вызов read_stats_raw(), чтобы не дублировать логику.
        """
        return read_stats_raw()

    # ==== БУДУЩАЯ ИНТЕГРАЦИЯ С API ====

    def fetch_latest_stats_from_api(self) -> list[StatRecord]:
        """
        В будущем: запросить свежую статистику из WB API и вернуть
        нормализованный список StatRecord.

        Сейчас: заглушка, возвращает пустой список.
        """
        # client может быть None — на этом этапе мы не делаем реальных запросов.
        _ = self.client
        return []

    def append_stats(self, records: Iterable[StatRecord]) -> None:
        """
        Добавить новые записи в stats.csv.

        Сейчас: конвертируем StatRecord в dict и используем append_stats_rows().
        """
        rows: list[dict[str, Any]] = []

        for r in records:
            rows.append(
                {
                    "date": r.date,
                    "advert_id": r.advert_id,
                    "views": r.views,
                    "clicks": r.clicks,
                    "cost": r.cost,
                    "orders": r.orders,
                    "revenue": r.revenue,
                    "ctr": r.ctr,
                    "cpc": r.cpc,
                    "cr": r.cr,
                }
            )

        if rows:
            append_stats_rows(rows)

    def append_stats_deduped(
        self,
        records: Iterable[StatRecord],
        key_fields: tuple[str, ...] = ("date", "advert_id"),
    ) -> None:
        """
        Добавить записи в stats.csv, избегая точных дублей по ключу key_fields.

        Логика:
        - читаем существующий stats.csv через read_stats_raw();
        - строим множество ключей (date, advert_id, query) для уже существующих строк;
        - конвертируем новые StatRecord в dict;
        - отфильтровываем те, у которых ключ уже есть в файле;
        - записываем только новые строки через append_stats_rows().

        ВАЖНО:
        - формат строк (имена полей) должен совпадать с тем, что использует append_stats().
        - этот метод пока НИГДЕ не вызывается в старом коде. Подключим его позже.
        """
        existing = read_stats_raw()
        existing_keys: set[tuple[str, ...]] = set()

        for row in existing:
            key: list[str] = []
            for field in key_fields:
                key.append(row.get(field, ""))
            existing_keys.add(tuple(key))

        new_dicts: list[dict[str, Any]] = []
        for r in records:
            row = {
                "date": r.date,
                "advert_id": r.advert_id,
                "views": r.views,
                "clicks": r.clicks,
                "cost": r.cost,
                "orders": r.orders,
                "revenue": r.revenue,
                "ctr": r.ctr,
                "cpc": r.cpc,
                "cr": r.cr,
            }

            key = tuple(str(row.get(field, "")) for field in key_fields)
            if key in existing_keys:
                continue

            existing_keys.add(key)
            new_dicts.append(row)

        if new_dicts:
            append_stats_rows(new_dicts)


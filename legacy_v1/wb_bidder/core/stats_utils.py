from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Mapping, Final

# Путь к основному файлу статистики бота.
# Сейчас в проекте уже используется stats.csv в корне, поэтому
# просто централизуем путь здесь.
STATS_FILE_NAME: Final[str] = "stats.csv"


def get_stats_path() -> Path:
    """
    Вернуть Path до файла stats.csv.

    Пока считаем, что файл лежит в корне проекта (как и сейчас).
    Если позже решим менять структуру — правим только здесь.
    """
    return Path(STATS_FILE_NAME)


def read_stats_raw() -> list[dict[str, str]]:
    """
    Считать stats.csv как список словарей (сырые строки).

    НИКАК не меняет существующий код: это просто новый хелпер,
    который позже можно будет использовать вместо дублирующего кода.
    """
    path = get_stats_path()
    if not path.exists():
        return []

    rows: list[dict[str, str]] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def append_stats_rows(rows: Iterable[Mapping[str, Any]]) -> None:
    """
    Добавить одну или несколько строк в stats.csv.

    - Если файл пустой или не существует, заголовки берём из ключей первой строки.
    - Значения приводим к str.
    - Никакой дедупликации здесь пока нет — она будет реализована позже
      поверх этих хелперов (например, в collectors/stats_collector.py).
    """
    rows = list(rows)
    if not rows:
        return

    path = get_stats_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Преобразуем значения к строкам
    normalized: list[dict[str, str]] = []
    for row in rows:
        normalized.append({k: str(v) for k, v in row.items()})

    file_exists = path.exists() and path.stat().st_size > 0

    fieldnames = list(normalized[0].keys())
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(normalized)


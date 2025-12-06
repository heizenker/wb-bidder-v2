from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
from collections import defaultdict


# --- helpers ---------------------------------------------------------------


def _to_int(value: Any) -> int:
    """Аккуратно переводим любое значение в int (учитывая пробелы, запятые и т.п.)."""
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    # убираем пробелы-разделители тысяч и символ "₽"
    s = s.replace(" ", "").replace("₽", "")
    s = s.replace(",", ".")
    try:
        return int(float(s))
    except ValueError:
        return 0


def _to_float(value: Any) -> float:
    """Аккуратно переводим значение в float."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    s = s.replace(" ", "").replace("₽", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _get(row: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Универсальный getter: пробуем несколько ключей (английские/русские),
    возвращаем первое найденное значение.
    """
    for k in keys:
        if k in row:
            return row[k]
    return default


# --- dataclass c агрегированными метриками по артикулу ---------------------


@dataclass
class SalesFunnelStats:
    """
    Агрегированные метрики воронки продаж по одному артикулу WB (nm_id).

    Эти поля максимально привязаны к структуре отчёта 12ва1а:
    - "Артикул WB"
    - "Показы"
    - "Переходы в карточку"
    - "Положили в корзину"
    - "Заказали, шт"
    - "Выкупили, шт"
    - "Заказали на сумму, ₽"
    - "Выкупили на сумму, ₽"
    и т.д.
    """

    article_id: int  # Артикул WB / nmId
    supplier_article: Optional[str]  # Артикул продавца
    name: Optional[str]  # Название
    brand: Optional[str]  # Бренд
    subject: Optional[str]  # Предмет

    shows: int  # Показы
    detail_views: int  # Переходы в карточку
    add_to_cart: int  # Положили в корзину
    orders: int  # Заказали, шт
    buyouts: int  # Выкупили, шт

    revenue_orders: float  # Заказали на сумму, ₽
    revenue_buyouts: float  # Выкупили на сумму, ₽

    avg_price: float  # Средняя цена, ₽ (если есть в отчёте)

    def ctr(self) -> float:
        """CTR = Переходы в карточку / Показы * 100."""
        if self.shows <= 0:
            return 0.0
        return self.detail_views * 100.0 / float(self.shows)

    def cr_to_cart(self) -> float:
        """CR в корзину = Положили в корзину / Переходы * 100."""
        if self.detail_views <= 0:
            return 0.0
        return self.add_to_cart * 100.0 / float(self.detail_views)

    def cr_to_order_from_views(self) -> float:
        """CR в заказ от показов = Заказали / Показы * 100."""
        if self.shows <= 0:
            return 0.0
        return self.orders * 100.0 / float(self.shows)

    def cr_to_order_from_clicks(self) -> float:
        """CR в заказ от переходов = Заказали / Переходы * 100."""
        if self.detail_views <= 0:
            return 0.0
        return self.orders * 100.0 / float(self.detail_views)

    def buyout_rate(self) -> float:
        """Доля выкупа = Выкупили / Заказали * 100."""
        if self.orders <= 0:
            return 0.0
        return self.buyouts * 100.0 / float(self.orders)

    def aov(self) -> float:
        """Средний чек по заказам = выручка / заказанные штуки."""
        if self.orders <= 0:
            return 0.0
        return self.revenue_orders / float(self.orders)


# --- основная функция нормализации/агрегации -------------------------------


def aggregate_sales_funnel(rows: Iterable[Dict[str, Any]]) -> List[SalesFunnelStats]:
    """
    Превратить сырые строки воронки продаж (12ва1а) в агрегированную таблицу по артикулу.

    ВАЖНО:
    - Функция НЕ читает XLSX и НЕ ходит в API.
      Она принимает уже собранные "строки" (dict) — это задача коллектора
      (SalesFunnelCollector).
    - Мы только аккуратно приводим числа и считаем агрегаты.

    Ожидаемые ключи в row (минимум):
    - Артикул WB      / "article_id" / "nmId"
    - Артикул продавца / "supplierArticle"
    - Название         / "name"
    - Предмет          / "subject"
    - Бренд            / "brand"

    - Показы                          / "shows"
    - Переходы в карточку             / "detailViews"
    - Положили в корзину              / "addToCart"
    - Заказали, шт                    / "orders"
    - Выкупили, шт                    / "buyouts"
    - Заказали на сумму, ₽            / "ordersRevenue"
    - Выкупили на сумму, ₽            / "buyoutsRevenue"
    - Средняя цена, ₽                 / "avgPrice"
    """

    # Группируем по article_id, т.к. коллектора может отдавать несколько строк
    # по датам / источникам трафика.
    acc: dict[int, Dict[str, Any]] = defaultdict(
        lambda: {
            "supplier_article": None,
            "name": None,
            "brand": None,
            "subject": None,
            "shows": 0,
            "detail_views": 0,
            "add_to_cart": 0,
            "orders": 0,
            "buyouts": 0,
            "revenue_orders": 0.0,
            "revenue_buyouts": 0.0,
            "avg_price_sum": 0.0,
            "avg_price_count": 0,
        }
    )

    for row in rows:
        article_raw = _get(
            row,
            "article_id",
            "nmId",
            "nm_id",
            "nm",
            "Артикул WB",
        )
        article_id = _to_int(article_raw)
        if article_id <= 0:
            # строка без артикулу WB нам неинтересна
            continue

        bucket = acc[article_id]

        # базовая инфа по карточке сохраняем "как есть", если уже есть — не затираем
        if bucket["supplier_article"] is None:
            bucket["supplier_article"] = _get(
                row, "supplier_article", "Артикул продавца"
            )
        if bucket["name"] is None:
            bucket["name"] = _get(row, "name", "Название")
        if bucket["brand"] is None:
            bucket["brand"] = _get(row, "brand", "Бренд")
        if bucket["subject"] is None:
            bucket["subject"] = _get(row, "subject", "Предмет")

        # числовые поля: суммируем
        bucket["shows"] += _to_int(_get(row, "shows", "Показы"))
        bucket["detail_views"] += _to_int(
            _get(row, "detail_views", "Переходы в карточку")
        )
        bucket["add_to_cart"] += _to_int(
            _get(row, "add_to_cart", "Положили в корзину")
        )
        bucket["orders"] += _to_int(_get(row, "orders", "Заказали, шт"))
        bucket["buyouts"] += _to_int(_get(row, "buyouts", "Выкупили, шт"))

        bucket["revenue_orders"] += _to_float(
            _get(row, "orders_revenue", "Заказали на сумму, ₽")
        )
        bucket["revenue_buyouts"] += _to_float(
            _get(row, "buyouts_revenue", "Выкупили на сумму, ₽")
        )

        avg_price_val = _get(row, "avg_price", "Средняя цена, ₽")
        if avg_price_val not in (None, ""):
            bucket["avg_price_sum"] += _to_float(avg_price_val)
            bucket["avg_price_count"] += 1

    # превращаем агрегированные словари в dataclass'ы
    result: List[SalesFunnelStats] = []

    for article_id, b in acc.items():
        if b["avg_price_count"] > 0:
            avg_price = b["avg_price_sum"] / float(b["avg_price_count"])
        else:
            avg_price = 0.0

        result.append(
            SalesFunnelStats(
                article_id=article_id,
                supplier_article=b["supplier_article"],
                name=b["name"],
                brand=b["brand"],
                subject=b["subject"],
                shows=b["shows"],
                detail_views=b["detail_views"],
                add_to_cart=b["add_to_cart"],
                orders=b["orders"],
                buyouts=b["buyouts"],
                revenue_orders=b["revenue_orders"],
                revenue_buyouts=b["revenue_buyouts"],
                avg_price=avg_price,
            )
        )

    # можно отсортировать по выручке/заказам, чтобы удобнее читать
    result.sort(key=lambda x: (-x.revenue_buyouts, -x.orders))
    return result


# Мини-тест для отладки (локально можно запустить python -m wb_bidder_v2.analytics.sales_funnel)
if __name__ == "__main__":
    sample_rows = [
        {
            "Артикул WB": 265104282,
            "Артикул продавца": "ЧерныеЗима1",
            "Название": "Носки теплые махровые термо 5 пар",
            "Бренд": "Brenker",
            "Предмет": "Носки",
            "Показы": 10000,
            "Переходы в карточку": 500,
            "Положили в корзину": 150,
            "Заказали, шт": 80,
            "Выкупили, шт": 70,
            "Заказали на сумму, ₽": 120000,
            "Выкупили на сумму, ₽": 100000,
            "Средняя цена, ₽": 1500,
        }
    ]

    stats = aggregate_sales_funnel(sample_rows)
    for s in stats:
        print(s)
        print(
            "CTR=",
            s.ctr(),
            "CR_cart=",
            s.cr_to_cart(),
            "CR_order_views=",
            s.cr_to_order_from_views(),
            "CR_order_clicks=",
            s.cr_to_order_from_clicks(),
            "BuyoutRate=",
            s.buyout_rate(),
            "AOV=",
            s.aov(),
        )



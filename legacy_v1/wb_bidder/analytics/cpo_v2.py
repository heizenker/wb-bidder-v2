
from __future__ import annotations



from dataclasses import dataclass

from typing import Any, Dict, Optional





@dataclass

class CPOContext:

    """

    Контекст для расчёта CPO-решения по одному товару / кампании.

    """

    item_id: int

    clicks: int

    orders: int

    spent: float

    revenue: float

    current_bid: float

    target_cpo: float

    min_clicks: int

    min_orders: int

    step_up_pct: float

    step_down_pct: float

    dry_run: bool = True



    @property

    def cpo(self) -> Optional[float]:

        if self.orders <= 0:

            return None

        return self.spent / self.orders





@dataclass

class BidDecision:

    """

    Результат CPO-аналитики по одному объекту.

    """

    item_id: int

    action: str  # "increase" | "decrease" | "hold" | "insufficient_data"

    old_bid: float

    new_bid: float

    reason: str

    dry_run: bool = True



    def as_dict(self) -> Dict[str, Any]:

        return {

            "item_id": self.item_id,

            "action": self.action,

            "old_bid": self.old_bid,

            "new_bid": self.new_bid,

            "reason": self.reason,

            "dry_run": self.dry_run,

        }





def decide_bid(ctx: CPOContext) -> BidDecision:

    """

    Чистая CPO-логика v2.



    - учитывает пороги min_clicks / min_orders

    - использует step_up_pct / step_down_pct

    - НЕ меняет ставки на WB, только считает решение (DRY-RUN)

    """

    # 1. Недостаточно данных

    if ctx.clicks < ctx.min_clicks or ctx.orders < ctx.min_orders:

        return BidDecision(

            item_id=ctx.item_id,

            action="insufficient_data",

            old_bid=ctx.current_bid,

            new_bid=ctx.current_bid,

            reason=f"Недостаточно данных: clicks={ctx.clicks}, orders={ctx.orders}",

            dry_run=ctx.dry_run,

        )



    current_cpo = ctx.cpo



    # 2. Есть клики, но нет заказов → CPO бесконечный, снижаем ставку

    if current_cpo is None:

        return BidDecision(

            item_id=ctx.item_id,

            action="decrease",

            old_bid=ctx.current_bid,

            new_bid=round(ctx.current_bid * (1.0 - ctx.step_down_pct), 4),

            reason="Есть клики, но нет заказов → снижаем ставку",

            dry_run=ctx.dry_run,

        )



    # 3. CPO выше таргета → снижаем ставку

    if current_cpo > ctx.target_cpo:

        return BidDecision(

            item_id=ctx.item_id,

            action="decrease",

            old_bid=ctx.current_bid,

            new_bid=round(ctx.current_bid * (1.0 - ctx.step_down_pct), 4),

            reason=f"CPO={current_cpo:.2f} выше таргета {ctx.target_cpo:.2f} → снижаем ставку",

            dry_run=ctx.dry_run,

        )



    # 4. CPO ниже таргета → можем позволить себе поднять ставку

    if current_cpo < ctx.target_cpo:

        return BidDecision(

            item_id=ctx.item_id,

            action="increase",

            old_bid=ctx.current_bid,

            new_bid=round(ctx.current_bid * (1.0 + ctx.step_up_pct), 4),

            reason=f"CPO={current_cpo:.2f} ниже таргета {ctx.target_cpo:.2f} → повышаем ставку",

            dry_run=ctx.dry_run,

        )



    # 5. CPO в допустимом диапазоне → ничего не делаем

    return BidDecision(

        item_id=ctx.item_id,

        action="hold",

        old_bid=ctx.current_bid,

        new_bid=ctx.current_bid,

        reason="CPO в допустимом диапазоне → ставку не трогаем",

        dry_run=ctx.dry_run,

    )


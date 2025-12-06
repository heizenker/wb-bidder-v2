from __future__ import annotations



import datetime

from dataclasses import dataclass

from typing import Any, Dict, List, Optional



from wb_bidder.collectors.collectors_v2 import (

    AdsCollectorV2,

    SearchQueriesCollectorV2,

    SalesFunnelCollectorV2,

)





# ---------------------------------------------------------------

#       ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ

# ---------------------------------------------------------------



def safe_float(v: Any) -> float:

    try:

        return float(v)

    except Exception:

        return 0.0



def safe_int(v: Any) -> int:

    try:

        return int(v)

    except Exception:

        return 0





# ---------------------------------------------------------------

#             CombinedAnalyzerV2

# ---------------------------------------------------------------



@dataclass

class CombinedAnalyzerV2:

    """

    Аналитика v2: объединяет

        - рекламу

        - поисковые запросы

        - воронку продаж



    Выполняет расчёт:

        CTR, CPC, CPO, ROAS, CR, blended-метрики.

    """



    ads: AdsCollectorV2

    queries: SearchQueriesCollectorV2

    funnel: SalesFunnelCollectorV2



    # -----------------------------------------------------------

    #   Загрузка всех данных

    # -----------------------------------------------------------



    def load_all(

        self,

        date_from: datetime.date,

        date_to: datetime.date,

        nm_ids: Optional[List[int]] = None,

    ) -> Dict[str, List[Dict[str, Any]]]:



        ads_rows = self.ads.fetch_ads(date_from, date_to, nm_ids=nm_ids)

        query_rows = self.queries.fetch_search_queries(date_from, date_to, nm_ids=nm_ids)

        funnel_rows = self.funnel.fetch_sales_funnel(date_from, date_to, nm_ids=nm_ids)



        return {

            "ads": ads_rows,

            "queries": query_rows,

            "funnel": funnel_rows,

        }



    # -----------------------------------------------------------

    #          Метрики по строке

    # -----------------------------------------------------------



    @staticmethod

    def enrich_row(row: Dict[str, Any]) -> Dict[str, Any]:

        """

        Добавляет CTR/CPC/CR/CPO/ROAS на каждую строку.

        Работает и для рекламы, и для запросов, и для воронки.

        """



        impressions = safe_int(row.get("impressions")) or safe_int(row.get("views"))

        clicks = safe_int(row.get("clicks"))

        spend = safe_float(row.get("spend")) or safe_float(row.get("spent"))

        orders = safe_int(row.get("orders"))

        revenue = safe_float(row.get("revenue"))

        row["impressions"] = impressions
        row["spend"] = spend



        row["ctr"] = (clicks / impressions * 100.0) if impressions > 0 else 0.0

        row["cpc"] = (spend / clicks) if clicks > 0 else 0.0

        row["cr"] = (orders / clicks * 100.0) if clicks > 0 else 0.0

        row["cpo"] = (spend / orders) if orders > 0 else 0.0

        row["roas"] = (revenue / spend) if spend > 0 else 0.0



        return row



    # -----------------------------------------------------------

    #      Группировка по nm_id

    # -----------------------------------------------------------



    @staticmethod

    def group_by_nm(rows: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:

        out: Dict[int, List[Dict[str, Any]]] = {}

        for row in rows:

            nm_value = row.get("nm_id") or row.get("nmId") or row.get("item_id")

            nm = safe_int(nm_value)

            out.setdefault(nm, []).append(row)

        return out



    # -----------------------------------------------------------

    #      Агрегация blended-метрик

    # -----------------------------------------------------------



    @staticmethod

    def aggregate(rows: List[Dict[str, Any]]) -> Dict[str, float]:

        """

        Агрегирует ключевые поля.

        """

        total = {

            "impressions": 0,

            "clicks": 0,

            "spend": 0.0,

            "orders": 0,

            "revenue": 0.0,

        }



        for r in rows:

            total["impressions"] += safe_int(r.get("impressions") or r.get("views"))

            total["clicks"] += safe_int(r.get("clicks"))

            total["spend"] += safe_float(r.get("spend") or r.get("spent"))

            total["orders"] += safe_int(r.get("orders"))

            total["revenue"] += safe_float(r.get("revenue"))



        # считаем метрики

        imp = total["impressions"]

        clk = total["clicks"]

        sp = total["spend"]

        ords = total["orders"]

        rev = total["revenue"]



        return {

            **total,

            "ctr": (clk / imp * 100.0) if imp > 0 else 0.0,

            "cpc": (sp / clk) if clk > 0 else 0.0,

            "cr": (ords / clk * 100.0) if clk > 0 else 0.0,

            "cpo": (sp / ords) if ords > 0 else 0.0,

            "roas": (rev / sp) if sp > 0 else 0.0,

        }



    # -----------------------------------------------------------

    #          Итоговый отчёт по NM-id

    # -----------------------------------------------------------



    def build_report(

        self,

        date_from: datetime.date,

        date_to: datetime.date,

        nm_ids: Optional[List[int]] = None,

    ) -> Dict[int, Dict[str, Any]]:



        raw = self.load_all(date_from, date_to, nm_ids)

        ads = self.group_by_nm(raw["ads"])

        queries = self.group_by_nm(raw["queries"])

        funnel = self.group_by_nm(raw["funnel"])



        final: Dict[int, Dict[str, Any]] = {}



        all_nms = set(ads.keys()) | set(queries.keys()) | set(funnel.keys())



        for nm in sorted(all_nms):

            nm_ads_rows = [self.enrich_row(r) for r in ads.get(nm, [])]

            nm_query_rows = [self.enrich_row(r) for r in queries.get(nm, [])]

            nm_funnel_rows = [self.enrich_row(r) for r in funnel.get(nm, [])]



            final[nm] = {

                "ads": {

                    "rows": nm_ads_rows,

                    "agg": self.aggregate(nm_ads_rows),

                },

                "queries": {

                    "rows": nm_query_rows,

                    "agg": self.aggregate(nm_query_rows),

                },

                "funnel": {

                    "rows": nm_funnel_rows,

                    "agg": self.aggregate(nm_funnel_rows),

                },

            }



        return final


from wb_bidder.analytics.cpo_v2 import CPOContext, decide_bid





class CPOModuleV2:

    """

    Модуль CPO-аналитики v2.



    Принимает агрегированные данные по кампании/товару и вычисляет решение:

    - increase / decrease / hold / insufficient_data

    - новую ставку

    - причину

    """



    def __init__(

        self,

        target_cpo: float = 300.0,

        min_clicks: int = 20,

        min_orders: int = 2,

        step_up_pct: float = 0.15,

        step_down_pct: float = 0.15,

        dry_run: bool = True,

    ):

        self.target_cpo = target_cpo

        self.min_clicks = min_clicks

        self.min_orders = min_orders

        self.step_up_pct = step_up_pct

        self.step_down_pct = step_down_pct

        self.dry_run = dry_run



    def analyze_item(self, item_data: dict):

        """

        item_data должен содержать:

        - item_id

        - clicks

        - orders

        - spent

        - revenue

        - current_bid

        """



        ctx = CPOContext(

            item_id=item_data["item_id"],

            clicks=item_data.get("clicks", 0),

            orders=item_data.get("orders", 0),

            spent=item_data.get("spent", 0.0),

            revenue=item_data.get("revenue", 0.0),

            current_bid=item_data.get("current_bid", 10.0),

            target_cpo=self.target_cpo,

            min_clicks=self.min_clicks,

            min_orders=self.min_orders,

            step_up_pct=self.step_up_pct,

            step_down_pct=self.step_down_pct,

            dry_run=self.dry_run,

        )



        return decide_bid(ctx).as_dict()



    def analyze_many(self, items: list[dict]):

        """

        Массовый расчёт CPO-решений.

        """

        return [self.analyze_item(x) for x in items]


def test_imports() -> None:
    __import__("wb_bidder_v2.analytics.analytics_v2")
    __import__("wb_bidder_v2.collectors_v2.ads_collector")
    __import__("wb_bidder_v2.collectors_v2.sales_funnel_collector")
    __import__("wb_bidder_v2.collectors_v2.search_queries_collector")
    __import__("wb_bidder_v2.bidder.bidder_v2")
    __import__("wb_bidder_v2.backend_v2.backend_v2")


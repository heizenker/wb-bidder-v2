"""Raw Wildberries API endpoint wrappers."""

from .ads_client import AdsRawClient
from .sales_funnel_client import SalesFunnelRawClient
from .search_report_client import SearchReportRawClient
from .feedbacks_client import FeedbacksRawClient

__all__ = [
    "AdsRawClient",
    "SalesFunnelRawClient",
    "SearchReportRawClient",
    "FeedbacksRawClient",
]


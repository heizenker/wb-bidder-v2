from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List

from wb_bidder_v2.analytics.analytics_v2 import CombinedAnalyzerV2


@dataclass
class SectionBlock:
    """
    Normalized representation of a data section (ads / queries / funnel).
    """

    rows: List[Dict[str, Any]] = field(default_factory=list)
    aggregate: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {"rows": self.rows, "aggregate": self.aggregate}


@dataclass
class PanelItem:
    """
    Aggregated snapshot for a single nmId.
    """

    nm_id: int
    ads: SectionBlock
    queries: SectionBlock
    funnel: SectionBlock

    def as_dict(self) -> Dict[str, Any]:
        return {
            "nm_id": self.nm_id,
            "ads": self.ads.as_dict(),
            "queries": self.queries.as_dict(),
            "funnel": self.funnel.as_dict(),
        }


@dataclass
class PanelSnapshot:
    """
    Read-only snapshot for displaying combined analytics.
    """

    items: List[PanelItem] = field(default_factory=list)

    def as_dict(self) -> List[Dict[str, Any]]:
        return [item.as_dict() for item in self.items]

    def find(self, nm_id: int) -> PanelItem | None:
        for item in self.items:
            if item.nm_id == nm_id:
                return item
        return None


def build_panel_snapshot(
    *,
    ads_rows: Iterable[Dict[str, Any]],
    query_rows: Iterable[Dict[str, Any]],
    funnel_rows: Iterable[Dict[str, Any]],
) -> PanelSnapshot:
    """
    Build a PanelSnapshot using the existing analytics pipeline (CombinedAnalyzerV2).
    """

    analyzer = CombinedAnalyzerV2(
        ads_source=list(ads_rows),
        queries_source=list(query_rows),
        funnel_source=list(funnel_rows),
    )
    report = analyzer.build_report()

    def _to_section_block(section: Dict[str, Any] | None) -> SectionBlock:
        if not section:
            return SectionBlock()
        rows = section.get("rows") or []
        aggregate = section.get("agg") or {}
        return SectionBlock(
            rows=list(rows),
            aggregate=dict(aggregate),
        )

    items: List[PanelItem] = []
    for nm_id in sorted(report.keys()):
        sections = report[nm_id]
        items.append(
            PanelItem(
                nm_id=nm_id,
                ads=_to_section_block(sections.get("ads")),
                queries=_to_section_block(sections.get("queries")),
                funnel=_to_section_block(sections.get("funnel")),
            )
        )

    return PanelSnapshot(items=items)


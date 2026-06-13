from __future__ import annotations
from datetime import datetime
from typing import Literal, Union, Annotated, Any
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class BlockStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    ERROR = "error"


class ReportBlockBase(BaseModel):
    block_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    block_type: str
    title: str
    order: int = 0
    status: BlockStatus = BlockStatus.COMPLETE
    warnings: list[str] = []
    source_task_ids: list[str] = []
    created_by_dept: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Text ────────────────────────────────────────────────────────────────────

class TextBlock(ReportBlockBase):
    block_type: Literal["text"] = "text"
    content: str
    style: Literal["body", "heading", "callout", "quote"] = "body"
    language: str = "ru"


# ─── KPI Card ────────────────────────────────────────────────────────────────

class KPICard(ReportBlockBase):
    block_type: Literal["kpi_card"] = "kpi_card"
    metric_name: str
    value: float
    unit: str = ""
    delta: float | None = None
    delta_pct: float | None = None
    trend: Literal["up", "down", "stable"] | None = None
    is_positive_trend: bool | None = None
    benchmark: float | None = None
    verification_status: Literal["verified", "unverified"] = "verified"
    source_reference: str = ""


# ─── Table ───────────────────────────────────────────────────────────────────

class TableColumn(BaseModel):
    key: str
    label: str
    dtype: Literal["number", "string", "date", "percent", "currency"] = "string"
    unit: str | None = None
    sortable: bool = True
    highlight_rule: dict[str, Any] | None = None


class TableBlock(ReportBlockBase):
    block_type: Literal["table"] = "table"
    columns: list[TableColumn]
    rows: list[dict[str, Any]]
    totals_row: dict[str, Any] | None = None
    pagination: bool = True
    exportable: bool = True
    source_file_id: str = ""
    source_location: str = ""


# ─── Chart ───────────────────────────────────────────────────────────────────

class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    AREA = "area"
    PIE = "pie"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    HISTOGRAM = "histogram"
    BOX = "box"
    WATERFALL = "waterfall"
    TREEMAP = "treemap"
    FUNNEL = "funnel"
    RADAR = "radar"


class ChartBlock(ReportBlockBase):
    block_type: Literal["chart"] = "chart"
    chart_type: ChartType
    vega_lite_spec: dict[str, Any]
    caption: str | None = None
    data_source_description: str = ""
    interactive: bool = True


# ─── Insight ─────────────────────────────────────────────────────────────────

class InsightBlock(ReportBlockBase):
    block_type: Literal["insight"] = "insight"
    insight_type: Literal["finding", "anomaly", "recommendation", "risk", "opportunity"]
    severity: Literal["info", "warning", "critical"] = "info"
    headline: str
    explanation: str
    supporting_data: list[str] = []
    confidence: float = 0.8


# ─── Comparison ──────────────────────────────────────────────────────────────

class ComparisonItem(BaseModel):
    label: str
    metrics: dict[str, float | str]


class ComparisonBlock(ReportBlockBase):
    block_type: Literal["comparison"] = "comparison"
    items: list[ComparisonItem]
    dimensions: list[str]
    winner: str | None = None
    analysis: str = ""


# ─── Forecast ────────────────────────────────────────────────────────────────

class TimePoint(BaseModel):
    period: str
    value: float


class ForecastPoint(BaseModel):
    period: str
    value: float
    lower_bound: float
    upper_bound: float


class ForecastBlock(ReportBlockBase):
    block_type: Literal["forecast"] = "forecast"
    metric_name: str
    historical: list[TimePoint]
    forecast: list[ForecastPoint]
    method: str = "auto"
    confidence_interval: float = 0.95
    model_accuracy: dict[str, float] = {}


# ─── Risk Matrix ─────────────────────────────────────────────────────────────

class RiskItem(BaseModel):
    name: str
    probability: Literal["low", "medium", "high"]
    impact: Literal["low", "medium", "high"]
    description: str
    mitigation: str | None = None


class RiskMatrixBlock(ReportBlockBase):
    block_type: Literal["risk_matrix"] = "risk_matrix"
    risks: list[RiskItem]
    overall_risk_level: Literal["low", "medium", "high", "critical"]


# ─── Executive Summary ────────────────────────────────────────────────────────

class ExecutiveSummaryBlock(ReportBlockBase):
    block_type: Literal["executive_summary"] = "executive_summary"
    key_findings: list[str]
    recommendations: list[str]
    overall_conclusion: str
    report_quality_score: float = 0.8


# ─── Discriminated Union ─────────────────────────────────────────────────────

ReportBlock = Annotated[
    Union[
        TextBlock,
        KPICard,
        TableBlock,
        ChartBlock,
        InsightBlock,
        ComparisonBlock,
        ForecastBlock,
        RiskMatrixBlock,
        ExecutiveSummaryBlock,
    ],
    Field(discriminator="block_type"),
]

BLOCK_TYPES = {
    "text": TextBlock,
    "kpi_card": KPICard,
    "table": TableBlock,
    "chart": ChartBlock,
    "insight": InsightBlock,
    "comparison": ComparisonBlock,
    "forecast": ForecastBlock,
    "risk_matrix": RiskMatrixBlock,
    "executive_summary": ExecutiveSummaryBlock,
}

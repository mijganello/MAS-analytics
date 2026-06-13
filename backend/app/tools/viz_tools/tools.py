from __future__ import annotations
from typing import Any
from app.tools.registry import tool


@tool(departments=["visualization"])
def suggest_chart_type(data_description: str, analysis_goal: str) -> dict[str, Any]:
    """Rule-based chart type suggestion based on data and goal."""
    desc_lower = data_description.lower()
    goal_lower = analysis_goal.lower()

    suggestions = []

    if any(w in goal_lower for w in ["тренд", "динамика", "trend", "over time", "temporal"]):
        suggestions.append({"type": "line", "reason": "Temporal trend visualization"})
    if any(w in goal_lower for w in ["сравни", "compare", "versus", "vs"]):
        suggestions.append({"type": "bar", "reason": "Categorical comparison"})
    if any(w in desc_lower for w in ["доля", "процент", "share", "percent", "distribution"]):
        suggestions.append({"type": "pie", "reason": "Part-to-whole relationship"})
    if any(w in goal_lower for w in ["корреляция", "зависимость", "correlation", "scatter"]):
        suggestions.append({"type": "scatter", "reason": "Relationship between variables"})
    if any(w in desc_lower for w in ["распределение", "histogram", "частота", "frequency"]):
        suggestions.append({"type": "histogram", "reason": "Distribution visualization"})
    if any(w in goal_lower for w in ["waterfall", "водопад", "breakdown", "разбивка"]):
        suggestions.append({"type": "waterfall", "reason": "Cumulative change"})

    if not suggestions:
        suggestions.append({"type": "bar", "reason": "Default for categorical data"})

    return {"suggestions": suggestions, "primary": suggestions[0]["type"]}


@tool(departments=["visualization"])
def generate_bar_chart_spec(
    labels: list,
    values: list,
    x_label: str = "Category",
    y_label: str = "Value",
    title: str = "",
    color: str = "#3b82f6",
) -> dict[str, Any]:
    """Generate Vega-Lite bar chart specification."""
    data = [{"x": str(l), "y": float(v)} for l, v in zip(labels, values)]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title,
        "data": {"values": data},
        "mark": {"type": "bar", "color": color, "cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
        "encoding": {
            "x": {"field": "x", "type": "nominal", "title": x_label, "axis": {"labelAngle": -30}},
            "y": {"field": "y", "type": "quantitative", "title": y_label},
            "tooltip": [{"field": "x", "title": x_label}, {"field": "y", "title": y_label}],
        },
        "width": "container",
        "height": 300,
    }


@tool(departments=["visualization"])
def generate_line_chart_spec(
    labels: list,
    values: list,
    x_label: str = "Period",
    y_label: str = "Value",
    title: str = "",
) -> dict[str, Any]:
    """Generate Vega-Lite line chart with points."""
    data = [{"x": str(l), "y": float(v)} for l, v in zip(labels, values)]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title,
        "data": {"values": data},
        "layer": [
            {
                "mark": {"type": "line", "strokeWidth": 2, "color": "#3b82f6"},
                "encoding": {
                    "x": {"field": "x", "type": "ordinal", "title": x_label},
                    "y": {"field": "y", "type": "quantitative", "title": y_label},
                },
            },
            {
                "mark": {"type": "point", "filled": True, "size": 60, "color": "#3b82f6"},
                "encoding": {
                    "x": {"field": "x", "type": "ordinal"},
                    "y": {"field": "y", "type": "quantitative"},
                    "tooltip": [{"field": "x", "title": x_label}, {"field": "y", "title": y_label}],
                },
            },
        ],
        "width": "container",
        "height": 300,
    }


@tool(departments=["visualization"])
def generate_pie_chart_spec(
    labels: list,
    values: list,
    title: str = "",
) -> dict[str, Any]:
    """Generate Vega-Lite pie/donut chart specification."""
    data = [{"category": str(l), "value": float(v)} for l, v in zip(labels, values)]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title,
        "data": {"values": data},
        "mark": {"type": "arc", "innerRadius": 50},
        "encoding": {
            "theta": {"field": "value", "type": "quantitative"},
            "color": {"field": "category", "type": "nominal", "legend": {"title": "Category"}},
            "tooltip": [{"field": "category"}, {"field": "value"}],
        },
        "width": 350,
        "height": 300,
    }


@tool(departments=["visualization"])
def generate_scatter_spec(
    x_values: list,
    y_values: list,
    labels: list,
    x_label: str = "X",
    y_label: str = "Y",
    title: str = "",
) -> dict[str, Any]:
    """Generate Vega-Lite scatter plot."""
    data = [{"x": float(x), "y": float(y), "label": str(l)} for x, y, l in zip(x_values, y_values, labels)]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title,
        "data": {"values": data},
        "mark": {"type": "point", "filled": True, "size": 80},
        "encoding": {
            "x": {"field": "x", "type": "quantitative", "title": x_label},
            "y": {"field": "y", "type": "quantitative", "title": y_label},
            "tooltip": [{"field": "label"}, {"field": "x"}, {"field": "y"}],
        },
        "width": "container",
        "height": 300,
    }


@tool(departments=["visualization", "report_assembly"])
def generate_kpi_card_spec(
    metric_name: str,
    value: float,
    unit: str = "",
    delta_pct: float | None = None,
    trend: str = "stable",
) -> dict[str, Any]:
    """Generate KPI card data spec (rendered by React component)."""
    return {
        "metric_name": metric_name,
        "value": value,
        "unit": unit,
        "delta_pct": delta_pct,
        "trend": trend,
        "is_positive": delta_pct is not None and delta_pct > 0,
    }

from __future__ import annotations
from typing import Any
import pandas as pd
import numpy as np
from app.tools.registry import tool


def _to_series(values: list[float]) -> pd.Series:
    return pd.Series([float(v) for v in values], dtype=float)


@tool(departments=["quant_analysis"])
def calculate_statistics(values: list, metrics: list) -> dict[str, Any]:
    """Calculate descriptive statistics: mean, median, std, min, max, percentiles."""
    s = _to_series(values)
    available = {
        "mean": float(s.mean()),
        "median": float(s.median()),
        "std": float(s.std()),
        "min": float(s.min()),
        "max": float(s.max()),
        "count": int(s.count()),
        "sum": float(s.sum()),
        "p25": float(s.quantile(0.25)),
        "p75": float(s.quantile(0.75)),
        "p90": float(s.quantile(0.90)),
        "skewness": float(s.skew()),
        "kurtosis": float(s.kurt()),
    }
    if not metrics:
        return available
    return {m: available[m] for m in metrics if m in available}


@tool(departments=["quant_analysis"])
def calculate_growth_rate(values: list, periods: list) -> dict[str, Any]:
    """Calculate YoY, MoM, QoQ growth rates and CAGR."""
    s = _to_series(values)
    if len(s) < 2:
        return {"error": "Need at least 2 values"}

    result: dict[str, Any] = {}
    n = len(s)

    # Period-over-period
    pct_changes = s.pct_change().dropna().tolist()
    result["period_changes_pct"] = [round(v * 100, 2) for v in pct_changes]
    result["periods"] = periods[1:] if periods and len(periods) >= n else list(range(1, n))

    # CAGR
    start, end = float(s.iloc[0]), float(s.iloc[-1])
    if start > 0 and n > 1:
        result["cagr_pct"] = round((pow(end / start, 1 / (n - 1)) - 1) * 100, 2)

    result["total_change_pct"] = round((end - start) / abs(start) * 100, 2) if start != 0 else None
    result["latest_value"] = end
    result["first_value"] = start
    return result


@tool(departments=["quant_analysis"])
def calculate_correlation(series_a: list, series_b: list, method: str = "pearson") -> dict[str, Any]:
    """Calculate correlation between two series (pearson/spearman/kendall) with p-value."""
    from scipy import stats
    a, b = _to_series(series_a), _to_series(series_b)
    if len(a) != len(b):
        return {"error": "Series must have equal length"}

    methods = {
        "pearson": stats.pearsonr,
        "spearman": stats.spearmanr,
        "kendall": stats.kendalltau,
    }
    fn = methods.get(method, stats.pearsonr)
    corr, pvalue = fn(a.dropna(), b.dropna())
    return {
        "method": method,
        "correlation": round(float(corr), 4),
        "p_value": round(float(pvalue), 6),
        "significant": float(pvalue) < 0.05,
        "interpretation": _interpret_corr(float(corr)),
    }


def _interpret_corr(r: float) -> str:
    a = abs(r)
    if a >= 0.9: return "very strong"
    if a >= 0.7: return "strong"
    if a >= 0.5: return "moderate"
    if a >= 0.3: return "weak"
    return "negligible"


@tool(departments=["quant_analysis"])
def run_trend_analysis(values: list, periods: list) -> dict[str, Any]:
    """Linear trend analysis with slope, R-squared, direction."""
    from scipy import stats as sp_stats
    import numpy as np
    s = _to_series(values)
    x = np.arange(len(s))
    slope, intercept, r, p, se = sp_stats.linregress(x, s.values)

    fitted = [round(intercept + slope * xi, 4) for xi in x]
    return {
        "slope": round(float(slope), 4),
        "intercept": round(float(intercept), 4),
        "r_squared": round(float(r ** 2), 4),
        "p_value": round(float(p), 6),
        "direction": "increasing" if slope > 0 else "decreasing" if slope < 0 else "flat",
        "trend_strength": "strong" if r**2 > 0.7 else "moderate" if r**2 > 0.4 else "weak",
        "fitted_values": fitted,
        "periods": periods or list(range(len(values))),
    }


@tool(departments=["quant_analysis"])
def forecast_series(values: list, periods: list, horizon: int = 3, method: str = "auto") -> dict[str, Any]:
    """Forecast future values using ARIMA/ETS. Returns forecast + confidence intervals."""
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        import numpy as np
        s = _to_series(values)
        if len(s) < 3:
            return {"error": "Need at least 3 data points"}

        fit = ExponentialSmoothing(s, trend="add", seasonal=None).fit()
        forecast = fit.forecast(horizon)
        residuals = s - fit.fittedvalues
        std_err = float(residuals.std())

        z = 1.96  # 95% CI
        points = []
        for i, (val, period) in enumerate(zip(forecast, range(len(values), len(values) + horizon))):
            points.append({
                "period": str(period),
                "value": round(float(val), 4),
                "lower_bound": round(float(val) - z * std_err * (1 + i * 0.1), 4),
                "upper_bound": round(float(val) + z * std_err * (1 + i * 0.1), 4),
            })

        mae = float(abs(residuals).mean())
        mape = float((abs(residuals / s.replace(0, np.nan))).mean()) * 100

        return {
            "method": "ExponentialSmoothing",
            "forecast": points,
            "model_accuracy": {"MAE": round(mae, 4), "MAPE_pct": round(mape, 2)},
            "historical": [{"period": str(p), "value": float(v)} for p, v in zip(periods or range(len(values)), values)],
        }
    except Exception as e:
        return {"error": str(e)}


@tool(departments=["quant_analysis"])
def detect_outliers(values: list, method: str = "iqr") -> dict[str, Any]:
    """Detect outliers using IQR, Z-score, or Isolation Forest."""
    s = _to_series(values)
    if method == "iqr":
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        mask = (s < lower) | (s > upper)
    elif method == "zscore":
        z = (s - s.mean()) / s.std()
        mask = z.abs() > 3
        lower, upper = float(s.mean() - 3 * s.std()), float(s.mean() + 3 * s.std())
    else:
        from sklearn.ensemble import IsolationForest
        iso = IsolationForest(contamination=0.1, random_state=42)
        preds = iso.fit_predict(s.values.reshape(-1, 1))
        mask = pd.Series(preds == -1, index=s.index)
        lower, upper = float(s.min()), float(s.max())

    outliers = [{"index": int(i), "value": float(v)} for i, v in s[mask].items()]
    return {
        "method": method,
        "outliers": outliers,
        "outlier_count": len(outliers),
        "outlier_pct": round(len(outliers) / len(s) * 100, 2),
        "lower_bound": round(float(lower), 4),
        "upper_bound": round(float(upper), 4),
    }


@tool(departments=["quant_analysis"])
def calculate_financial_metrics(
    revenue: list,
    costs: list,
    periods: list,
) -> dict[str, Any]:
    """Calculate gross margin, net margin, and period trends."""
    results = []
    for r, c, p in zip(revenue, costs, periods):
        r_f, c_f = float(r), float(c)
        profit = r_f - c_f
        margin = round(profit / r_f * 100, 2) if r_f != 0 else 0
        results.append({
            "period": p,
            "revenue": r_f,
            "costs": c_f,
            "profit": round(profit, 2),
            "margin_pct": margin,
        })
    return {"periods": results}

"""Generator: Financial statements JSON (5 years, quarterly)."""
import json
import random
from pathlib import Path

SEED = 42
random.seed(SEED)
OUT_DIR = Path(__file__).parent.parent / "fixtures"

SEGMENTS = ["Корпоративный", "МСБ", "Розничный", "Международный"]


def _grow(base: float, rate: float, noise: float = 0.05) -> float:
    return round(base * (1 + rate + random.uniform(-noise, noise)), 2)


def generate():
    OUT_DIR.mkdir(exist_ok=True)

    data: dict = {"company": "ООО Аналитика-Про", "currency": "RUB_thousands", "quarters": []}

    # Seed values (2020 Q1)
    revenue_seg = {"Корпоративный": 280_000, "МСБ": 140_000,
                   "Розничный": 95_000, "Международный": 45_000}
    opex_base = 420_000
    capex_base = 35_000
    debt_base  = 500_000

    key_metrics: dict = {
        "years": [], "total_revenue_by_year": {}, "ebitda_by_year": {},
        "net_income_by_year": {}, "segments": {s: [] for s in SEGMENTS},
    }

    for year in range(2020, 2025):
        yr_revenue = 0.0
        yr_ebitda  = 0.0
        yr_ni      = 0.0
        for q in range(1, 5):
            q_label = f"Q{q}_{year}"

            # Revenue by segment
            seg_rev = {}
            total_rev = 0.0
            for seg in SEGMENTS:
                yoy_rate = {"Корпоративный": 0.18, "МСБ": 0.22,
                            "Розничный": 0.12, "Международный": 0.30}.get(seg, 0.15)
                seasonal = 1.0 + (0.15 if q == 4 else -0.05 if q == 1 else 0.0)
                revenue_seg[seg] = _grow(revenue_seg[seg], yoy_rate / 4, 0.04) * seasonal
                seg_rev[seg] = round(revenue_seg[seg], 2)
                total_rev += revenue_seg[seg]

            # Cost structure
            cogs    = round(total_rev * random.uniform(0.38, 0.44), 2)
            gross   = round(total_rev - cogs, 2)
            opex    = round(_grow(opex_base, 0.12 / 4, 0.03), 2)
            opex_base = opex
            ebitda  = round(gross - opex, 2)
            da      = round(total_rev * 0.06, 2)
            ebit    = round(ebitda - da, 2)
            interest= round(debt_base * 0.12 / 4, 2)
            ebt     = round(ebit - interest, 2)
            tax     = round(max(0.0, ebt * 0.20), 2)
            net_inc = round(ebt - tax, 2)

            # Cash flow
            capex   = round(_grow(capex_base, 0.10 / 4, 0.05), 2)
            capex_base = capex
            op_cf   = round(ebitda * random.uniform(0.82, 0.95), 2)
            free_cf = round(op_cf - capex, 2)

            # Balance sheet
            debt_base = round(debt_base * random.uniform(0.97, 1.02), 2)
            equity    = round(debt_base * random.uniform(0.8, 1.3), 2)
            assets    = round(debt_base + equity, 2)

            data["quarters"].append({
                "period": q_label,
                "year": year,
                "quarter": q,
                "income_statement": {
                    "revenue_by_segment": seg_rev,
                    "total_revenue": round(total_rev, 2),
                    "cogs": cogs,
                    "gross_profit": gross,
                    "gross_margin_pct": round(gross / total_rev * 100, 2),
                    "opex": opex,
                    "ebitda": ebitda,
                    "ebitda_margin_pct": round(ebitda / total_rev * 100, 2),
                    "depreciation_amortization": da,
                    "ebit": ebit,
                    "interest_expense": interest,
                    "ebt": ebt,
                    "income_tax": tax,
                    "net_income": net_inc,
                    "net_margin_pct": round(net_inc / total_rev * 100, 2),
                },
                "cash_flow": {
                    "operating_cf": op_cf,
                    "capex": capex,
                    "free_cash_flow": free_cf,
                },
                "balance_sheet": {
                    "total_assets": assets,
                    "total_debt": debt_base,
                    "equity": equity,
                    "debt_to_equity": round(debt_base / max(equity, 1), 2),
                    "net_debt": round(debt_base - op_cf * 0.5, 2),
                },
            })

            yr_revenue += total_rev
            yr_ebitda  += ebitda
            yr_ni      += net_inc

        key_metrics["years"].append(year)
        key_metrics["total_revenue_by_year"][str(year)] = round(yr_revenue, 2)
        key_metrics["ebitda_by_year"][str(year)]        = round(yr_ebitda,  2)
        key_metrics["net_income_by_year"][str(year)]    = round(yr_ni,      2)

    out_json = OUT_DIR / "financial_statements.json"
    out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # Compute ground truth
    rev_2024  = key_metrics["total_revenue_by_year"]["2024"]
    rev_2023  = key_metrics["total_revenue_by_year"]["2023"]
    ebitda_2024 = key_metrics["ebitda_by_year"]["2024"]
    ni_2024   = key_metrics["net_income_by_year"]["2024"]
    cagr_rev  = round(((rev_2024 / key_metrics["total_revenue_by_year"]["2020"]) ** (1/4) - 1) * 100, 2)

    last_q = data["quarters"][-1]

    gt = {
        "dataset_id": "03_financial",
        "file": "financial_statements.json",
        "description": "Quarterly P&L, cash flow, balance sheet for 2020-2024, 4 segments",
        "query": (
            "Оцени финансовое здоровье компании: динамика выручки и EBITDA за 5 лет (2020-2024), "
            "маржинальность по сегментам в 2024 году, долговая нагрузка (Debt/Equity), "
            "операционный денежный поток и свободный денежный поток, CAGR выручки?"
        ),
        "ground_truth": {
            "total_revenue_2024":     rev_2024,
            "total_revenue_2023":     rev_2023,
            "ebitda_2024":            ebitda_2024,
            "ebitda_margin_2024_pct": round(ebitda_2024 / rev_2024 * 100, 2),
            "net_income_2024":        ni_2024,
            "cagr_revenue_pct":       cagr_rev,
            "last_debt_to_equity":    last_q["balance_sheet"]["debt_to_equity"],
            "last_free_cf":           last_q["cash_flow"]["free_cash_flow"],
        },
        "expected_numbers": [
            {"key": "ebitda_margin_2024", "value": round(ebitda_2024 / rev_2024 * 100, 1), "tolerance": 0.05},
            {"key": "cagr_revenue",       "value": cagr_rev,  "tolerance": 0.10},
            {"key": "debt_to_equity",     "value": last_q["balance_sheet"]["debt_to_equity"], "tolerance": 0.15},
        ],
        "required_topics": [
            "выручк", "ebitda", "маржин", "долг", "денежный поток", "cagr", "чистая прибыл"
        ],
    }
    (OUT_DIR / "financial_statements_ground_truth.json").write_text(
        json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_json.name}  ({out_json.stat().st_size // 1024} KB)")
    return gt


if __name__ == "__main__":
    generate()

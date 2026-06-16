"""Generator: Manufacturing quality control CSV (60 000 measurements)."""
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
random.seed(SEED)
OUT_DIR = Path(__file__).parent.parent / "fixtures"

LINES = [
    ("LINE-A", {"base_defect": 0.025, "speed": 120}),
    ("LINE-B", {"base_defect": 0.018, "speed": 95}),
    ("LINE-C", {"base_defect": 0.042, "speed": 150}),
    ("LINE-D", {"base_defect": 0.031, "speed": 110}),
    ("LINE-E", {"base_defect": 0.015, "speed": 80}),
]

DEFECT_TYPES = [
    "Царапина",
    "Деформация",
    "Неправильная сборка",
    "Загрязнение",
    "Размерное отклонение",
    "Электрический дефект",
    "Нет дефекта",
]
DEFECT_W = [0.15, 0.12, 0.20, 0.10, 0.18, 0.08, 0.17]  # last = no defect when defective slot

STAGES = ["Подготовка", "Сборка", "Контроль", "Тестирование", "Упаковка"]

N_ROWS    = 60_000
START_TS  = datetime(2024, 7, 1)


def generate():
    OUT_DIR.mkdir(exist_ok=True)
    out_csv = OUT_DIR / "manufacturing_quality.csv"

    line_stats: dict[str, dict] = {
        ln: {"total": 0, "defects": 0, "defect_types": {}, "stage_defects": {s: 0 for s in STAGES}}
        for ln, _ in LINES
    }
    defect_type_total: dict[str, int] = {d: 0 for d in DEFECT_TYPES if d != "Нет дефекта"}
    total_defects = 0
    rows_per_line = N_ROWS // len(LINES)

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "measurement_id", "timestamp", "line_id", "stage",
            "unit_id", "temp_celsius", "pressure_bar", "vibration_hz",
            "weight_g", "dimension_mm", "pass_fail", "defect_type",
            "operator_id", "shift"
        ])

        ts = START_TS
        row_num = 0

        for line_id, cfg in LINES:
            base_defect = cfg["base_defect"]
            line_ts = START_TS

            for _ in range(rows_per_line):
                # Drift: quality degrades over time (maintenance needed)
                progress = row_num / N_ROWS
                drift_factor = 1.0 + progress * 0.5  # up to 50% more defects at end

                # Shift patterns
                hour = line_ts.hour
                shift = "Ночная" if 0 <= hour < 8 else "Дневная" if 8 <= hour < 16 else "Вечерняя"
                shift_mult = 1.4 if shift == "Ночная" else 1.0

                stage = random.choice(STAGES)
                defect_prob = base_defect * drift_factor * shift_mult

                # Environmental measurements (correlated with defects)
                temp = round(random.gauss(72 + (5 if defect_prob > 0.05 else 0), 3), 1)
                pressure = round(random.gauss(2.5, 0.15), 3)
                vibration = round(random.gauss(50 + (20 if defect_prob > 0.05 else 0), 8), 2)
                weight    = round(random.gauss(500, 5), 2)
                dimension = round(random.gauss(100.0, 0.5), 3)

                is_defect = random.random() < defect_prob
                if is_defect:
                    defect_type = random.choices(
                        [d for d in DEFECT_TYPES if d != "Нет дефекта"],
                        weights=DEFECT_W[:-1]
                    )[0]
                    pass_fail   = "БРАК"
                    total_defects += 1
                    line_stats[line_id]["defects"] += 1
                    line_stats[line_id]["defect_types"][defect_type] = (
                        line_stats[line_id]["defect_types"].get(defect_type, 0) + 1)
                    line_stats[line_id]["stage_defects"][stage] += 1
                    defect_type_total[defect_type] = defect_type_total.get(defect_type, 0) + 1
                else:
                    defect_type = "Нет дефекта"
                    pass_fail   = "ОК"

                line_stats[line_id]["total"] += 1

                writer.writerow([
                    f"M-{row_num+1:07d}",
                    line_ts.strftime("%Y-%m-%dT%H:%M:%S"),
                    line_id, stage,
                    f"UNIT-{random.randint(1, 10000):06d}",
                    temp, pressure, vibration, weight, dimension,
                    pass_fail, defect_type,
                    f"OP-{random.randint(1, 50):03d}", shift,
                ])

                row_num += 1
                line_ts += timedelta(seconds=random.randint(30, 90))

    # Aggregate
    for ln in line_stats:
        t = line_stats[ln]["total"]
        d = line_stats[ln]["defects"]
        line_stats[ln]["defect_rate"] = round(d / t, 5) if t else 0

    worst_line = max(line_stats, key=lambda l: line_stats[l]["defect_rate"])
    best_line  = min(line_stats, key=lambda l: line_stats[l]["defect_rate"])
    top3_defects = sorted(defect_type_total.items(), key=lambda x: x[1], reverse=True)[:3]
    overall_defect_rate = round(total_defects / N_ROWS * 100, 3)

    gt = {
        "dataset_id": "09_manufacturing",
        "file": "manufacturing_quality.csv",
        "description": "Quality control: 60 000 measurements, 5 production lines",
        "query": (
            "Анализ производства: каков общий процент брака и по каждой линии? "
            "Какая линия имеет наихудший показатель качества? "
            "Топ-3 типа дефектов по количеству — на каком этапе производства больше всего выбраковки? "
            "Прослеживается ли тренд ухудшения качества со временем?"
        ),
        "ground_truth": {
            "total_measurements":   N_ROWS,
            "total_defects":        total_defects,
            "overall_defect_rate_pct": overall_defect_rate,
            "worst_line":           worst_line,
            "worst_line_defect_pct":round(line_stats[worst_line]["defect_rate"] * 100, 3),
            "best_line":            best_line,
            "best_line_defect_pct": round(line_stats[best_line]["defect_rate"] * 100, 3),
            "top3_defects":         [{"type": d, "count": c} for d, c in top3_defects],
            "line_stats":           {ln: {k: v for k, v in s.items() if k != "defect_types"}
                                      for ln, s in line_stats.items()},
        },
        "expected_numbers": [
            {"key": "total_measurements",   "value": N_ROWS,   "tolerance": 0.001},
            {"key": "total_defects",        "value": total_defects, "tolerance": 0.02},
            {"key": "overall_defect_pct",   "value": overall_defect_rate, "tolerance": 0.05},
            {"key": "worst_line_defect_pct","value": round(line_stats[worst_line]["defect_rate"] * 100, 2), "tolerance": 0.05},
        ],
        "required_topics": [
            "брак", "дефект", "линия", "этап", "тренд", "процент", "качеств"
        ],
    }
    (OUT_DIR / "manufacturing_quality_ground_truth.json").write_text(
        json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_csv.name}  ({out_csv.stat().st_size // 1024} KB)")
    return gt


if __name__ == "__main__":
    generate()

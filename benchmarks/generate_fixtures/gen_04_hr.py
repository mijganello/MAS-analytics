"""Generator: HR employee dataset CSV (5 000 employees)."""
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
random.seed(SEED)
OUT_DIR = Path(__file__).parent.parent / "fixtures"

DEPARTMENTS = {
    "Разработка ПО":   {"size": 420, "base_salary": 210_000, "attrition_rate": 0.08},
    "Продажи":         {"size": 310, "base_salary": 130_000, "attrition_rate": 0.18},
    "Маркетинг":       {"size": 145, "base_salary": 125_000, "attrition_rate": 0.12},
    "Финансы":         {"size": 180, "base_salary": 150_000, "attrition_rate": 0.07},
    "HR":              {"size": 95,  "base_salary": 100_000, "attrition_rate": 0.10},
    "Операции":        {"size": 260, "base_salary": 95_000,  "attrition_rate": 0.22},
    "Поддержка":       {"size": 190, "base_salary": 88_000,  "attrition_rate": 0.28},
    "Юридический":     {"size": 75,  "base_salary": 175_000, "attrition_rate": 0.05},
    "ИТ-инфраструктура":{"size": 160,"base_salary": 180_000, "attrition_rate": 0.09},
    "Аналитика":       {"size": 165, "base_salary": 195_000, "attrition_rate": 0.06},
}

GRADES = ["Junior", "Middle", "Senior", "Lead", "Principal"]
GRADE_MULT = [0.70, 1.00, 1.40, 1.80, 2.20]

HIRE_DATE_START = date(2015, 1, 1)
HIRE_DATE_END   = date(2024, 12, 31)


def _rand_date(start: date, end: date) -> date:
    return start + timedelta(days=random.randint(0, (end - start).days))


def generate():
    OUT_DIR.mkdir(exist_ok=True)
    out_csv = OUT_DIR / "hr_employees.csv"

    rows = []
    emp_id = 1
    dept_stats: dict[str, dict] = {}

    for dept, cfg in DEPARTMENTS.items():
        salaries_m, salaries_f = [], []
        left_count, total = 0, 0
        engagement_scores = []
        perf_scores = []

        for _ in range(cfg["size"]):
            gender  = random.choices(["М", "Ж"], weights=[0.62, 0.38])[0]
            age     = random.randint(22, 58)
            grade   = random.choices(GRADES, weights=[0.25, 0.35, 0.25, 0.10, 0.05])[0]
            grade_i = GRADES.index(grade)

            # Gender pay gap: women earn ~12% less on average
            gender_mult = 1.0 if gender == "М" else random.uniform(0.84, 0.95)
            salary = round(
                cfg["base_salary"] * GRADE_MULT[grade_i] * gender_mult
                * random.uniform(0.90, 1.10)
            )

            hire_date  = _rand_date(HIRE_DATE_START, HIRE_DATE_END)
            tenure_yrs = round((date(2025, 1, 1) - hire_date).days / 365.25, 1)

            perf  = round(random.gauss(3.4, 0.8), 1)
            perf  = max(1.0, min(5.0, perf))
            eng   = round(random.gauss(6.8, 1.5), 1)
            eng   = max(1.0, min(10.0, eng))

            # Attrition correlated with low engagement
            left = random.random() < (cfg["attrition_rate"] * (1.5 if eng < 5 else 0.6))
            left_start = hire_date + timedelta(days=90)
            left_end   = date(2025, 1, 1)
            left_date  = _rand_date(left_start, left_end) if (left and left_start < left_end) else None

            rows.append({
                "employee_id":   f"EMP-{emp_id:05d}",
                "department":    dept,
                "gender":        gender,
                "age":           age,
                "grade":         grade,
                "salary":        salary,
                "hire_date":     hire_date.isoformat(),
                "tenure_years":  tenure_yrs,
                "performance_score": perf,
                "engagement_score":  eng,
                "left_company":  int(left),
                "left_date":     left_date.isoformat() if left_date else "",
            })

            if gender == "М":
                salaries_m.append(salary)
            else:
                salaries_f.append(salary)
            if left:
                left_count += 1
            total += 1
            engagement_scores.append(eng)
            perf_scores.append(perf)
            emp_id += 1

        avg_m = round(sum(salaries_m) / len(salaries_m)) if salaries_m else 0
        avg_f = round(sum(salaries_f) / len(salaries_f)) if salaries_f else 0
        dept_stats[dept] = {
            "headcount":        total,
            "attrition_count":  left_count,
            "attrition_rate":   round(left_count / total, 4),
            "avg_salary_male":  avg_m,
            "avg_salary_female":avg_f,
            "gender_pay_gap_pct": round((avg_m - avg_f) / max(avg_m, 1) * 100, 2) if avg_m else 0,
            "avg_engagement":   round(sum(engagement_scores) / len(engagement_scores), 2),
            "avg_performance":  round(sum(perf_scores) / len(perf_scores), 2),
        }

    # Write CSV
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # Ground truth
    highest_attr  = max(dept_stats, key=lambda d: dept_stats[d]["attrition_rate"])
    largest_gap   = max(dept_stats, key=lambda d: dept_stats[d]["gender_pay_gap_pct"])
    total_emp     = sum(d["headcount"] for d in dept_stats.values())
    total_left    = sum(d["attrition_count"] for d in dept_stats.values())
    overall_attr  = round(total_left / total_emp, 4)

    gt = {
        "dataset_id": "04_hr",
        "file": "hr_employees.csv",
        "description": "HR dataset: 5000 employees across 10 departments, 2015-2024",
        "query": (
            "Кадровый анализ: в каком отделе самая высокая текучесть кадров и каков её уровень? "
            "Есть ли гендерный разрыв в зарплатах — в каком отделе он максимален? "
            "Какова общая численность сотрудников и общий уровень текучести по компании? "
            "Корреляция между уровнем вовлечённости и показателем производительности?"
        ),
        "ground_truth": {
            "total_employees":        total_emp,
            "total_attrition":        total_left,
            "overall_attrition_rate": overall_attr,
            "highest_attrition_dept": highest_attr,
            "highest_attrition_rate": dept_stats[highest_attr]["attrition_rate"],
            "largest_gender_gap_dept":largest_gap,
            "largest_gender_gap_pct": dept_stats[largest_gap]["gender_pay_gap_pct"],
            "dept_stats":             dept_stats,
        },
        "expected_numbers": [
            {"key": "total_employees",        "value": total_emp,      "tolerance": 0.001},
            {"key": "overall_attrition_rate", "value": round(overall_attr * 100, 1), "tolerance": 0.05},
            {"key": "highest_attrition_rate", "value": round(dept_stats[highest_attr]["attrition_rate"] * 100, 1), "tolerance": 0.05},
            {"key": "largest_gender_gap_pct", "value": dept_stats[largest_gap]["gender_pay_gap_pct"], "tolerance": 0.10},
        ],
        "required_topics": [
            "текучест", "отдел", "гендерн", "зарплат", "вовлечённост", "производительност"
        ],
    }
    (OUT_DIR / "hr_employees_ground_truth.json").write_text(
        json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_csv.name}  ({out_csv.stat().st_size // 1024} KB)")
    return gt


if __name__ == "__main__":
    generate()

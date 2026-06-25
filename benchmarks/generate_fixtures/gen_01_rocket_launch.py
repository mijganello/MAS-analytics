"""Dataset 01: Rocket launches — 12 missions (small) / 1000+ (big)."""
import csv
import json
import math
import random
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "fixtures"
COLUMNS = ["mission_id", "date", "rocket", "payload_kg", "max_altitude_km", "success", "cost_million_rub"]

# Rockets with their typical parameter ranges
ROCKETS = [
    ("Союз-2.1а",  (900, 2200),   (370, 430),  0.92),
    ("Протон-М",   (5000, 7000),  (340, 380),  0.88),
    ("Ангара-1.2", (800, 1400),   (360, 420),  0.90),
    ("Союз-2.1б",  (1400, 2500),  (395, 435),  0.91),
    ("Союз-5",     (3000, 5500),  (350, 410),  0.89),
    ("Ангара-А5",  (4000, 8000),  (330, 400),  0.85),
]


def _gen_row(mission_num: int, year: int) -> tuple:
    rocket_name, (pay_min, pay_max), (alt_min, alt_max), succ_prob = random.choice(ROCKETS)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    payload = random.randint(pay_min, pay_max)
    altitude = round(random.uniform(alt_min, alt_max), 1)
    success = 1 if random.random() < succ_prob else 0
    # Cost correlates with payload
    base_cost = payload * 1.8 + random.uniform(-300, 300)
    cost = round(max(500, base_cost))
    return (f"M{mission_num:04d}", f"{year}-{month:02d}-{day:02d}",
            rocket_name, payload, altitude, success, cost)


def generate(big: bool = False):
    OUT_DIR.mkdir(exist_ok=True)

    if big:
        random.seed(42)
        total_rows = 1200
        data = []
        for i in range(1, total_rows + 1):
            year = 2023 + (i - 1) // 400
            data.append(_gen_row(i, min(year, 2025)))
    else:
        data = [
            ("M001", "2023-03-12", "Союз-2.1а",  1340, 412, 1, 2870),
            ("M002", "2023-05-27", "Протон-М",   6200, 357, 1, 4120),
            ("M003", "2023-07-19", "Ангара-1.2",  980, 389, 1, 1980),
            ("M004", "2023-09-08", "Союз-2.1б",  2100, 425, 0, 3010),
            ("M005", "2023-11-21", "Союз-2.1а",  1560, 401, 1, 2760),
            ("M006", "2024-01-14", "Ангара-1.2", 1120, 376, 1, 2050),
            ("M007", "2024-03-03", "Протон-М",   5800, 362, 1, 3980),
            ("M008", "2024-05-17", "Союз-2.1б",  1890, 418, 1, 2940),
            ("M009", "2024-07-29", "Союз-2.1а",  1420, 407, 0, 2810),
            ("M010", "2024-09-11", "Ангара-1.2", 1050, 382, 1, 2010),
            ("M011", "2024-11-05", "Союз-2.1б",  1670, 421, 1, 2890),
            ("M012", "2025-01-22", "Протон-М",   6400, 368, 1, 4210),
        ]

    suffix = "_big" if big else ""
    out_csv = OUT_DIR / f"rocket_launches{suffix}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(data)

    total = len(data)
    successful = sum(r[5] for r in data)
    success_rate = round(successful / total * 100, 2)
    total_payload = sum(r[3] for r in data)
    max_cost = max(r[6] for r in data)
    avg_altitude = round(sum(r[4] for r in data) / total, 2)
    failed = total - successful

    gt = {
        "dataset_id": f"01_rocket_launch{suffix}",
        "file": f"rocket_launches{suffix}.csv",
        "description": f"{total} космических запусков 2023–2025",
        "query": (
            "Проанализируй данные о запусках ракет. Ответь точно:\n"
            "1. Сколько всего запусков?\n"
            "2. Сколько успешных запусков?\n"
            "3. Каков процент успешных запусков?\n"
            "4. Какова суммарная масса полезной нагрузки (кг)?\n"
            "5. Какова максимальная стоимость одного запуска (млн руб.)?\n"
            "6. Какова средняя максимальная высота полёта (км)?"
        ),
        "ground_truth": {
            "total_launches": total,
            "successful_launches": successful,
            "failed_launches": failed,
            "success_rate_pct": success_rate,
            "total_payload_kg": total_payload,
            "max_cost_million": max_cost,
            "avg_altitude_km": avg_altitude,
        },
        "expected_numbers": [
            {"key": "total_launches", "question": "Всего запусков?", "value": total, "tolerance": 0.001},
            {"key": "successful_launches", "question": "Успешных запусков?", "value": successful, "tolerance": 0.001},
            {"key": "success_rate_pct", "question": "Процент успешных?", "value": success_rate, "tolerance": 0.05},
            {"key": "total_payload_kg", "question": "Суммарная нагрузка (кг)?", "value": total_payload, "tolerance": 0.02},
            {"key": "max_cost_million", "question": "Макс. стоимость (млн руб.)?", "value": max_cost, "tolerance": 0.001},
            {"key": "avg_altitude_km", "question": "Средняя высота (км)?", "value": avg_altitude, "tolerance": 0.02},
        ],
    }
    gt_path = OUT_DIR / f"rocket_launches{suffix}_ground_truth.json"
    gt_path.write_text(json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_csv.name} ({len(data)} rows) → {gt_path.name}")
    return gt


if __name__ == "__main__":
    big = "--big" in __import__("sys").argv
    generate(big=big)


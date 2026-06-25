"""Dataset 05: Server logs — 20 rows (small) / 1000+ (big)."""
import csv
import json
import random
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "fixtures"
COLUMNS = ["date", "endpoint", "requests", "errors_4xx", "errors_5xx", "avg_response_ms"]

ENDPOINTS = ["/api/users", "/api/orders", "/api/search", "/api/auth",
             "/api/products", "/api/payments", "/api/notifications", "/api/reports",
             "/api/settings", "/api/upload"]

SMALL_DATA = [
    ("2024-06-10", "/api/users",    2847, 112, 28, 198),
    ("2024-06-10", "/api/orders",   1923,  76, 41, 312),
    ("2024-06-10", "/api/search",   3412, 187, 15, 145),
    ("2024-06-10", "/api/auth",     1567,  63, 89, 267),
    ("2024-06-11", "/api/users",    3124, 128, 31, 205),
    ("2024-06-11", "/api/orders",   2108,  84, 47, 328),
    ("2024-06-11", "/api/search",   3678, 201, 18, 138),
    ("2024-06-11", "/api/auth",     1689,  71, 94, 281),
    ("2024-06-12", "/api/users",    2654, 104, 25, 191),
    ("2024-06-12", "/api/orders",   1789,  69, 38, 305),
    ("2024-06-12", "/api/search",   3291, 178, 12, 142),
    ("2024-06-12", "/api/auth",     1456,  58, 82, 259),
    ("2024-06-13", "/api/users",    3341, 134, 35, 212),
    ("2024-06-13", "/api/orders",   2287,  91, 52, 341),
    ("2024-06-13", "/api/search",   3892, 213, 21, 151),
    ("2024-06-13", "/api/auth",     1823,  77, 98, 289),
    ("2024-06-14", "/api/users",    2987, 118, 29, 201),
    ("2024-06-14", "/api/orders",   2012,  81, 44, 319),
    ("2024-06-14", "/api/search",   3523, 195, 16, 147),
    ("2024-06-14", "/api/auth",     1612,  66, 91, 274),
]


def _compute_gt(data):
    total_requests = sum(r[2] for r in data)
    total_4xx = sum(r[3] for r in data)
    total_5xx = sum(r[4] for r in data)
    total_errors = total_4xx + total_5xx
    error_rate = round(total_errors / total_requests * 100, 2)

    ep_req: dict[str, int] = {}
    ep_5xx: dict[str, int] = {}
    for r in data:
        ep_req[r[1]] = ep_req.get(r[1], 0) + r[2]
        ep_5xx[r[1]] = ep_5xx.get(r[1], 0) + r[4]
    top_endpoint = max(ep_req, key=ep_req.__getitem__)
    top_ep_requests = ep_req[top_endpoint]
    worst_5xx_ep = max(ep_5xx, key=ep_5xx.__getitem__)
    worst_5xx_count = ep_5xx[worst_5xx_ep]

    day_req: dict[str, int] = {}
    for r in data:
        day_req[r[0]] = day_req.get(r[0], 0) + r[2]
    busiest_day = max(day_req, key=day_req.__getitem__)
    busiest_day_req = day_req[busiest_day]
    return total_requests, total_errors, error_rate, top_endpoint, top_ep_requests, busiest_day, busiest_day_req, worst_5xx_ep, worst_5xx_count


def generate(big: bool = False):
    OUT_DIR.mkdir(exist_ok=True)

    if big:
        random.seed(101)
        num_days = 120  # 120 days × 10 endpoints = 1200 rows
        data = []
        for day_offset in range(num_days):
            month = 6 + (day_offset // 30)
            day = 1 + (day_offset % 30)
            if month > 12:
                month -= 12
            if day > 28:
                day = day % 28 + 1
            date_str = f"2024-{month:02d}-{day:02d}"
            for ep in ENDPOINTS:
                requests = random.randint(800, 5000)
                errors_4xx = random.randint(10, 250)
                errors_5xx = random.randint(5, 120)
                avg_ms = random.randint(100, 400)
                data.append((date_str, ep, requests, errors_4xx, errors_5xx, avg_ms))
    else:
        data = SMALL_DATA

    suffix = "_big" if big else ""
    out_csv = OUT_DIR / f"server_logs{suffix}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(data)

    total_requests, total_errors, error_rate, top_endpoint, top_ep_requests, busiest_day, busiest_day_req, worst_5xx_ep, worst_5xx_count = _compute_gt(data)

    gt = {
        "dataset_id": f"05_server_logs{suffix}",
        "file": f"server_logs{suffix}.csv",
        "description": f"HTTP-логи: {len(set(r[1] for r in data))} эндпоинтов × {len(set(r[0] for r in data))} дней",
        "query": (
            "Проанализируй серверные логи. Ответь точно:\n"
            "1. Сколько всего запросов?\n"
            "2. Сколько ошибок 4xx и 5xx суммарно?\n"
            "3. Каков процент ошибок?\n"
            "4. Какой эндпоинт самый нагруженный и сколько запросов?\n"
            "5. Сколько запросов в самый нагруженный день?\n"
            "6. Сколько ошибок 5xx у эндпоинта с наибольшим числом 5xx?"
        ),
        "ground_truth": {
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate_pct": error_rate,
            "top_endpoint": top_endpoint,
            "top_ep_requests": top_ep_requests,
            "busiest_day": busiest_day,
            "busiest_day_req": busiest_day_req,
            "worst_5xx_endpoint": worst_5xx_ep,
            "worst_5xx_count": worst_5xx_count,
        },
        "expected_numbers": [
            {"key": "total_requests", "question": "Всего запросов?", "value": total_requests, "tolerance": 0.02},
            {"key": "total_errors", "question": "Суммарно ошибок?", "value": total_errors, "tolerance": 0.02},
            {"key": "error_rate_pct", "question": "Процент ошибок?", "value": error_rate, "tolerance": 0.05},
            {"key": "top_ep_requests", "question": "Запросов у топ-эндпоинта?", "value": top_ep_requests, "tolerance": 0.02},
            {"key": "busiest_day_req", "question": "Запросов в пиковый день?", "value": busiest_day_req, "tolerance": 0.02},
            {"key": "worst_5xx_count", "question": "5xx у худшего эндпоинта?", "value": worst_5xx_count, "tolerance": 0.02},
        ],
    }
    gt_path = OUT_DIR / f"server_logs{suffix}_ground_truth.json"
    gt_path.write_text(json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_csv.name} ({len(data)} rows) → {gt_path.name}")
    return gt


if __name__ == "__main__":
    big = "--big" in __import__("sys").argv
    generate(big=big)


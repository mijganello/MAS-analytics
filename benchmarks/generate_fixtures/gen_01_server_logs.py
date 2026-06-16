"""Generator: Apache-style HTTP server access logs (100 000 rows)."""
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
random.seed(SEED)

OUT_DIR = Path(__file__).parent.parent / "fixtures"

ENDPOINTS = [
    ("/api/v1/users",          0.14),
    ("/api/v1/products",       0.11),
    ("/api/v1/orders",         0.10),
    ("/api/v1/auth/login",     0.08),
    ("/api/v1/search",         0.09),
    ("/api/v1/cart",           0.07),
    ("/api/v1/checkout",       0.04),
    ("/api/v1/reports",        0.03),
    ("/api/v1/admin/stats",    0.02),
    ("/static/js/main.js",     0.05),
    ("/static/css/style.css",  0.04),
    ("/favicon.ico",           0.03),
    ("/health",                0.06),
    ("/api/v1/notifications",  0.05),
    ("/api/v1/profile",        0.09),
]
EP_NAMES   = [e[0] for e in ENDPOINTS]
EP_WEIGHTS = [e[1] for e in ENDPOINTS]

STATUS_DIST = [
    (200, 0.70), (201, 0.05), (204, 0.02),
    (301, 0.02), (302, 0.02), (304, 0.03),
    (400, 0.02), (401, 0.01), (403, 0.01), (404, 0.03),
    (429, 0.01),
    (500, 0.015), (502, 0.005), (503, 0.005), (504, 0.005),
]
STATUS_CODES   = [s[0] for s in STATUS_DIST]
STATUS_WEIGHTS = [s[1] for s in STATUS_DIST]

METHODS = ["GET"] * 65 + ["POST"] * 20 + ["PUT"] * 10 + ["DELETE"] * 5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605 Safari/604",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Firefox/125",
    "python-httpx/0.27.0",
    "curl/8.4.0",
    "Googlebot/2.1 (+http://www.google.com/bot.html)",
]

N_ROWS      = 100_000
N_IPS       = 5_000
START_TS    = datetime(2025, 1, 1)


def _weighted_choice(choices, weights):
    return random.choices(choices, weights=weights, k=1)[0]


def generate():
    OUT_DIR.mkdir(exist_ok=True)
    out_csv = OUT_DIR / "server_logs.csv"

    # Pre-generate IPs (some will be heavy hitters)
    ips = [f"192.168.{random.randint(0,255)}.{random.randint(1,254)}" for _ in range(N_IPS)]
    # Make 10 IPs high-volume (anomalous)
    heavy_ips = random.sample(ips, 10)
    heavy_ip_counts = {}

    counters = {
        "total": 0,
        "5xx": 0,
        "4xx": 0,
        "3xx": 0,
        "2xx": 0,
    }
    endpoint_counter: dict[str, int] = {}
    hour_counter: dict[int, int] = {}
    ip_counter: dict[str, int] = {}

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", "ip", "method", "endpoint",
            "status", "response_bytes", "response_ms", "user_agent"
        ])

        current_ts = START_TS
        for i in range(N_ROWS):
            # Time: advance ~3 seconds per request with noise; heavy traffic hours 9-18
            hour_weight = 3.0 if 9 <= current_ts.hour <= 18 else 0.7
            delta_s = max(0.1, random.gauss(3.0 / hour_weight, 1.5))
            current_ts += timedelta(seconds=delta_s)

            # IP: heavy hitters appear more often
            if random.random() < 0.03:
                ip = random.choice(heavy_ips)
                heavy_ip_counts[ip] = heavy_ip_counts.get(ip, 0) + 1
            else:
                ip = random.choice(ips)

            method   = random.choice(METHODS)
            endpoint = _weighted_choice(EP_NAMES, EP_WEIGHTS)
            status   = _weighted_choice(STATUS_CODES, STATUS_WEIGHTS)
            resp_kb  = random.randint(200, 50_000)
            resp_ms  = max(5, int(random.lognormvariate(5.5, 1.0)))
            ua       = random.choice(USER_AGENTS)

            writer.writerow([
                current_ts.strftime("%Y-%m-%d %H:%M:%S"),
                ip, method, endpoint, status, resp_kb, resp_ms, ua,
            ])

            # Accumulate stats
            counters["total"] += 1
            if 200 <= status < 300:
                counters["2xx"] += 1
            elif 300 <= status < 400:
                counters["3xx"] += 1
            elif 400 <= status < 500:
                counters["4xx"] += 1
            elif status >= 500:
                counters["5xx"] += 1

            endpoint_counter[endpoint] = endpoint_counter.get(endpoint, 0) + 1
            h = current_ts.hour
            hour_counter[h] = hour_counter.get(h, 0) + 1
            ip_counter[ip] = ip_counter.get(ip, 0) + 1

    # Derive ground truth
    top5_ep = sorted(endpoint_counter.items(), key=lambda x: x[1], reverse=True)[:5]
    peak_hour = max(hour_counter, key=hour_counter.get)
    top10_ip = sorted(ip_counter.items(), key=lambda x: x[1], reverse=True)[:10]
    unique_ips = len(ip_counter)

    gt = {
        "dataset_id": "01_server_logs",
        "file": "server_logs.csv",
        "description": "Apache HTTP-server access logs, 100 000 requests, Jan 2025",
        "query": (
            "Сколько всего запросов обработал сервер? Каков процент ошибок 4xx и 5xx? "
            "Определи топ-5 самых загруженных эндпоинтов по числу запросов. "
            "В какие часы суток пиковая нагрузка? "
            "Есть ли подозрительные IP с аномально высоким числом запросов (топ-10)?"
        ),
        "ground_truth": {
            "total_requests":     counters["total"],
            "unique_ips":         unique_ips,
            "count_2xx":          counters["2xx"],
            "count_3xx":          counters["3xx"],
            "count_4xx":          counters["4xx"],
            "count_5xx":          counters["5xx"],
            "pct_4xx":            round(counters["4xx"] / counters["total"] * 100, 2),
            "pct_5xx":            round(counters["5xx"] / counters["total"] * 100, 2),
            "top1_endpoint":      top5_ep[0][0],
            "top1_endpoint_count": top5_ep[0][1],
            "top5_endpoints":     [{"endpoint": e, "count": c} for e, c in top5_ep],
            "peak_hour":          peak_hour,
            "peak_hour_requests": hour_counter[peak_hour],
            "top1_ip":            top10_ip[0][0],
            "top1_ip_count":      top10_ip[0][1],
        },
        "expected_numbers": [
            {"key": "total_requests",     "value": counters["total"],      "tolerance": 0.001},
            {"key": "unique_ips",         "value": unique_ips,              "tolerance": 0.05},
            {"key": "pct_4xx",            "value": round(counters["4xx"] / counters["total"] * 100, 1), "tolerance": 0.10},
            {"key": "pct_5xx",            "value": round(counters["5xx"] / counters["total"] * 100, 1), "tolerance": 0.10},
            {"key": "top1_endpoint_count","value": top5_ep[0][1],          "tolerance": 0.05},
            {"key": "peak_hour",          "value": peak_hour,               "tolerance": 0.0},
        ],
        "required_topics": [
            "запрос", "ошибк", "5xx", "4xx", "эндпоинт", "нагрузк", "пик", "ip"
        ],
    }

    gt_path = OUT_DIR / "server_logs_ground_truth.json"
    gt_path.write_text(json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_csv.name}  ({out_csv.stat().st_size // 1024} KB)  →  {gt_path.name}")
    return gt


if __name__ == "__main__":
    generate()

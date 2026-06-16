"""Generator: Network monitoring CSV (100 000 measurements, 1/min for ~70 days)."""
import csv
import json
import random
import math
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
random.seed(SEED)
OUT_DIR = Path(__file__).parent.parent / "fixtures"

NODES = [
    ("node-msk-01", "Москва",          "core"),
    ("node-msk-02", "Москва",          "core"),
    ("node-spb-01", "Санкт-Петербург", "edge"),
    ("node-ekb-01", "Екатеринбург",    "edge"),
    ("node-nsk-01", "Новосибирск",     "edge"),
    ("node-kzn-01", "Казань",          "edge"),
]

N_ROWS     = 100_000
START_TS   = datetime(2025, 1, 1)
INTERVAL_S = 60  # 1 minute


def generate():
    OUT_DIR.mkdir(exist_ok=True)
    out_csv = OUT_DIR / "network_monitoring.csv"

    node_stats: dict[str, dict] = {
        n[0]: {"up": 0, "down": 0, "degraded": 0,
                "latencies": [], "packet_losses": [], "bandwidths": []}
        for n in NODES
    }

    anomaly_events = []
    total_rows = 0

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", "node_id", "region", "node_type",
            "latency_ms", "packet_loss_pct", "bandwidth_mbps",
            "cpu_pct", "memory_pct", "status", "anomaly"
        ])

        rows_per_node = N_ROWS // len(NODES)
        ts = START_TS

        for node_id, region, node_type in NODES:
            node_ts = START_TS
            # Each node: inject 2–4 outage windows
            outage_starts = sorted(random.sample(range(1000, rows_per_node - 100), 3))
            outage_durations = [random.randint(5, 40) for _ in outage_starts]
            outage_windows = set()
            for s, d in zip(outage_starts, outage_durations):
                outage_windows.update(range(s, s + d))

            base_latency = {"core": 12.0, "edge": 28.0}[node_type]

            for row_i in range(rows_per_node):
                node_ts_str = node_ts.strftime("%Y-%m-%dT%H:%M:%S")
                hour = node_ts.hour

                if row_i in outage_windows:
                    status      = "down"
                    latency_ms  = 0.0
                    pkt_loss    = 100.0
                    bandwidth   = 0.0
                    cpu_pct     = 0.0
                    mem_pct     = 0.0
                    anomaly     = 1
                    anomaly_events.append({"node": node_id, "ts": node_ts_str, "type": "outage"})
                else:
                    # Business hours: higher load
                    load_mult = 1.0 + 0.6 * math.sin((hour - 6) / 24 * 2 * math.pi) if 8 <= hour <= 20 else 0.7
                    latency_ms  = round(base_latency * load_mult + random.gauss(0, 3), 2)
                    pkt_loss    = round(max(0, random.gauss(0.3, 0.5)), 3)
                    bandwidth   = round(random.uniform(100, 1000) * load_mult, 1)
                    cpu_pct     = round(min(100, random.gauss(35 * load_mult, 10)), 1)
                    mem_pct     = round(min(100, random.gauss(55, 8)), 1)
                    # Occasional high-latency spikes
                    if random.random() < 0.005:
                        latency_ms *= random.uniform(5, 20)
                        anomaly = 1
                        anomaly_events.append({"node": node_id, "ts": node_ts_str, "type": "latency_spike"})
                    else:
                        anomaly = 0
                    if latency_ms > 200:
                        status = "degraded"
                    else:
                        status = "up"

                writer.writerow([
                    node_ts_str, node_id, region, node_type,
                    round(latency_ms, 2), round(pkt_loss, 3), round(bandwidth, 1),
                    round(cpu_pct, 1), round(mem_pct, 1), status, anomaly
                ])

                ns = node_stats[node_id]
                ns[status if status in ("up","down","degraded") else "up"] += 1
                if status != "down":
                    ns["latencies"].append(latency_ms)
                    ns["packet_losses"].append(pkt_loss)
                    ns["bandwidths"].append(bandwidth)
                total_rows += 1
                node_ts += timedelta(seconds=INTERVAL_S)

    # Compute per-node uptime
    node_uptime: dict[str, float] = {}
    node_avg_lat: dict[str, float] = {}
    for node_id, stats in node_stats.items():
        total = stats["up"] + stats["down"] + stats["degraded"]
        node_uptime[node_id] = round(stats["up"] / max(total, 1) * 100, 3)
        node_avg_lat[node_id] = (round(sum(stats["latencies"]) / len(stats["latencies"]), 2)
                                  if stats["latencies"] else 0.0)

    worst_node     = min(node_uptime, key=node_uptime.get)
    best_node      = max(node_uptime, key=node_uptime.get)
    total_anomalies= len(anomaly_events)
    outage_events  = sum(1 for e in anomaly_events if e["type"] == "outage")

    gt = {
        "dataset_id": "07_network",
        "file": "network_monitoring.csv",
        "description": "Network monitoring: 6 nodes × ~17000 measurements (1 min interval), ~70 days",
        "query": (
            "Анализ сети: средняя задержка и пиковые значения по узлам? "
            "Процент времени доступности (uptime) для каждого узла — у какого узла наихудший uptime? "
            "Сколько аномальных событий зафиксировано и каков % оттказов (outage)? "
            "Корреляция нагрузки (bandwidth) с задержкой (latency)?"
        ),
        "ground_truth": {
            "total_measurements": total_rows,
            "total_anomalies":    total_anomalies,
            "outage_events":      outage_events,
            "node_uptime_pct":    node_uptime,
            "node_avg_latency_ms":node_avg_lat,
            "worst_uptime_node":  worst_node,
            "worst_uptime_pct":   node_uptime[worst_node],
            "best_uptime_node":   best_node,
            "best_uptime_pct":    node_uptime[best_node],
        },
        "expected_numbers": [
            {"key": "total_measurements", "value": total_rows,  "tolerance": 0.02},
            {"key": "total_anomalies",    "value": total_anomalies, "tolerance": 0.05},
            {"key": "worst_uptime_pct",   "value": node_uptime[worst_node], "tolerance": 0.02},
        ],
        "required_topics": [
            "задержк", "uptime", "доступност", "аномали", "узел", "отказ", "нагрузк"
        ],
    }
    (OUT_DIR / "network_monitoring_ground_truth.json").write_text(
        json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_csv.name}  ({out_csv.stat().st_size // 1024} KB)")
    return gt


if __name__ == "__main__":
    generate()

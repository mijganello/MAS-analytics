"""Generator: Support tickets JSON (5 000 tickets)."""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
random.seed(SEED)
OUT_DIR = Path(__file__).parent.parent / "fixtures"

CATEGORIES = {
    "Технический сбой":     {"weight": 0.22, "sla_hours": 4,  "avg_resolve_h": 8.0},
    "Запрос функционала":   {"weight": 0.18, "sla_hours": 72, "avg_resolve_h": 96.0},
    "Проблема с доступом":  {"weight": 0.16, "sla_hours": 2,  "avg_resolve_h": 3.5},
    "Вопрос по продукту":   {"weight": 0.15, "sla_hours": 24, "avg_resolve_h": 20.0},
    "Выставление счёта":    {"weight": 0.12, "sla_hours": 48, "avg_resolve_h": 36.0},
    "Производительность":   {"weight": 0.10, "sla_hours": 8,  "avg_resolve_h": 14.0},
    "Безопасность":         {"weight": 0.07, "sla_hours": 1,  "avg_resolve_h": 2.0},
}

PRIORITIES = ["Критический", "Высокий", "Средний", "Низкий"]
PRIORITY_W  = [0.10, 0.20, 0.45, 0.25]

STATUSES    = ["Закрыт", "Открыт", "В работе"]
STATUS_W    = [0.78, 0.10, 0.12]

N_TICKETS   = 5_000
START_TS    = datetime(2024, 1, 1)
END_TS      = datetime(2025, 1, 1)


def _rand_dt():
    delta = (END_TS - START_TS).total_seconds()
    return START_TS + timedelta(seconds=random.random() * delta)


def generate():
    OUT_DIR.mkdir(exist_ok=True)
    out_json = OUT_DIR / "support_tickets.json"

    tickets = []
    cat_stats: dict[str, dict] = {
        c: {"count": 0, "sla_breaches": 0, "resolve_hours": []}
        for c in CATEGORIES
    }
    dow_counts = {i: 0 for i in range(7)}  # 0=Mon
    total_sla_breaches = 0

    for i in range(N_TICKETS):
        cat  = random.choices(list(CATEGORIES.keys()),
                               weights=[v["weight"] for v in CATEGORIES.values()])[0]
        cfg  = CATEGORIES[cat]
        prio = random.choices(PRIORITIES, weights=PRIORITY_W)[0]
        status = random.choices(STATUSES, weights=STATUS_W)[0]

        created = _rand_dt()
        sla_h   = cfg["sla_hours"] * (0.5 if prio == "Критический" else 1.0)
        if prio == "Низкий":
            sla_h *= 2.0

        if status == "Закрыт":
            resolve_h = round(abs(random.gauss(cfg["avg_resolve_h"], cfg["avg_resolve_h"] * 0.4)), 2)
            resolved_dt = created + timedelta(hours=resolve_h)
            sla_breach  = resolve_h > sla_h
        else:
            resolve_h   = None
            resolved_dt = None
            sla_breach  = False

        if sla_breach:
            total_sla_breaches += 1
            cat_stats[cat]["sla_breaches"] += 1

        cat_stats[cat]["count"] += 1
        if resolve_h:
            cat_stats[cat]["resolve_hours"].append(resolve_h)
        dow_counts[created.weekday()] += 1

        tickets.append({
            "ticket_id":    f"TKT-{i+1:05d}",
            "category":     cat,
            "priority":     prio,
            "status":       status,
            "created_at":   created.isoformat(),
            "resolved_at":  resolved_dt.isoformat() if resolved_dt else None,
            "resolve_hours":resolve_h,
            "sla_hours":    sla_h,
            "sla_breach":   sla_breach,
            "customer_id":  f"CUST-{random.randint(1, 2000):05d}",
            "agent_id":     f"AGT-{random.randint(1, 30):03d}",
        })

    out_json.write_text(json.dumps({"tickets": tickets}, ensure_ascii=False, indent=2))

    # Ground truth
    for c in cat_stats:
        rh = cat_stats[c]["resolve_hours"]
        cat_stats[c]["avg_resolve_hours"] = round(sum(rh) / len(rh), 2) if rh else None
        cat_stats[c]["sla_breach_rate"]   = round(
            cat_stats[c]["sla_breaches"] / cat_stats[c]["count"], 4)

    busiest_dow = max(dow_counts, key=dow_counts.get)
    dow_names   = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    top_cat     = max(cat_stats, key=lambda c: cat_stats[c]["count"])
    slowest_cat = max((c for c in cat_stats if cat_stats[c]["avg_resolve_hours"]),
                       key=lambda c: cat_stats[c]["avg_resolve_hours"])

    closed = sum(1 for t in tickets if t["status"] == "Закрыт")
    sla_pct= round(total_sla_breaches / closed * 100, 2) if closed else 0

    gt = {
        "dataset_id": "08_support",
        "file": "support_tickets.json",
        "description": "5000 support tickets, 7 categories, 2024",
        "query": (
            "Анализ поддержки: среднее время закрытия тикетов по категориям? "
            "Какой % тикетов нарушил SLA (закрыт после дедлайна)? "
            "Топ-3 категории по количеству обращений и по нарушениям SLA? "
            "В какой день недели наибольший поток тикетов?"
        ),
        "ground_truth": {
            "total_tickets":     N_TICKETS,
            "total_closed":      closed,
            "total_sla_breaches":total_sla_breaches,
            "sla_breach_pct":    sla_pct,
            "top_category":      top_cat,
            "top_category_count":cat_stats[top_cat]["count"],
            "slowest_category":  slowest_cat,
            "slowest_avg_hours": cat_stats[slowest_cat]["avg_resolve_hours"],
            "busiest_dow":       dow_names[busiest_dow],
            "busiest_dow_count": dow_counts[busiest_dow],
            "cat_stats":         {c: {k: v for k, v in s.items() if k != "resolve_hours"}
                                   for c, s in cat_stats.items()},
        },
        "expected_numbers": [
            {"key": "total_tickets",   "value": N_TICKETS, "tolerance": 0.001},
            {"key": "sla_breach_pct",  "value": sla_pct,   "tolerance": 0.10},
            {"key": "total_sla_breaches","value": total_sla_breaches, "tolerance": 0.05},
        ],
        "required_topics": [
            "sla", "нарушен", "категори", "время", "закрыт", "тикет", "день недели"
        ],
    }
    (OUT_DIR / "support_tickets_ground_truth.json").write_text(
        json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_json.name}  ({out_json.stat().st_size // 1024} KB)")
    return gt


if __name__ == "__main__":
    generate()

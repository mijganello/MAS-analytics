"""Generator: E-commerce events CSV (100 000 rows, funnel data)."""
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
random.seed(SEED)
OUT_DIR = Path(__file__).parent.parent / "fixtures"

CATEGORIES = {
    "Электроника":   {"weight": 0.22, "avg_price": 35_000},
    "Одежда":        {"weight": 0.18, "avg_price": 4_500},
    "Бытовая техника":{"weight":0.14, "avg_price": 22_000},
    "Спорт":         {"weight": 0.12, "avg_price": 8_000},
    "Красота":       {"weight": 0.10, "avg_price": 2_500},
    "Книги":         {"weight": 0.08, "avg_price": 900},
    "Игрушки":       {"weight": 0.07, "avg_price": 3_500},
    "Продукты":      {"weight": 0.09, "avg_price": 1_800},
}
CAT_NAMES   = list(CATEGORIES.keys())
CAT_WEIGHTS = [v["weight"] for v in CATEGORIES.values()]

CHANNELS = ["organic", "paid_search", "social", "email", "direct", "referral"]
CHAN_W    = [0.28, 0.22, 0.18, 0.12, 0.12, 0.08]

DEVICES   = ["mobile", "desktop", "tablet"]
DEVICE_W  = [0.55, 0.35, 0.10]

EVENT_TYPES = ["view", "add_to_cart", "begin_checkout", "purchase", "abandon_cart"]

N_ROWS    = 100_000
N_USERS   = 25_000
N_PRODUCTS= 2_000
START_TS  = datetime(2024, 10, 1)
END_TS    = datetime(2025, 1, 1)


def _rand_dt():
    delta = (END_TS - START_TS).total_seconds()
    ts = START_TS + timedelta(seconds=random.random() * delta)
    return ts


def generate():
    OUT_DIR.mkdir(exist_ok=True)
    out_csv = OUT_DIR / "ecommerce_events.csv"

    funnel: dict[str, int] = {e: 0 for e in EVENT_TYPES}
    cat_gmv: dict[str, float] = {c: 0.0 for c in CAT_NAMES}
    cat_orders: dict[str, int] = {c: 0 for c in CAT_NAMES}
    channel_revenue: dict[str, float] = {ch: 0.0 for ch in CHANNELS}
    dow_purchases: dict[int, int] = {i: 0 for i in range(7)}
    total_revenue = 0.0
    purchase_amounts: list[float] = []

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "event_id", "timestamp", "user_id", "session_id",
            "event_type", "product_id", "category", "channel",
            "device", "quantity", "unit_price", "revenue"
        ])

        for i in range(N_ROWS):
            ts       = _rand_dt()
            user_id  = f"U-{random.randint(1, N_USERS):06d}"
            sess_id  = f"S-{random.randint(1, N_USERS*3):08d}"
            cat      = random.choices(CAT_NAMES, weights=CAT_WEIGHTS)[0]
            cat_cfg  = CATEGORIES[cat]
            prod_id  = f"P-{random.randint(1, N_PRODUCTS):05d}"
            channel  = random.choices(CHANNELS, weights=CHAN_W)[0]
            device   = random.choices(DEVICES, weights=DEVICE_W)[0]

            # Event type distribution (funnel)
            event = random.choices(EVENT_TYPES, weights=[0.55, 0.20, 0.10, 0.08, 0.07])[0]

            price = round(cat_cfg["avg_price"] * random.uniform(0.7, 1.4), 2)
            qty   = 1

            if event == "purchase":
                qty     = random.choices([1, 2, 3, 4, 5], weights=[0.65, 0.20, 0.08, 0.05, 0.02])[0]
                revenue = round(price * qty, 2)
                cat_gmv[cat] += revenue
                cat_orders[cat] += 1
                channel_revenue[channel] += revenue
                total_revenue += revenue
                purchase_amounts.append(revenue)
                dow_purchases[ts.weekday()] += 1
            elif event in ("view", "abandon_cart", "add_to_cart", "begin_checkout"):
                revenue = 0.0
            else:
                revenue = 0.0

            funnel[event] += 1

            writer.writerow([
                f"EV-{i+1:08d}", ts.strftime("%Y-%m-%dT%H:%M:%S"),
                user_id, sess_id, event,
                prod_id, cat, channel, device,
                qty if event == "purchase" else 0,
                price, revenue,
            ])

    # Funnel metrics
    views        = funnel["view"]
    cart_adds    = funnel["add_to_cart"]
    checkouts    = funnel["begin_checkout"]
    purchases    = funnel["purchase"]
    abandons     = funnel["abandon_cart"]

    view_to_cart   = round(cart_adds / max(views, 1) * 100, 2)
    cart_to_chk    = round(checkouts / max(cart_adds, 1) * 100, 2)
    chk_to_pur     = round(purchases / max(checkouts, 1) * 100, 2)
    overall_conv   = round(purchases / max(views, 1) * 100, 2)
    abandon_rate   = round(abandons / max(cart_adds + abandons, 1) * 100, 2)
    avg_order_val  = round(total_revenue / max(purchases, 1), 2)

    top3_cat_gmv  = sorted(cat_gmv.items(), key=lambda x: x[1], reverse=True)[:3]
    top_channel   = max(channel_revenue, key=channel_revenue.get)
    dow_names     = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    busiest_dow   = max(dow_purchases, key=dow_purchases.get)

    gt = {
        "dataset_id": "10_ecommerce",
        "file": "ecommerce_events.csv",
        "description": "E-commerce event stream: 100 000 events, Q4 2024, 8 categories",
        "query": (
            "Анализ e-commerce: конверсия воронки продаж (view→cart→checkout→purchase)? "
            "Процент брошенных корзин? Топ-3 категории по GMV (выручке)? "
            "Средний чек и общая выручка? В какой день недели больше всего покупок?"
        ),
        "ground_truth": {
            "total_events":     N_ROWS,
            "total_views":      views,
            "total_purchases":  purchases,
            "total_revenue":    round(total_revenue, 2),
            "avg_order_value":  avg_order_val,
            "overall_conversion_pct": overall_conv,
            "view_to_cart_pct": view_to_cart,
            "cart_to_chk_pct":  cart_to_chk,
            "chk_to_pur_pct":   chk_to_pur,
            "abandon_rate_pct": abandon_rate,
            "top3_categories":  [{"category": c, "gmv": round(g, 2)} for c, g in top3_cat_gmv],
            "top_channel":      top_channel,
            "top_channel_rev":  round(channel_revenue[top_channel], 2),
            "busiest_dow":      dow_names[busiest_dow],
            "busiest_dow_purchases": dow_purchases[busiest_dow],
        },
        "expected_numbers": [
            {"key": "total_events",       "value": N_ROWS,  "tolerance": 0.001},
            {"key": "total_purchases",    "value": purchases, "tolerance": 0.02},
            {"key": "overall_conversion", "value": overall_conv, "tolerance": 0.10},
            {"key": "abandon_rate",       "value": abandon_rate, "tolerance": 0.10},
            {"key": "avg_order_value",    "value": avg_order_val, "tolerance": 0.05},
            {"key": "total_revenue_M",    "value": round(total_revenue / 1e6, 2), "tolerance": 0.05},
        ],
        "required_topics": [
            "конверси", "воронк", "корзин", "выручк", "средний чек", "категори", "день"
        ],
    }
    (OUT_DIR / "ecommerce_events_ground_truth.json").write_text(
        json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_csv.name}  ({out_csv.stat().st_size // 1024} KB)")
    return gt


if __name__ == "__main__":
    generate()

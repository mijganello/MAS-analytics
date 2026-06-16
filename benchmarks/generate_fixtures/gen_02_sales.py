"""Generator: Sales transactions CSV (80 000 rows)."""
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
random.seed(SEED)
OUT_DIR = Path(__file__).parent.parent / "fixtures"

PRODUCTS = [
    ("Ноутбук ProBook 450",       45_000, "Электроника"),
    ("Смартфон Galaxy A54",       28_000, "Электроника"),
    ("Планшет iPad 10",           55_000, "Электроника"),
    ("Наушники Sony WH-1000",     18_000, "Электроника"),
    ("Монитор Dell 27\"",         32_000, "Электроника"),
    ("Кресло Ergohuman",          35_000, "Мебель"),
    ("Стол рабочий IKEA",         12_000, "Мебель"),
    ("Стеллаж металлический",      8_000, "Мебель"),
    ("Принтер HP LaserJet",       22_000, "Оргтехника"),
    ("МФУ Canon MAXIFY",          15_000, "Оргтехника"),
    ("Сканер Epson DS-310",       12_500, "Оргтехника"),
    ("Клавиатура Logitech MX",     6_500, "Периферия"),
    ("Мышь Logitech MX Master",    5_800, "Периферия"),
    ("USB-хаб 7-port",             2_200, "Периферия"),
    ("Веб-камера Logitech C920",   8_500, "Периферия"),
    ("ПО Microsoft Office 365",   11_000, "ПО"),
    ("Антивирус Kaspersky",        3_500, "ПО"),
    ("CRM Bitrix24",              45_000, "ПО"),
    ("Бумага А4 500 л.",             500, "Расходники"),
    ("Картридж HP 305A",           2_800, "Расходники"),
    ("Тонер Samsung",              1_800, "Расходники"),
    ("Папка архивная",               180, "Расходники"),
    ("Маркер Stabilo (набор)",       350, "Расходники"),
    ("Степлер Rapid",              1_200, "Канцелярия"),
    ("Ежедневник кожаный",           800, "Канцелярия"),
]

REGIONS = ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург",
           "Казань", "Нижний Новгород", "Ростов-на-Дону", "Самара"]

REGION_WEIGHTS = [0.30, 0.18, 0.10, 0.09, 0.08, 0.08, 0.09, 0.08]

SALESPERSONS = [f"Менеджер_{i:02d}" for i in range(1, 21)]

CHANNELS = ["Интернет", "Телефон", "Офис", "Партнёр"]
CHANNEL_W = [0.45, 0.25, 0.20, 0.10]

N_ROWS    = 80_000
START_DAY = date(2023, 1, 1)
END_DAY   = date(2024, 12, 31)


def _rand_date():
    delta = (END_DAY - START_DAY).days
    return START_DAY + timedelta(days=random.randint(0, delta))


def generate():
    OUT_DIR.mkdir(exist_ok=True)
    out_csv = OUT_DIR / "sales_transactions.csv"

    total_revenue = 0.0
    quarterly_rev: dict[str, float] = {}
    product_rev: dict[str, float] = {}
    region_rev: dict[str, float] = {}
    rows_written = 0
    all_amounts = []

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "transaction_id", "date", "product", "category", "region",
            "salesperson", "channel", "quantity", "unit_price",
            "discount_pct", "revenue", "margin_pct"
        ])

        for i in range(N_ROWS):
            tx_date = _rand_date()
            prod_name, base_price, category = random.choice(PRODUCTS)
            region     = random.choices(REGIONS, weights=REGION_WEIGHTS)[0]
            salesperson= random.choice(SALESPERSONS)
            channel    = random.choices(CHANNELS, weights=CHANNEL_W)[0]
            quantity   = random.randint(1, 10 if base_price < 5_000 else 3)
            # Price variation ±15%
            unit_price = round(base_price * random.uniform(0.85, 1.15), 2)
            discount   = round(random.choices(
                [0, 5, 10, 15, 20],
                weights=[0.40, 0.25, 0.20, 0.10, 0.05]
            )[0], 1)
            revenue    = round(unit_price * quantity * (1 - discount / 100), 2)
            margin     = round(random.uniform(8, 45), 1)

            # Seasonal boost: Q4 (Oct–Dec) +30%
            if tx_date.month in (10, 11, 12) and random.random() < 0.30:
                quantity  = min(quantity * 2, 20)
                revenue   = round(unit_price * quantity * (1 - discount / 100), 2)

            q_key = f"Q{(tx_date.month - 1) // 3 + 1}_{tx_date.year}"
            quarterly_rev[q_key] = quarterly_rev.get(q_key, 0.0) + revenue
            product_rev[prod_name]  = product_rev.get(prod_name, 0.0) + revenue
            region_rev[region]      = region_rev.get(region, 0.0) + revenue
            total_revenue += revenue
            all_amounts.append(revenue)

            writer.writerow([
                f"TX-{i+1:06d}", tx_date.isoformat(), prod_name, category,
                region, salesperson, channel, quantity,
                unit_price, discount, revenue, margin,
            ])
            rows_written += 1

    top5_products = sorted(product_rev.items(), key=lambda x: x[1], reverse=True)[:5]
    top3_regions  = sorted(region_rev.items(),  key=lambda x: x[1], reverse=True)[:3]
    worst_region  = min(region_rev, key=region_rev.get)
    avg_check     = round(total_revenue / N_ROWS, 2)
    peak_quarter  = max(quarterly_rev, key=quarterly_rev.get)

    gt = {
        "dataset_id": "02_sales",
        "file": "sales_transactions.csv",
        "description": "B2B sales transactions, 2023-2024, 25 products, 8 regions",
        "query": (
            "Проанализируй продажи: какова общая выручка и средний чек за период? "
            "Топ-5 продуктов и топ-3 региона по выручке? "
            "Какой регион показал наихудший результат? "
            "Динамика выручки по кварталам — в каком квартале пик?"
        ),
        "ground_truth": {
            "total_revenue":     round(total_revenue, 2),
            "total_transactions": N_ROWS,
            "avg_check":         avg_check,
            "top1_product":      top5_products[0][0],
            "top1_product_rev":  round(top5_products[0][1], 2),
            "top5_products":     [{"product": p, "revenue": round(r, 2)} for p, r in top5_products],
            "top3_regions":      [{"region": r, "revenue": round(v, 2)} for r, v in top3_regions],
            "worst_region":      worst_region,
            "worst_region_rev":  round(region_rev[worst_region], 2),
            "peak_quarter":      peak_quarter,
            "peak_quarter_rev":  round(quarterly_rev[peak_quarter], 2),
        },
        "expected_numbers": [
            {"key": "total_revenue",     "value": round(total_revenue / 1e6, 2),   "tolerance": 0.02, "note": "млн руб."},
            {"key": "total_transactions","value": N_ROWS,                            "tolerance": 0.001},
            {"key": "avg_check",         "value": avg_check,                        "tolerance": 0.05},
            {"key": "top1_product_rev",  "value": round(top5_products[0][1] / 1e6, 2), "tolerance": 0.05},
        ],
        "required_topics": [
            "выручк", "продукт", "регион", "квартал", "средний чек", "топ", "динамик"
        ],
    }
    (OUT_DIR / "sales_transactions_ground_truth.json").write_text(
        json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_csv.name}  ({out_csv.stat().st_size // 1024} KB)")
    return gt


if __name__ == "__main__":
    generate()

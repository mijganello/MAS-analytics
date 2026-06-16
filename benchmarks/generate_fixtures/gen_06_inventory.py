"""Generator: Warehouse inventory CSV (30 000 SKUs)."""
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
random.seed(SEED)
OUT_DIR = Path(__file__).parent.parent / "fixtures"

CATEGORIES = {
    "Электроника":   (0.18, 12_000,  80_000),
    "Мебель":        (0.10, 4_000,   45_000),
    "Оргтехника":    (0.12, 8_000,   35_000),
    "Периферия":     (0.15, 1_500,   15_000),
    "ПО":            (0.05, 5_000,   60_000),
    "Расходники":    (0.20, 200,     3_000),
    "Канцелярия":    (0.10, 80,      800),
    "Инструменты":   (0.07, 1_200,   18_000),
    "Запасные части":(0.03, 500,     12_000),
}

SUPPLIERS = [f"Поставщик_{i}" for i in range(1, 51)]
WAREHOUSES = ["Москва-Север", "Москва-Юг", "СПб", "Екатеринбург", "Новосибирск"]

N_SKUS = 30_000


def generate():
    OUT_DIR.mkdir(exist_ok=True)
    out_csv = OUT_DIR / "warehouse_inventory.csv"

    cat_stats: dict[str, dict] = {
        c: {"count": 0, "frozen_capital": 0.0, "below_min": 0, "total_stock_value": 0.0}
        for c in CATEGORIES
    }
    total_frozen = 0.0
    total_below_min = 0

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "sku_id", "product_name", "category", "supplier", "warehouse",
            "current_stock", "min_stock", "max_stock", "reorder_point",
            "unit_cost", "stock_value", "days_of_supply", "last_reorder_date",
            "avg_daily_demand", "turnover_days", "status"
        ])

        for i in range(N_SKUS):
            # Pick category weighted
            cat = random.choices(list(CATEGORIES.keys()),
                                  weights=[v[0] for v in CATEGORIES.values()])[0]
            _, price_lo, price_hi = CATEGORIES[cat]

            unit_cost      = round(random.uniform(price_lo, price_hi), 2)
            min_stock      = random.randint(5, 50)
            max_stock      = min_stock * random.randint(5, 20)
            reorder_point  = int(min_stock * 1.5)
            avg_demand     = round(random.uniform(0.5, 15.0), 2)  # units/day

            # Stock level: sometimes critical
            critical = random.random() < 0.08
            if critical:
                current_stock = random.randint(0, min_stock - 1)
            else:
                current_stock = random.randint(reorder_point, max_stock)

            stock_value  = round(current_stock * unit_cost, 2)
            turnover     = round(max_stock / max(avg_demand, 0.1), 1)  # days
            dos          = round(current_stock / max(avg_demand, 0.1), 1)
            last_reorder = date(2025, 1, 1) - timedelta(days=random.randint(1, 90))
            warehouse    = random.choice(WAREHOUSES)
            supplier     = random.choice(SUPPLIERS)

            if current_stock == 0:
                status = "НУЛЕВОЙ"
            elif current_stock < min_stock:
                status = "КРИТИЧЕСКИЙ"
            elif current_stock < reorder_point:
                status = "НИЗКИЙ"
            elif current_stock > max_stock * 0.9:
                status = "ИЗБЫТОК"
            else:
                status = "НОРМА"

            frozen = stock_value if current_stock > max_stock * 0.8 else 0.0

            cat_stats[cat]["count"] += 1
            cat_stats[cat]["total_stock_value"] += stock_value
            cat_stats[cat]["frozen_capital"]    += frozen
            if current_stock < min_stock:
                cat_stats[cat]["below_min"] += 1
                total_below_min += 1
            total_frozen += frozen

            writer.writerow([
                f"SKU-{i+1:06d}",
                f"Товар_{cat[:4]}_{i+1}",
                cat, supplier, warehouse,
                current_stock, min_stock, max_stock, reorder_point,
                unit_cost, stock_value, dos, last_reorder.isoformat(),
                avg_demand, turnover, status
            ])

    worst_cat   = max(cat_stats, key=lambda c: cat_stats[c]["below_min"])
    richest_cat = max(cat_stats, key=lambda c: cat_stats[c]["frozen_capital"])

    gt = {
        "dataset_id": "06_inventory",
        "file": "warehouse_inventory.csv",
        "description": "Warehouse: 30 000 SKUs across 9 categories, 5 warehouses",
        "query": (
            "Анализ склада: сколько позиций ниже минимального запаса (статус КРИТИЧЕСКИЙ/НУЛЕВОЙ)? "
            "В какой категории товаров больше всего проблемных позиций? "
            "Какова суммарная стоимость замороженного капитала (позиции с избыточным запасом)? "
            "Средняя оборачиваемость склада по категориям (в днях)?"
        ),
        "ground_truth": {
            "total_skus":          N_SKUS,
            "total_below_min":     total_below_min,
            "pct_below_min":       round(total_below_min / N_SKUS * 100, 2),
            "worst_category":      worst_cat,
            "worst_cat_below_min": cat_stats[worst_cat]["below_min"],
            "total_frozen_capital": round(total_frozen, 2),
            "richest_frozen_cat":  richest_cat,
            "cat_stats":           {c: {k: round(v, 2) if isinstance(v, float) else v
                                         for k, v in s.items()}
                                     for c, s in cat_stats.items()},
        },
        "expected_numbers": [
            {"key": "total_skus",      "value": N_SKUS,  "tolerance": 0.001},
            {"key": "total_below_min", "value": total_below_min, "tolerance": 0.05},
            {"key": "pct_below_min",   "value": round(total_below_min / N_SKUS * 100, 1), "tolerance": 0.10},
            {"key": "frozen_millions", "value": round(total_frozen / 1e6, 1), "tolerance": 0.10},
        ],
        "required_topics": [
            "дефицит", "минимальн", "критическ", "замороженн", "капитал", "категори", "оборачиваемост"
        ],
    }
    (OUT_DIR / "warehouse_inventory_ground_truth.json").write_text(
        json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_csv.name}  ({out_csv.stat().st_size // 1024} KB)")
    return gt


if __name__ == "__main__":
    generate()

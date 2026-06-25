"""Dataset 04: Online shop reviews — 15 products (small) / 1000+ (big)."""
import csv
import json
import random
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "fixtures"
COLUMNS = ["product_id", "product_name", "category", "avg_rating", "review_count", "returns_count"]

CATEGORIES = ["Электроника", "Мебель", "Освещение", "Аксессуары", "Оргтехника",
              "Бытовая техника", "Спорт", "Книги", "Одежда", "Детские товары"]

ADJECTIVES = ["Pro", "Ultra", "Max", "Comfort", "Smart", "Eco", "Premium", "Lite",
              "Classic", "Modern", "Wireless", "HD", "XL", "Mini", "Plus"]
NOUNS = ["Ноутбук", "Мышь", "Кресло", "Монитор", "Клавиатура", "Стол", "Наушники",
         "Лампа", "Коврик", "Камера", "Принтер", "Полка", "Хаб", "Подставка",
         "Фильтр", "Вентилятор", "Чайник", "Миксер", "Утюг", "Пылесос"]

SMALL_DATA = [
    (1,  "Ноутбук Pro 15",     "Электроника", 4.7, 234, 12),
    (2,  "Мышь Wireless X",    "Электроника", 4.3, 567, 28),
    (3,  "Кресло Comfort",     "Мебель",      4.1, 189, 31),
    (4,  "Монитор 27 Ultra",   "Электроника", 4.6, 312, 15),
    (5,  "Клавиатура Mech",    "Электроника", 4.8, 421, 9),
    (6,  "Стол Office",        "Мебель",      3.9, 156, 42),
    (7,  "Наушники BT Pro",    "Электроника", 4.4, 278, 19),
    (8,  "Лампа LED Desk",     "Освещение",   4.5, 134, 8),
    (9,  "Коврик для мыши XL", "Аксессуары",  4.0, 89,  11),
    (10, "Веб-камера HD",      "Электроника", 4.2, 345, 22),
    (11, "Принтер Laser",      "Оргтехника",  3.7, 167, 38),
    (12, "Полка Kallax",       "Мебель",      4.4, 523, 17),
    (13, "USB-хаб 7-in-1",     "Аксессуары",  4.1, 412, 14),
    (14, "Подставка для ноутб.", "Аксессуары", 4.6, 198, 7),
    (15, "Сетевой фильтр",     "Аксессуары",  4.3, 156, 10),
]


def _compute_gt(data):
    total_reviews = sum(r[4] for r in data)
    total_returns = sum(r[5] for r in data)
    avg_rating = round(sum(r[3] * r[4] for r in data) / total_reviews, 3)
    below_4 = sum(1 for r in data if r[3] < 4.0)
    top_rated = max(data, key=lambda r: r[3])[3]
    cat_reviews: dict[str, int] = {}
    for r in data:
        cat_reviews[r[2]] = cat_reviews.get(r[2], 0) + r[4]
    top_category = max(cat_reviews, key=cat_reviews.__getitem__)
    top_category_reviews = cat_reviews[top_category]
    return total_reviews, total_returns, avg_rating, below_4, top_rated, top_category, top_category_reviews


def generate(big: bool = False):
    OUT_DIR.mkdir(exist_ok=True)

    if big:
        random.seed(789)
        total_rows = 2000
        used_names = set()
        data = []
        for i in range(1, total_rows + 1):
            # Guarantee unique product names using index
            adj = ADJECTIVES[i % len(ADJECTIVES)]
            noun = NOUNS[(i // len(ADJECTIVES)) % len(NOUNS)]
            suffix_num = i // (len(ADJECTIVES) * len(NOUNS))
            suffix_str = f" {suffix_num}" if suffix_num > 0 else ""
            name = f"{noun} {adj}{suffix_str}"
            cat = random.choice(CATEGORIES)
            rating = round(random.uniform(3.0, 5.0), 1)
            reviews = random.randint(10, 800)
            returns = random.randint(0, max(1, int(reviews * random.uniform(0.01, 0.25))))
            data.append((i, name, cat, rating, reviews, returns))
    else:
        data = SMALL_DATA

    suffix = "_big" if big else ""
    out_csv = OUT_DIR / f"shop_reviews{suffix}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(data)

    total_reviews, total_returns, avg_rating, below_4, top_rated, top_category, top_category_reviews = _compute_gt(data)

    gt = {
        "dataset_id": f"04_shop_reviews{suffix}",
        "file": f"shop_reviews{suffix}.csv",
        "description": f"Отзывы интернет-магазина, {len(data)} товаров",
        "query": (
            "Проанализируй отзывы интернет-магазина. Ответь точно:\n"
            "1. Сколько всего отзывов?\n"
            "2. Сколько всего возвратов?\n"
            "3. Какова средневзвешенная оценка?\n"
            "4. Сколько товаров с оценкой ниже 4.0?\n"
            "5. Какова максимальная средняя оценка товара?\n"
            "6. Сколько отзывов у самой популярной категории?"
        ),
        "ground_truth": {
            "total_reviews": total_reviews,
            "total_returns": total_returns,
            "avg_rating": avg_rating,
            "below_4_count": below_4,
            "top_rating": top_rated,
            "top_category": top_category,
            "top_category_reviews": top_category_reviews,
        },
        "expected_numbers": [
            {"key": "total_reviews", "question": "Всего отзывов?", "value": total_reviews, "tolerance": 0.02},
            {"key": "total_returns", "question": "Всего возвратов?", "value": total_returns, "tolerance": 0.02},
            {"key": "avg_rating", "question": "Средневзвешенная оценка?", "value": avg_rating, "tolerance": 0.02},
            {"key": "below_4_count", "question": "Товаров с оценкой < 4.0?", "value": below_4, "tolerance": 0.02},
            {"key": "top_rating", "question": "Максимальная оценка?", "value": top_rated, "tolerance": 0.01},
            {"key": "top_category_reviews", "question": "Отзывов в топ-категории?", "value": top_category_reviews, "tolerance": 0.02},
        ],
    }
    gt_path = OUT_DIR / f"shop_reviews{suffix}_ground_truth.json"
    gt_path.write_text(json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_csv.name} ({len(data)} rows) → {gt_path.name}")
    return gt


if __name__ == "__main__":
    big = "--big" in __import__("sys").argv
    generate(big=big)


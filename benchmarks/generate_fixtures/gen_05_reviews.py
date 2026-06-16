"""Generator: Customer reviews TXT (10 000 reviews)."""
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
random.seed(SEED)
OUT_DIR = Path(__file__).parent.parent / "fixtures"

PRODUCTS = [
    ("Ноутбук ProBook",   {"1": 0.05, "2": 0.08, "3": 0.15, "4": 0.35, "5": 0.37}),
    ("Смартфон GalaxyX",  {"1": 0.07, "2": 0.10, "3": 0.18, "4": 0.30, "5": 0.35}),
    ("Наушники SoundMax", {"1": 0.04, "2": 0.06, "3": 0.12, "4": 0.38, "5": 0.40}),
    ("Планшет ProTab",    {"1": 0.10, "2": 0.14, "3": 0.20, "4": 0.28, "5": 0.28}),
    ("Монитор UltraView", {"1": 0.03, "2": 0.05, "3": 0.14, "4": 0.40, "5": 0.38}),
    ("МФУ PrintPro",      {"1": 0.12, "2": 0.16, "3": 0.22, "4": 0.28, "5": 0.22}),
    ("Клавиатура MechKey",{"1": 0.04, "2": 0.07, "3": 0.15, "4": 0.36, "5": 0.38}),
    ("Веб-камера ClearCam",{"1":0.08, "2": 0.11, "3": 0.20, "4": 0.33, "5": 0.28}),
]

POSITIVE_PHRASES = [
    "Отличное качество сборки, всем доволен.",
    "Работает быстро, без нареканий.",
    "Очень доволен покупкой, рекомендую.",
    "Соответствует описанию, доставка быстрая.",
    "Отличное соотношение цена/качество.",
    "Пользуюсь уже полгода — полёт нормальный.",
    "Быстрая зарядка, долго держит заряд.",
    "Прекрасный дизайн, удобен в использовании.",
    "Звук чистый, без помех, очень доволен.",
    "Экран яркий, цвета сочные.",
]

NEGATIVE_PHRASES = [
    "Перегревается при нагрузке, разочарован.",
    "Батарея садится быстро, не оправдывает ожидания.",
    "Качество сборки оставляет желать лучшего.",
    "Шумит вентилятор, мешает работать.",
    "Долго ждал доставки, упаковка была помята.",
    "Зависает, приходится перезагружать.",
    "Оказался бракованным, пришлось вернуть.",
    "Не соответствует описанию на сайте.",
    "Слабый процессор, не справляется с задачами.",
    "Постоянно глючит, очень разочарован.",
]

NEUTRAL_PHRASES = [
    "В целом нормально, но есть нюансы.",
    "Ожидал немного большего за эту цену.",
    "Пойдёт для базового использования.",
    "Есть и плюсы, и минусы — средний вариант.",
    "Не шедевр, но и не плохой.",
    "Приемлемо для домашнего использования.",
    "Покупкой удовлетворён на 50%.",
]

N_REVIEWS = 10_000
START_DATE = date(2023, 1, 1)
END_DATE   = date(2024, 12, 31)


def _rand_date():
    return START_DATE + timedelta(days=random.randint(0, (END_DATE - START_DATE).days))


def generate():
    OUT_DIR.mkdir(exist_ok=True)
    out_txt = OUT_DIR / "customer_reviews.txt"

    product_stats: dict[str, dict] = {
        p: {"ratings": [], "count": 0} for p, _ in PRODUCTS
    }
    monthly_ratings: dict[str, list] = {}
    lines = []

    for i in range(N_REVIEWS):
        prod_name, rating_dist = random.choice(PRODUCTS)
        rating = int(random.choices(
            list(rating_dist.keys()),
            weights=list(rating_dist.values())
        )[0])

        if rating >= 4:
            text = random.choice(POSITIVE_PHRASES)
            # Add more detail for high ratings
            if random.random() < 0.5:
                text += " " + random.choice(POSITIVE_PHRASES)
        elif rating <= 2:
            text = random.choice(NEGATIVE_PHRASES)
            if random.random() < 0.5:
                text += " " + random.choice(NEGATIVE_PHRASES)
        else:
            text = random.choice(NEUTRAL_PHRASES)

        rev_date = _rand_date()
        month_key = rev_date.strftime("%Y-%m")

        lines.append(
            f"[{i+1:05d}] {rev_date.isoformat()} | Товар: {prod_name} | "
            f"Оценка: {rating}/5 | {text}"
        )

        product_stats[prod_name]["ratings"].append(rating)
        product_stats[prod_name]["count"] += 1
        monthly_ratings.setdefault(month_key, []).append(rating)

    out_txt.write_text("\n".join(lines), encoding="utf-8")

    # Ground truth
    for p in product_stats:
        rs = product_stats[p]["ratings"]
        product_stats[p]["avg_rating"]  = round(sum(rs) / len(rs), 2)
        product_stats[p]["pct_negative"] = round(sum(1 for r in rs if r <= 2) / len(rs) * 100, 2)

    all_ratings = [r for p in product_stats.values() for r in p["ratings"]]
    overall_avg = round(sum(all_ratings) / len(all_ratings), 2)
    worst_product = min(product_stats, key=lambda p: product_stats[p]["avg_rating"])
    best_product  = max(product_stats, key=lambda p: product_stats[p]["avg_rating"])

    monthly_nps = {m: round(sum(1 for r in rs if r >= 4) / len(rs) * 100 -
                            sum(1 for r in rs if r <= 2) / len(rs) * 100, 1)
                   for m, rs in monthly_ratings.items()}
    best_month  = max(monthly_nps, key=monthly_nps.get)
    worst_month = min(monthly_nps, key=monthly_nps.get)

    gt = {
        "dataset_id": "05_reviews",
        "file": "customer_reviews.txt",
        "description": "10 000 customer reviews for 8 products, 2023-2024",
        "query": (
            "Анализ отзывов: какой средний рейтинг по всем продуктам? "
            "Какой товар получил наилучшие и наихудшие оценки? "
            "Каков % негативных отзывов (оценка ≤2) для каждого продукта? "
            "Динамика NPS по месяцам — когда лучший и худший месяц?"
        ),
        "ground_truth": {
            "total_reviews":    N_REVIEWS,
            "overall_avg_rating": overall_avg,
            "best_product":     best_product,
            "best_avg_rating":  product_stats[best_product]["avg_rating"],
            "worst_product":    worst_product,
            "worst_avg_rating": product_stats[worst_product]["avg_rating"],
            "worst_product_neg_pct": product_stats[worst_product]["pct_negative"],
            "best_nps_month":   best_month,
            "worst_nps_month":  worst_month,
            "product_stats":    {p: {"avg_rating": v["avg_rating"],
                                      "count": v["count"],
                                      "pct_negative": v["pct_negative"]}
                                  for p, v in product_stats.items()},
        },
        "expected_numbers": [
            {"key": "total_reviews",   "value": N_REVIEWS, "tolerance": 0.001},
            {"key": "overall_avg",     "value": overall_avg, "tolerance": 0.05},
            {"key": "worst_neg_pct",   "value": product_stats[worst_product]["pct_negative"], "tolerance": 0.10},
        ],
        "required_topics": [
            "рейтинг", "отзыв", "негатив", "продукт", "nps", "оценк", "месяц"
        ],
    }
    (OUT_DIR / "customer_reviews_ground_truth.json").write_text(
        json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_txt.name}  ({out_txt.stat().st_size // 1024} KB)")
    return gt


if __name__ == "__main__":
    generate()

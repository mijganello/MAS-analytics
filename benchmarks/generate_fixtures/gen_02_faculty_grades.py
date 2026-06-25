"""Dataset 02: Faculty grades — 18 exam records (small) / 1000+ (big)."""
import csv
import json
import random
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "fixtures"
COLUMNS = ["record_id", "student", "course", "grade", "semester", "teacher"]

STUDENTS = ["Иванов", "Сидорова", "Козлов", "Новикова", "Морозов", "Лебедев",
            "Соколов", "Попова", "Фёдоров", "Михайлова", "Егоров", "Никитина",
            "Семёнов", "Громова", "Титов", "Орлов", "Зайцева", "Кузнецова",
            "Алексеев", "Борисова", "Власов", "Григорьев", "Дмитриева", "Ефимов",
            "Жуков", "Захаров", "Игнатов", "Кириллов", "Лазарев", "Максимова"]

COURSES = ["Матанализ", "Программирование", "Физика", "Алгоритмы", "Базы данных",
           "Линейная алгебра", "Дискретная математика", "ОС", "Сети", "Статистика"]

TEACHERS = ["Петров", "Смирнов", "Волкова", "Кузнецов", "Орлова",
            "Новиков", "Морозова", "Лебедев", "Соколова", "Попов"]

SEMESTERS = ["2024-осень", "2024-весна", "2025-осень", "2025-весна"]

# Small fixture data
SMALL_DATA = [
    (1,  "Иванов",    "Матанализ",      5, "2024-осень",  "Петров"),
    (2,  "Сидорова",  "Матанализ",      4, "2024-осень",  "Петров"),
    (3,  "Козлов",    "Программирование", 3, "2024-осень", "Смирнов"),
    (4,  "Новикова",  "Программирование", 5, "2024-осень", "Смирнов"),
    (5,  "Морозов",   "Физика",         2, "2024-осень",  "Волкова"),
    (6,  "Лебедев",   "Физика",         4, "2024-осень",  "Волкова"),
    (7,  "Соколов",   "Алгоритмы",      5, "2024-осень",  "Кузнецов"),
    (8,  "Попова",    "Алгоритмы",      4, "2024-осень",  "Кузнецов"),
    (9,  "Фёдоров",   "Базы данных",    3, "2024-осень",  "Орлова"),
    (10, "Михайлова", "Базы данных",    5, "2024-осень",  "Орлова"),
    (11, "Егоров",    "Матанализ",      3, "2024-весна",  "Петров"),
    (12, "Никитина",  "Программирование", 4, "2024-весна", "Смирнов"),
    (13, "Семёнов",   "Физика",         3, "2024-весна",  "Волкова"),
    (14, "Громова",   "Алгоритмы",      2, "2024-весна",  "Кузнецов"),
    (15, "Титов",     "Базы данных",    4, "2024-весна",  "Орлова"),
    (16, "Орлов",     "Матанализ",      5, "2024-весна",  "Петров"),
    (17, "Зайцева",   "Программирование", 5, "2024-весна", "Смирнов"),
    (18, "Кузнецова", "Физика",         4, "2024-весна",  "Волкова"),
]


def _compute_gt(data):
    grades = [r[3] for r in data]
    avg_grade = round(sum(grades) / len(grades), 3)
    below_3 = sum(1 for g in grades if g < 3)
    grade_5 = sum(1 for g in grades if g == 5)
    course_avg: dict[str, list] = {}
    for r in data:
        course_avg.setdefault(r[2], []).append(r[3])
    best_course = max(course_avg, key=lambda c: sum(course_avg[c]) / len(course_avg[c]))
    best_course_avg = round(sum(course_avg[best_course]) / len(course_avg[best_course]), 3)
    return avg_grade, below_3, grade_5, best_course, best_course_avg, len(course_avg)


def generate(big: bool = False):
    OUT_DIR.mkdir(exist_ok=True)

    if big:
        random.seed(123)
        total_rows = 1500
        data = []
        for i in range(1, total_rows + 1):
            student = random.choice(STUDENTS)
            course = random.choice(COURSES)
            # Grade distribution: mostly 3-5, few 2
            grade = random.choices([2, 3, 4, 5], weights=[5, 25, 40, 30])[0]
            semester = random.choice(SEMESTERS)
            teacher = random.choice(TEACHERS)
            data.append((i, student, course, grade, semester, teacher))
    else:
        data = SMALL_DATA

    suffix = "_big" if big else ""
    out_csv = OUT_DIR / f"faculty_grades{suffix}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(data)

    avg_grade, below_3, grade_5, best_course, best_course_avg, unique_courses = _compute_gt(data)

    gt = {
        "dataset_id": f"02_faculty_grades{suffix}",
        "file": f"faculty_grades{suffix}.csv",
        "description": f"Оценки студентов кафедры за семестры, {len(data)} записей",
        "query": (
            "Проанализируй оценки на кафедре. Ответь точно:\n"
            "1. Сколько всего оценок в таблице?\n"
            "2. Какова средняя оценка?\n"
            "3. Сколько оценок ниже 3 (неудовлетворительно)?\n"
            "4. Сколько отличных оценок (5)?\n"
            "5. Какой курс имеет наивысший средний балл и какой он?\n"
            "6. Сколько уникальных дисциплин?"
        ),
        "ground_truth": {
            "total_records": len(data),
            "avg_grade": avg_grade,
            "below_3_count": below_3,
            "grade_5_count": grade_5,
            "best_course": best_course,
            "best_course_avg": best_course_avg,
            "unique_courses": unique_courses,
        },
        "expected_numbers": [
            {"key": "total_records", "question": "Всего оценок?", "value": len(data), "tolerance": 0.001},
            {"key": "avg_grade", "question": "Средняя оценка?", "value": avg_grade, "tolerance": 0.02},
            {"key": "below_3_count", "question": "Оценок ниже 3?", "value": below_3, "tolerance": 0.02},
            {"key": "grade_5_count", "question": "Отличных оценок (5)?", "value": grade_5, "tolerance": 0.02},
            {"key": "best_course_avg", "question": "Средний балл лучшего курса?", "value": best_course_avg, "tolerance": 0.02},
            {"key": "unique_courses", "question": "Уникальных дисциплин?", "value": unique_courses, "tolerance": 0.001},
        ],
    }
    gt_path = OUT_DIR / f"faculty_grades{suffix}_ground_truth.json"
    gt_path.write_text(json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_csv.name} ({len(data)} rows) → {gt_path.name}")
    return gt


if __name__ == "__main__":
    big = "--big" in __import__("sys").argv
    generate(big=big)


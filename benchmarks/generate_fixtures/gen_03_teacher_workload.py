"""Dataset 03: Teacher workload — 10 (small) / 1000+ (big)."""
import csv
import json
import random
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "fixtures"
COLUMNS = ["teacher", "department", "courses", "students", "hours_per_week", "exams_count"]

DEPARTMENTS = ["Математика", "Информатика", "Физика", "Химия", "Биология",
               "История", "Филология", "Экономика", "Право", "Психология"]

TEACHER_FIRST = ["Петров", "Смирнов", "Волкова", "Кузнецов", "Орлова",
                 "Новиков", "Морозова", "Лебедев", "Соколова", "Попов",
                 "Алексеев", "Борисова", "Власов", "Григорьев", "Дмитриева",
                 "Ефимов", "Жуков", "Захаров", "Игнатов", "Кириллова"]

TEACHER_LAST = ["А", "Б", "В", "Г", "Д", "Е", "Ж", "З", "И", "К",
                "Л", "М", "Н", "О", "П", "Р", "С", "Т", "У", "Ф"]

SMALL_DATA = [
    ("Петров",   "Математика",       3, 87, 18, 2),
    ("Смирнов",  "Информатика",     4, 112, 22, 3),
    ("Волкова",  "Физика",          2, 64, 14, 1),
    ("Кузнецов", "Информатика",     3, 95, 19, 2),
    ("Орлова",   "Информатика",     2, 58, 12, 1),
    ("Новиков",  "Математика",      2, 71, 15, 2),
    ("Морозова", "Физика",          3, 78, 17, 2),
    ("Лебедев",  "Математика",      4, 103, 21, 3),
    ("Соколова", "Информатика",     1, 42, 8, 1),
    ("Попов",    "Физика",          2, 56, 13, 1),
]


def _compute_gt(data):
    total_students = sum(r[3] for r in data)
    total_hours = sum(r[4] for r in data)
    max_hours_row = max(data, key=lambda r: r[4])
    max_hours = max_hours_row[4]
    max_hours_teacher = max_hours_row[0]
    avg_students = round(total_students / len(data), 2)
    cs_students = sum(r[3] for r in data if r[1] == "Информатика")
    overloaded = sum(1 for r in data if r[4] > 18)
    return total_students, total_hours, max_hours_teacher, max_hours, avg_students, cs_students, overloaded


def generate(big: bool = False):
    OUT_DIR.mkdir(exist_ok=True)

    if big:
        random.seed(456)
        total_rows = 1000
        used_names = set()
        data = []
        for i in range(total_rows):
            # Generate unique teacher names — use index to guarantee uniqueness
            first = TEACHER_FIRST[i % len(TEACHER_FIRST)]
            last = TEACHER_LAST[i % len(TEACHER_LAST)]
            suffix = chr(ord('А') + (i // (len(TEACHER_FIRST) * len(TEACHER_LAST))) % 32)
            name = f"{first} {last}{suffix}."
            dept = random.choice(DEPARTMENTS)
            courses = random.randint(1, 5)
            students = random.randint(20, 150)
            hours = random.randint(4, 28)
            exams = random.randint(0, 4)
            data.append((name, dept, courses, students, hours, exams))
    else:
        data = SMALL_DATA

    suffix = "_big" if big else ""
    out_csv = OUT_DIR / f"teacher_workload{suffix}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(data)

    total_students, total_hours, max_hours_teacher, max_hours, avg_students, cs_students, overloaded = _compute_gt(data)

    gt = {
        "dataset_id": f"03_teacher_workload{suffix}",
        "file": f"teacher_workload{suffix}.csv",
        "description": f"Нагрузка {len(data)} преподавателей кафедры",
        "query": (
            "Проанализируй нагрузку преподавателей. Ответь точно:\n"
            "1. Сколько всего преподавателей?\n"
            "2. Сколько всего студентов у кафедры?\n"
            "3. Какова суммарная нагрузка в часах в неделю?\n"
            "4. У кого максимальная нагрузка (ч/нед) и сколько именно?\n"
            "5. Какова средняя численность группы у преподавателя?\n"
            "6. Сколько студентов у кафедры информатики?\n"
            "7. Сколько преподавателей с нагрузкой выше 18 ч/нед?"
        ),
        "ground_truth": {
            "total_teachers": len(data),
            "total_students": total_students,
            "total_hours": total_hours,
            "max_hours_teacher": max_hours_teacher,
            "max_hours": max_hours,
            "avg_students": avg_students,
            "cs_students": cs_students,
            "overloaded_count": overloaded,
        },
        "expected_numbers": [
            {"key": "total_teachers", "question": "Всего преподавателей?", "value": len(data), "tolerance": 0.001},
            {"key": "total_students", "question": "Всего студентов?", "value": total_students, "tolerance": 0.02},
            {"key": "total_hours", "question": "Суммарная нагрузка (ч/нед)?", "value": total_hours, "tolerance": 0.02},
            {"key": "max_hours", "question": "Максимальная нагрузка (ч/нед)?", "value": max_hours, "tolerance": 0.001},
            {"key": "avg_students", "question": "Средняя численность группы?", "value": avg_students, "tolerance": 0.02},
            {"key": "cs_students", "question": "Студентов у информатики?", "value": cs_students, "tolerance": 0.02},
            {"key": "overloaded_count", "question": "Преподавателей > 18 ч/нед?", "value": overloaded, "tolerance": 0.02},
        ],
    }
    gt_path = OUT_DIR / f"teacher_workload{suffix}_ground_truth.json"
    gt_path.write_text(json.dumps(gt, ensure_ascii=False, indent=2))
    print(f"✓ {out_csv.name} ({len(data)} rows) → {gt_path.name}")
    return gt


if __name__ == "__main__":
    big = "--big" in __import__("sys").argv
    generate(big=big)


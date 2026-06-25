# Ручная проверка бенчмарка (5 датасетов)

## Принцип

Каждый датасет содержит **6–7 конкретных вопросов** с числовыми ответами в `expected_numbers`.
Проверка ответа модели:

```
|число_в_ответе − expected| / |expected| ≤ tolerance  →  ✓
```

**HI** (source-grounded): доля чисел в ответе, которые **нельзя вывести из исходного файла** (±2%).

Число считается *верифицированным*, если оно:
- встречается в ячейках CSV, или
- является стандартным агрегатом (SUM, MEAN, MAX, COUNT, GROUP BY, weighted avg, …), или
- совпадает с эталоном из `expected_numbers`.

Числа вне этого множества — **галлюцинации** (выдуманные или ошибочно «извлечённые»).

```
HI = галлюцинированные / (все_числа_в_ответе + 1)   →  [0, 1), меньше = лучше
```

Работает одинаково для **Naive** и **MAS** — оба режима сводятся к `response_text`.

| HI | Интерпретация |
|----|---------------|
| 0.0 – 0.1 | Почти все числа из данных |
| 0.1 – 0.3 | Есть лишние, но немного |
| > 0.5 | Много чисел не из источника |

**HI ≠ answers.** Модель может процитировать сырую таблицу (низкий HI), но не ответить на вопросы (низкий answers). И наоборот: перепутать SUM с MEAN — ошибка answers, но не галлюцинация (MEAN верифицируется из файла).

## Датасеты

| ID | Файл | Строк | Тема |
|----|------|-------|------|
| 01_rocket_launch | rocket_launches.csv | 12 | Запуски ракет |
| 02_faculty_grades | faculty_grades.csv | 18 | Оценки на кафедре |
| 03_teacher_workload | teacher_workload.csv | 10 | Нагрузка преподавателей |
| 04_shop_reviews | shop_reviews.csv | 15 | Отзывы интернет-магазина |
| 05_server_logs | server_logs.csv | 20 | Серверные логи |

## Быстрая проверка ground truth

```bash
python3 benchmarks/generate_fixtures/generate_all.py --force
python3 -c "
import json
gt = json.load(open('benchmarks/fixtures/rocket_launches_ground_truth.json'))
for e in gt['expected_numbers']:
    print(f\"{e['key']}: {e['value']}\")
"
```

## Пример ручного расчёта (01 rocket)

| Вопрос | Формула | Поле |
|--------|---------|------|
| Всего запусков | COUNT(rows) | total_launches = 12 |
| Успешных | SUM(success=1) | successful_launches = 10 |
| % успеха | 10/12×100 | success_rate_pct = 83.33 |
| Суммарная нагрузка | SUM(payload_kg) | total_payload_kg = 31530 |
| Макс. стоимость | MAX(cost) | max_cost_million = 4210 |
| Средняя высота | AVG(max_altitude_km) | avg_altitude_km = 393.17 |

## Чеклист проверки ответа модели

1. Открыть `*_ground_truth.json` → `expected_numbers`
2. Для каждого вопроса найти число в ответе
3. Проверить допуск
4. Итог: `answers_correct / answers_total`

| answers | Интерпретация |
|---------|---------------|
| 6/6 или 7/7 | Все ответы верны |
| ≥80% | Хорошо |
| <50% | Серьёзные ошибки |

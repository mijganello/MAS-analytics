# MAS Analytics

**Система контролируемой генерации аналитической отчётности на основе LLM**

> Диссертационный проект: многоагентная система с Blackboard-паттерном, Pydantic-валидацией вывода и цифровым слепком данных для повышения точности аналитических отчётов.

## Быстрый старт (3 команды)

```bash
cp .env.example .env          # Заполните DEEPSEEK_API_KEY
docker compose up --build     # Поднять все сервисы
# Открыть http://localhost:5173
```

### С локальной LLaMA (без API-ключей)

```bash
docker compose --profile ollama up --build
docker exec -it $(docker compose ps -q ollama) ollama pull llama3.1:8b
# В .env: LLM_PROVIDER=ollama
```

## Архитектура

Подробное описание — в [architecture.md](./architecture.md).

**Ключевые компоненты:**
- **Blackboard** — централизованная доска состояния; агенты не вызывают друг друга напрямую
- **NumericFingerprint** — слепок всех чисел документа; каждое число верифицируется перед вставкой в отчёт
- **LoopGuard** — TTL-счётчик повторов + EscalationPolicy для предотвращения бесконечных циклов
- **Pydantic-блоки** — каждый тип блока (`ChartBlock`, `KPICard`, `TableBlock`, ...) строго типизирован; React-компонент рендерит его по `block_type`

## Стек

| Компонент | Технология |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy, instructor |
| LLM | DeepSeek API / LLaMA через Ollama |
| Structured output | `instructor` + Pydantic v2 |
| Vector store | PostgreSQL + pgvector |
| Caching / PubSub | Redis |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Charts | Vega-Lite + vega-embed |
| Streaming | SSE (Server-Sent Events) |

## Команды разработки

```bash
# Применить миграции
docker compose exec backend alembic upgrade head

# Тесты
docker compose exec backend pytest tests/ -v

# Логи backend
docker compose logs -f backend

# Production-сборка
BUILD_TARGET=production docker compose up -d
```

## Поддерживаемые форматы файлов

PDF · XLSX · CSV · DOCX · TXT

## Типы блоков отчёта

`text` · `kpi_card` · `table` · `chart` · `insight` · `comparison` · `forecast` · `risk_matrix` · `executive_summary`

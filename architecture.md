# Архитектура системы контролируемой генерации аналитической отчётности на основе LLM

> **Тема диссертации:** Разработка системы контролируемой генерации аналитической отчётности на основе больших языковых моделей  
> **Стек:** Python (backend) · React + TypeScript + Vite + Shadcn (frontend) · DeepSeek API / LLaMA (LLM)

---

## Содержание

1. [Ключевые принципы и цели](#1-ключевые-принципы-и-цели)
2. [Обзор высокоуровневой архитектуры](#2-обзор-высокоуровневой-архитектуры)
3. [Многоагентная система (MAS)](#3-многоагентная-система-mas)
   - 3.1 [Доска объявлений (Blackboard)](#31-доска-объявлений-blackboard)
   - 3.2 [Оркестратор (Chief Agent)](#32-оркестратор-chief-agent)
   - 3.3 [Отделы: исполнители и валидаторы](#33-отделы-исполнители-и-валидаторы)
   - 3.4 [Протокол взаимодействия агентов](#34-протокол-взаимодействия-агентов)
   - 3.5 [Механизм предотвращения бесконечных циклов](#35-механизм-предотвращения-бесконечных-циклов)
4. [Конвейер обработки документов](#4-конвейер-обработки-документов)
   - 4.1 [Загрузка и чанкинг](#41-загрузка-и-чанкинг)
   - 4.2 [Цифровой слепок данных (Data Fingerprint)](#42-цифровой-слепок-данных-data-fingerprint)
   - 4.3 [Векторное хранилище и RAG](#43-векторное-хранилище-и-rag)
5. [Инструментарий агентов (Tools)](#5-инструментарий-агентов-tools)
   - 5.1 [Отдел извлечения данных](#51-отдел-извлечения-данных)
   - 5.2 [Отдел количественного анализа](#52-отдел-количественного-анализа)
   - 5.3 [Отдел качественного анализа](#53-отдел-качественного-анализа)
   - 5.4 [Отдел визуализации](#54-отдел-визуализации)
   - 5.5 [Отдел компиляции отчёта](#55-отдел-компиляции-отчёта)
6. [Pydantic-схемы блоков вывода](#6-pydantic-схемы-блоков-вывода)
7. [Управление токенами и контекстом](#7-управление-токенами-и-контекстом)
8. [Бэкенд-архитектура (Python)](#8-бэкенд-архитектура-python)
9. [Фронтенд-архитектура (React/TS/Vite/Shadcn)](#9-фронтенд-архитектура-reacttsviteshadcn)
10. [LLM-провайдеры: DeepSeek / LLaMA](#10-llm-провайдеры-deepseek--llama)
11. [Схема базы данных](#11-схема-базы-данных)
12. [Безопасность и ограничения](#12-безопасность-и-ограничения)
13. [Структура проекта](#13-структура-проекта)
14. [Зависимости и технологический стек](#14-зависимости-и-технологический-стек)
15. [Docker-инфраструктура](#15-docker-инфраструктура)
16. [Поэтапный план разработки](#16-поэтапный-план-разработки-для-llm-агента)
17. [Журнал архитектурных решений (ADR)](#17-журнал-архитектурных-решений-adr)

---

## 1. Ключевые принципы и цели

| Проблема LLM | Архитектурное решение |
|---|---|
| Галлюцинации при математических операциях | Полное отчуждение арифметики — все вычисления выполняются **инструментами** (pandas, numpy, scipy), LLM только интерпретирует результат |
| Неточное извлечение данных из документов | Чанкинг + **BM25 keyword search** + **цифровой слепок** (хэши числовых значений) для верификации извлечённых данных |
| Нестандартный вывод, сложно разбираемый UI | Все ответы агентов — строго **Pydantic-модели**; каждый тип блока имеет соответствующий React-компонент |
| Потеря контекста при длинных задачах | Декомпозиция на **атомарные подзадачи** + общая «доска» с сжатым состоянием |
| Бесконечные циклы исправлений | **TTL-счётчик** на задачу + escalation-политика + hard-stop |
| Высокая стоимость токенов | Многоуровневое кэширование, сжатый форматированный контекст, модели разного размера под задачу |

---

## 2. Обзор высокоуровневой архитектуры

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React)                               │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  ┌───────────────┐ │
│  │  File Upload │  │  Chat/Query  │  │ Report Canvas │  │ Agent Monitor │ │
│  └──────────────┘  └──────────────┘  └───────────────┘  └───────────────┘ │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ REST + SSE (streaming)
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                         BACKEND API (FastAPI)                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    SESSION MANAGER / TASK QUEUE                      │  │
│  └───────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                          │
│  ┌───────────────────────────────▼──────────────────────────────────────┐  │
│  │                  BLACKBOARD (Redis / in-memory)                      │  │
│  │   task_graph · intermediate_results · agent_messages · locks        │  │
│  └───────┬───────────────────────┬──────────────────┬───────────────────┘  │
│          │                       │                  │                       │
│  ┌───────▼──────┐       ┌────────▼───────┐  ┌──────▼────────┐            │
│  │  ORCHESTRATOR │       │  DEPT AGENTS   │  │  VALIDATORS   │            │
│  │  (Chief LLM) │◄─────►│  (Worker LLMs) │◄►│  (Critic LLMs)│            │
│  └───────┬──────┘       └────────┬───────┘  └───────────────┘            │
│          │                       │                                          │
│  ┌───────▼───────────────────────▼──────────────────────────────────────┐  │
│  │                        TOOL REGISTRY                                 │  │
│  │  doc_extractor · math_engine · stat_tools · nlp_tools · viz_tools   │  │
│  └───────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                          │
│  ┌───────────────────────────────▼──────────────────────────────────────┐  │
│  │               DOCUMENT PIPELINE + BM25 STORE                        │  │
│  │         chunker · fingerprinter · BM25 retriever                    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                              │
           ┌────────▼────────┐          ┌──────────▼──────────┐
           │  PostgreSQL     │          │  DeepSeek API /     │
           │  (без pgvector) │          │  LLaMA (Ollama)     │
           └─────────────────┘          └─────────────────────┘
```

---

## 3. Многоагентная система (MAS)

### 3.1 Доска объявлений (Blackboard)

Blackboard — центральное разделяемое хранилище состояния, через которое агенты взаимодействуют **без прямых вызовов друг друга**. Реализована на Redis (production) или `asyncio`-словаре (dev/test).

```
Blackboard (пространства ключей Redis / asyncio-словарь)
├── session:{id}                    # метаданные сессии (query, file_ids, status)
├── graph:{id}                      # TaskGraph (снимок плана, записывается один раз)
│   ├── tasks: dict[task_id → TaskSpec]
│   └── execution_groups: list[list[str]]   # уровни параллелизма (без edges)
├── task:{task_id}                  # TaskSpec отдельной задачи
├── task_status:{task_id}           # статус + счётчик ретраев
├── draft:{task_id}                 # черновик блока (опционально)
├── verdict:{task_id}               # CriticVerdict (опционально)
├── block:{block_id}                # одобренный блок отчёта
├── session_blocks:{id}             # список block_id текущей сессии
└── agentlog:{id}                   # структурированный лог событий агентов
```

**Ключевые свойства:**
- Двойной режим: Redis (production) / `asyncio`-словарь + in-process pub/sub (dev/test); переключение автоматическое при старте
- TTL на каждый ключ (по умолчанию 24 ч для блоков, `task_timeout * 10` для задач)
- Pub/sub через `broker.publish / broker.subscribe` — события транслируются как SSE фронтенду
- Оркестратор не подписывается на события Blackboard — он управляет выполнением через прямые вызовы и `asyncio.gather`

---

### 3.2 Оркестратор (Chief Agent)

**Единственная роль:** планирование и маршрутизация. Оркестратор **никогда не выполняет** аналитику сам.

**Алгоритм работы (`ChiefAgent.run`):**

1. Загрузить метаданные файлов из PostgreSQL (имена, типы, размеры, структуру — но **не содержимое**).
2. Вызвать `_plan(query, file_metas)` — сформировать системный и пользовательский промпт, отправить LLM, получить `OrchestratorPlan` через structured output (`instructor`).
3. Конвертировать план в `TaskGraph` и записать на Blackboard (однократно, как снимок состояния).
4. Последовательно выполнить группы `execution_order`: каждая группа — `asyncio.gather` параллельных задач.
5. После всех групп вызвать `AssemblyWorker` для финальной компиляции отчёта.
6. Сохранить блоки в PostgreSQL и пометить сессию как завершённую.

**Планирование через structured LLM output (декомпозиция без отдельного инструмента):**

```python
class OrchestratorPlan(BaseModel):
    reasoning: str                    # краткое обоснование плана (≤500 токенов)
    tasks: list[TaskSpec]             # атомарные задачи
    execution_order: list[list[str]]  # группы параллельных задач (топологические уровни)
    estimated_total_tokens: int = 0

class TaskSpec(BaseModel):
    task_id: str
    session_id: str
    department: DepartmentEnum
    description: str                  # ≤500 символов
    required_inputs: list[str] = []   # file_ids или task_ids
    depends_on_tasks: list[str] = []  # метаданные зависимостей (не валидируются runtime)
    expected_output_type: str = "text"
    priority: int = 5
    max_retries: int = 2
    timeout_seconds: int = 120
    max_tokens: int = 8000
    escalation_policy: EscalationPolicy = EscalationPolicy()
    context_hints: dict[str, Any] = {}
```

> **Важно:** зависимости между задачами задаются **порядком групп** в `execution_order`, а не рёбрами графа. Поле `depends_on_tasks` в `TaskSpec` — информационное; runtime не проверяет его при запуске задачи. `TaskGraph` записывается на Blackboard один раз при старте сессии и далее не обновляется.

**Стратегия токен-экономии оркестратора:**  
Оркестратор работает только с метаданными документов (не с полным содержимым), а его системный промпт содержит только описания типов задач и отделов — без примеров данных.

---

### 3.3 Отделы: исполнители и валидаторы

Каждый отдел состоит из:
- **Worker Agent** — выполняет задачу, вызывает инструменты, формирует блок
- **Critic Agent** — проверяет результат по чеклисту, возвращает `CriticVerdict`

```
┌──────────────────────────────────────────────────┐
│                    ОТДЕЛ                         │
│                                                  │
│  ┌──────────────┐    задача    ┌───────────────┐ │
│  │    Worker    │◄────────────│  Blackboard   │ │
│  │   (LLM +     │             │               │ │
│  │    Tools)    │─────────────►  result_draft │ │
│  └──────────────┘             └───────┬───────┘ │
│                                       │         │
│  ┌──────────────┐    verdict   ┌──────▼───────┐ │
│  │    Critic    │◄─────────────│ result_draft │ │
│  │   (LLM)      │             └──────────────┘ │
│  └──────┬───────┘                              │
│         │ APPROVED / REJECT(reason)            │
│  ┌──────▼───────────────────────────────────┐  │
│  │         Loop Guard (max_retries)         │  │
│  └──────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

**Отделы системы:**

| ID | Отдел | Worker | Critic | Инструменты |
|---|---|---|---|---|
| `DATA_EXTRACTION` | Извлечение данных | DataWorker | DataCritic | pdf_extract, excel_extract, table_detect, chunk_search, fingerprint_verify |
| `QUANT_ANALYSIS` | Количественный анализ | QuantWorker | QuantCritic | stats_calc, trend_analysis, correlation, forecasting, aggregation, outlier_detect |
| `QUAL_ANALYSIS` | Качественный анализ | QualWorker | QualCritic | text_summarize, sentiment, entity_extract, keyword_extract, text_compare |
| `VISUALIZATION` | Визуализация | VizWorker | VizCritic | chart_spec, table_format, heatmap_spec, geo_spec |
| `REPORT_ASSEMBLY` | Сборка отчёта | AssemblyWorker | AssemblyCritic | block_order, toc_generate, exec_summary |

**`CriticVerdict` — структура ответа валидатора:**

```python
class CriticVerdict(BaseModel):
    task_id: str
    status: Literal["APPROVED", "REJECT"]
    score: float                    # 0.0 – 1.0
    issues: list[CriticIssue]       # только при REJECT
    approved_block: ReportBlock | None  # только при APPROVED

class CriticIssue(BaseModel):
    severity: Literal["CRITICAL", "MAJOR", "MINOR"]
    category: Literal["DATA_ACCURACY", "MATH_ERROR", "MISSING_INFO", "FORMAT_VIOLATION", "LOGIC_ERROR"]
    description: str                # до 100 токенов
    suggested_fix: str              # до 100 токенов
```

**Промпт критика намеренно минималистичен** — только чеклист проверки (без лишнего контекста), что снижает потребление токенов.

---

### 3.4 Протокол взаимодействия агентов

Оркестратор является **централизованным диспетчером**: Worker и Critic одного отдела вызываются им **синхронно и напрямую** внутри метода `_execute_task()`. Blackboard при этом используется для публикации событий (через pub/sub) и ведения лога — но не как управляющий канал между агентами.

```
Оркестратор → asyncio.gather(группа задач)
  └── _execute_task(task)
        ├── Blackboard.update_task_status → pub/sub: TASK_ASSIGNED
        ├── retriever.search() → релевантные чанки из БД
        ├── Worker.run(task, chunks) → list[dict блоков]
        ├── Critic.review(task_id, blocks) → CriticVerdict
        ├── если APPROVED:
        │     Blackboard.write_approved_block() → pub/sub: BLOCK_APPROVED (→ SSE фронтенду)
        └── если REJECT и попытки не исчерпаны → повтор Worker → Critic
              иначе → блоки публикуются со статусом "partial"
```

**Прямых peer-to-peer вызовов между агентами нет.** Worker не подписывается на Blackboard и не «слышит» события — оркестратор вызывает его явно. Blackboard публикует события для двух потребителей: фронтенда (через SSE) и отладочного лога сессии.

**Модель сообщения** (используется для SSE и внутреннего аудита, но не как транспорт между Worker и Critic):

```python
class BlackboardMessage(BaseModel):
    msg_id: str
    from_agent: str
    to_agent: str | None        # None = broadcast
    session_id: str
    task_id: str
    msg_type: BlackboardEventType   # TASK_ASSIGNED | DRAFT_READY | VERDICT | ESCALATION | BLOCK_APPROVED | SESSION_DONE
    payload_ref: str            # ключ в Redis / id объекта (ссылка, не сам объект)
    payload: dict[str, Any] = {}   # лёгкий payload для фронтенда
    timestamp: datetime
    ttl_seconds: int = 3600
```

---

### 3.5 Механизм предотвращения бесконечных циклов

**Схемы защиты** (определены в `schemas/tasks.py`):

```python
class LoopGuard(BaseModel):
    task_id: str
    max_retries: int = 2          # Critic может вернуть задачу не более N раз
    current_retries: int = 0
    max_total_tokens: int = 8000  # информационный лимит токенов на задачу
    tokens_used: int = 0
    timeout_seconds: int = 120    # информационный дедлайн
    started_at: datetime
    escalation_policy: EscalationPolicy
    draft_scores: list[float] = []   # оценки черновиков для use_best_draft
    draft_ids: list[str] = []

class EscalationPolicy(BaseModel):
    on_retry_exhausted: Literal["use_best_draft", "skip_block", "fail_task"] = "use_best_draft"
    on_timeout: Literal["use_best_draft", "skip_block", "fail_task"] = "use_best_draft"
    on_token_limit: Literal["use_best_draft", "truncate_and_finalize"] = "use_best_draft"
    notify_orchestrator: bool = True
```

**Фактический алгоритм (реализован в `_execute_task`):**

1. Счётчик попыток управляется через `settings.max_task_retries` и переменную `attempt` цикла `for attempt in range(max_retries + 1)`.
2. При каждом `REJECT` от Critic — `Blackboard.increment_retry(task_id)` и переход к следующей итерации.
3. После исчерпания попыток последние полученные блоки публикуются на Blackboard со статусом `"partial"` и флагом предупреждения — это реализация стратегии `use_best_draft`.
4. Задача получает статус `"escalated"` в Blackboard; оркестратор **не перестраивает план** — он продолжает выполнение оставшихся групп.

> **Примечание:** поля `tokens_used`, `draft_scores` и `draft_ids` в `LoopGuard` определены в схеме, но оркестратором активно не заполняются — управление повторами основано на счётчике попыток.

**Статусы задачи в жизненном цикле:**

```
PENDING → RUNNING → (APPROVED | ESCALATED | FAILED)
```

При `REJECT` статус не меняется — задача остаётся в `RUNNING` до следующего вердикта или эскалации.

---

## 4. Конвейер обработки документов

### 4.1 Загрузка и чанкинг

```
Файл пользователя
       │
       ▼
┌──────────────────┐
│  Format Detector │  PDF, XLSX, CSV, DOCX, TXT, JSON
└──────┬───────────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│                  EXTRACTION LAYER                    │
│  PDF → PyMuPDF + pdfplumber (таблицы, текст, OCR)   │
│  XLSX → openpyxl + pandas                           │
│  CSV → pandas + chardet (кодировка)                 │
│  DOCX → python-docx                                 │
│  JSON → pydantic validation + flatten               │
└──────┬───────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│                  CHUNKING STRATEGY                   │
│                                                      │
│  Текст: RecursiveCharacterTextSplitter               │
│    chunk_size=512 tokens, overlap=64 tokens          │
│    границы по предложениям, не по словам             │
│                                                      │
│  Таблицы: TableChunker                               │
│    каждая таблица → отдельный чанк                   │
│    строки > 50 → разбивка с сохранением заголовков   │
│                                                      │
│  Числовые ряды: NumericSeriesChunker                 │
│    временные ряды → сегменты по 100 точек            │
│    сохранение контекста (названия колонок, единицы)  │
└──────┬───────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│                  METADATA ENRICHMENT                 │
│  chunk_id, file_id, page/row, section_header,        │
│  chunk_type (text/table/numeric), language,          │
│  numeric_density (доля числовых токенов)             │
└──────────────────────────────────────────────────────┘
```

### 4.2 Цифровой слепок данных (Data Fingerprint)

Ключевой механизм верификации — предотвращает извлечение LLM-ом «придуманных» чисел.

```python
class NumericFingerprint(BaseModel):
    """Создаётся при загрузке, НЕИЗМЕНЯЕМ в течение сессии."""
    file_id: str
    numeric_catalog: dict[str, NumericEntry]
    # ключ: нормализованный контекст ("выручка Q1 2023")

class NumericEntry(BaseModel):
    value: float
    unit: str | None
    source_chunk_id: str
    source_location: str          # "стр. 12, строка 4, колонка 'Revenue'"
    value_hash: str               # SHA-256(str(value) + source_location)
    extraction_confidence: float  # 0.0–1.0

class FingerprintVerifier:
    """Инструмент для Workers: проверяет число перед включением в блок."""
    def verify(self, claimed_value: float, context_hint: str) -> VerificationResult:
        # 1. Нормализация контекста
        # 2. Нечёткий поиск по catalog (rapidfuzz)
        # 3. Сравнение значений с допуском ±0.001 (float погрешности)
        # 4. Возврат: VERIFIED / MISMATCH / NOT_FOUND
        ...
```

**Принцип работы:**
- При загрузке файла все числа извлекаются инструментом (не LLM) и записываются в `NumericFingerprint`
- Когда Worker хочет включить число в блок, он **обязан** вызвать `verify_number(value, context)` как инструмент
- Если `NOT_FOUND` или `MISMATCH` → число не вставляется, Worker помечает его как `[UNVERIFIED]`
- Critic проверяет отсутствие `[UNVERIFIED]` чисел в результате

### 4.3 BM25-поиск по чанкам

Векторные эмбеддинги (sentence-transformers) убраны из пайплайна — они требовали загрузки тяжёлой локальной модели и существенно замедляли обработку файлов. Вместо них используется **BM25-only** поиск, который работает мгновенно и не требует GPU или дополнительных зависимостей.

```
Чанк → сохранение текста в PostgreSQL (без векторного поля)

При запросе Worker'а:
  bm25_index = BM25Okapi(all_chunks_for_file_ids)
  chunks = bm25_index.get_top_k(tokenize(query), top_k=8)
  → передаётся Worker'у как контекст (не весь файл!)
```

**Токенизатор:** регулярный (поддерживает кириллицу + латиницу):
```python
re.findall(r"[а-яёА-ЯЁa-zA-Z0-9]+", text.lower())
```

**Компромисс:** BM25 уступает семантическому поиску при парафразах и синонимах, однако для аналитических документов (с числами, терминами, заголовками разделов) даёт сопоставимое качество при значительно меньшей латентности.

> **Поле `embedding` в таблице `document_chunks`** оставлено в схеме БД (nullable), чтобы при необходимости можно было вернуть векторный поиск без миграции.

---

## 5. Инструментарий агентов (Tools)

Все инструменты — детерминированные Python-функции, обёрнутые в `@tool` декоратор. LLM **никогда** не выполняет математику самостоятельно.

### 5.1 Отдел извлечения данных

```python
# Инструменты DataWorker

@tool
def search_chunks(query: str, file_ids: list[str], top_k: int = 8) -> list[ChunkResult]:
    """Семантический + ключевое слово поиск по чанкам."""

@tool
def extract_table(file_id: str, table_hint: str) -> TableData:
    """Извлечь таблицу из документа по описанию. Возвращает структурированные данные."""

@tool
def verify_number(value: float, context_hint: str, file_id: str) -> VerificationResult:
    """Верифицировать число через NumericFingerprint."""

@tool
def get_document_structure(file_id: str) -> DocumentStructure:
    """Список разделов, заголовков, страниц, типов контента."""

@tool
def extract_named_entities(chunk_ids: list[str]) -> list[Entity]:
    """NER: организации, даты, денежные суммы, показатели."""

@tool
def find_numeric_context(search_term: str, file_id: str) -> list[NumericContext]:
    """Найти все числа, связанные с термином (выручка, прибыль и т.д.)."""
```

### 5.2 Отдел количественного анализа

```python
# Инструменты QuantWorker
# LLM ОПРЕДЕЛЯЕТ ЧТО делать, инструменты ДЕЛАЮТ

@tool
def calculate_statistics(data: list[float], metrics: list[StatMetric]) -> StatResult:
    """Описательная статистика: mean, median, std, percentiles, min, max."""

@tool
def calculate_growth_rate(values: list[float], periods: list[str]) -> GrowthResult:
    """CAGR, YoY, MoM, QoQ темпы роста."""

@tool
def calculate_correlation(series_a: list[float], series_b: list[float]) -> CorrelationResult:
    """Pearson, Spearman, Kendall корреляция с p-value."""

@tool
def run_trend_analysis(time_series: list[TimePoint]) -> TrendResult:
    """Линейный тренд, полиномиальная аппроксимация, сезонность (STL)."""

@tool
def forecast_series(time_series: list[TimePoint], horizon: int, method: ForecastMethod) -> ForecastResult:
    """ARIMA, ETS, Simple Exponential Smoothing прогноз."""

@tool
def detect_outliers(data: list[float], method: OutlierMethod) -> OutlierResult:
    """IQR, Z-score, Isolation Forest выбросы."""

@tool
def calculate_financial_metrics(data: FinancialData) -> FinancialMetrics:
    """ROI, ROE, EBITDA margin, P/E, DCF и прочие финансовые метрики."""

@tool
def run_cohort_analysis(events: list[Event], cohort_by: str) -> CohortResult:
    """Когортный анализ удержания/конверсии."""

@tool
def calculate_market_share(segments: dict[str, float]) -> MarketShareResult:
    """Доли рынка, HHI (индекс концентрации)."""

@tool
def run_regression(X: list[list[float]], y: list[float], model_type: RegressionType) -> RegressionResult:
    """Линейная, логистическая, полиномиальная регрессия. Коэффициенты + R²."""
```

### 5.3 Отдел качественного анализа

```python
@tool
def summarize_text(text: str, max_sentences: int = 5, style: SummaryStyle) -> SummaryResult:
    """Extractive (TextRank) + abstractive (LLM с ограниченным форматом) суммаризация."""

@tool
def analyze_sentiment(texts: list[str], granularity: SentimentGranularity) -> SentimentResult:
    """VADER + transformers модель. Документ / предложение / аспект уровень."""

@tool
def extract_keywords(text: str, top_k: int) -> list[Keyword]:
    """TF-частотный анализ. С весами релевантности (без локальных ML-моделей)."""

@tool
def extract_topics(texts: list[str], n_topics: int) -> TopicModelResult:
    """LDA / NMF тематическое моделирование."""

@tool
def compare_texts(text_a: str, text_b: str) -> TextComparisonResult:
    """Семантическое сходство, различия, общие темы."""

@tool
def classify_document(text: str, categories: list[str]) -> ClassificationResult:
    """Zero-shot классификация через NLI модель."""

@tool
def extract_action_items(text: str) -> list[ActionItem]:
    """Извлечение задач, дедлайнов, ответственных лиц."""

@tool
def analyze_risk_factors(text: str) -> list[RiskFactor]:
    """Выявление рисков, угроз, негативных факторов с уровнем серьёзности."""
```

### 5.4 Отдел визуализации

```python
@tool
def generate_chart_spec(data: ChartData, chart_type: ChartType, options: ChartOptions) -> VegaLiteSpec:
    """Генерирует валидную Vega-Lite спецификацию. LLM только выбирает тип."""

@tool
def generate_table_spec(data: TableData, formatting: TableFormatting) -> TableSpec:
    """Форматированная таблица с условным форматированием, сортировкой."""

@tool
def generate_heatmap(matrix: list[list[float]], labels: HeatmapLabels) -> VegaLiteSpec:
    """Тепловая карта корреляций, когорт, матрицы."""

@tool
def suggest_chart_type(data_profile: DataProfile, analysis_goal: str) -> list[ChartSuggestion]:
    """Rule-based рекомендация типа графика по профилю данных."""

@tool
def generate_kpi_card(metric: KPIMetric) -> KPICardSpec:
    """Спецификация KPI-карточки с трендом, дельтой, цветом."""

@tool
def generate_sparkline(series: list[float], context: str) -> SparklineSpec:
    """Мини-линейный график для встраивания в текст."""
```

### 5.5 Отдел компиляции отчёта

```python
@tool
def order_blocks(blocks: list[ReportBlock], strategy: OrderingStrategy) -> list[ReportBlock]:
    """Логически упорядочивает блоки: сводка → данные → анализ → выводы."""

@tool
def generate_table_of_contents(blocks: list[ReportBlock]) -> TOCBlock:
    """Генерирует оглавление на основе заголовков блоков."""

@tool
def generate_executive_summary(blocks: list[ReportBlock], max_words: int = 200) -> SummaryBlock:
    """Extractive executive summary из всех блоков."""

@tool
def check_report_completeness(blocks: list[ReportBlock], original_query: str) -> CompletenessReport:
    """Проверяет, что все вопросы из запроса покрыты блоками."""

@tool
def apply_report_template(blocks: list[ReportBlock], template: ReportTemplate) -> ReportSchema:
    """Применяет шаблон (финансовый, маркетинговый, операционный и т.д.)."""
```

---

## 6. Pydantic-схемы блоков вывода

Каждый блок — финальный, неизменяемый, полностью типизированный объект. React-компонент рендерит его по `block_type`.

```python
from pydantic import BaseModel, Field
from typing import Literal, Annotated, Union
from enum import Enum

# ─── Базовый блок ────────────────────────────────────────────────────────────

class BlockStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"       # блок создан, но с флагами (unverified data)
    ERROR = "error"

class ReportBlockBase(BaseModel):
    block_id: str
    block_type: str
    title: str
    order: int
    status: BlockStatus = BlockStatus.COMPLETE
    warnings: list[str] = []
    source_task_ids: list[str]
    created_by_dept: str
    created_at: datetime

# ─── Текстовый блок ──────────────────────────────────────────────────────────

class TextBlock(ReportBlockBase):
    block_type: Literal["text"] = "text"
    content: str
    style: Literal["body", "heading", "callout", "quote"] = "body"
    language: str = "ru"

# ─── KPI-карточка ────────────────────────────────────────────────────────────

class KPICard(ReportBlockBase):
    block_type: Literal["kpi_card"] = "kpi_card"
    metric_name: str
    value: float
    unit: str
    delta: float | None = None          # изменение к предыдущему периоду
    delta_pct: float | None = None
    trend: Literal["up", "down", "stable"] | None = None
    is_positive_trend: bool | None = None  # рост — это хорошо или плохо?
    benchmark: float | None = None
    verification_status: Literal["verified", "unverified"] = "verified"
    source_reference: str

# ─── Таблица ─────────────────────────────────────────────────────────────────

class TableColumn(BaseModel):
    key: str
    label: str
    dtype: Literal["number", "string", "date", "percent", "currency"]
    unit: str | None = None
    sortable: bool = True
    highlight_rule: dict | None = None   # e.g. {"gt": 0, "color": "green"}

class TableBlock(ReportBlockBase):
    block_type: Literal["table"] = "table"
    columns: list[TableColumn]
    rows: list[dict]
    totals_row: dict | None = None
    pagination: bool = True
    exportable: bool = True
    source_file_id: str
    source_location: str

# ─── График ──────────────────────────────────────────────────────────────────

class ChartType(str, Enum):
    BAR = "bar"; LINE = "line"; AREA = "area"; PIE = "pie"
    SCATTER = "scatter"; HEATMAP = "heatmap"; HISTOGRAM = "histogram"
    BOX = "box"; WATERFALL = "waterfall"; CANDLESTICK = "candlestick"
    TREEMAP = "treemap"; FUNNEL = "funnel"; RADAR = "radar"

class ChartBlock(ReportBlockBase):
    block_type: Literal["chart"] = "chart"
    chart_type: ChartType
    vega_lite_spec: dict       # полная Vega-Lite спецификация
    caption: str | None = None
    data_source_description: str
    interactive: bool = True

# ─── Аналитический инсайт ────────────────────────────────────────────────────

class InsightBlock(ReportBlockBase):
    block_type: Literal["insight"] = "insight"
    insight_type: Literal["finding", "anomaly", "recommendation", "risk", "opportunity"]
    severity: Literal["info", "warning", "critical"] = "info"
    headline: str
    explanation: str
    supporting_data: list[str]    # ссылки на block_id с данными
    confidence: float             # 0.0–1.0, от Critic

# ─── Сравнительный блок ──────────────────────────────────────────────────────

class ComparisonItem(BaseModel):
    label: str
    metrics: dict[str, float | str]

class ComparisonBlock(ReportBlockBase):
    block_type: Literal["comparison"] = "comparison"
    items: list[ComparisonItem]
    dimensions: list[str]
    winner: str | None = None
    analysis: str

# ─── Прогноз ─────────────────────────────────────────────────────────────────

class ForecastBlock(ReportBlockBase):
    block_type: Literal["forecast"] = "forecast"
    metric_name: str
    historical: list[TimePoint]
    forecast: list[ForecastPoint]
    method: str
    confidence_interval: float = 0.95
    model_accuracy: dict[str, float]   # MAE, RMSE, MAPE

class TimePoint(BaseModel):
    period: str
    value: float

class ForecastPoint(BaseModel):
    period: str
    value: float
    lower_bound: float
    upper_bound: float

# ─── Риск-анализ ─────────────────────────────────────────────────────────────

class RiskItem(BaseModel):
    name: str
    probability: Literal["low", "medium", "high"]
    impact: Literal["low", "medium", "high"]
    description: str
    mitigation: str | None = None

class RiskMatrixBlock(ReportBlockBase):
    block_type: Literal["risk_matrix"] = "risk_matrix"
    risks: list[RiskItem]
    overall_risk_level: Literal["low", "medium", "high", "critical"]

# ─── Executive Summary ────────────────────────────────────────────────────────

class ExecutiveSummaryBlock(ReportBlockBase):
    block_type: Literal["executive_summary"] = "executive_summary"
    key_findings: list[str]       # 3–7 пунктов
    recommendations: list[str]   # 2–5 пунктов
    overall_conclusion: str
    report_quality_score: float   # средний score от Critic'ов

# ─── Дискриминированный союз ─────────────────────────────────────────────────

ReportBlock = Annotated[
    Union[
        TextBlock, KPICard, TableBlock, ChartBlock,
        InsightBlock, ComparisonBlock, ForecastBlock,
        RiskMatrixBlock, ExecutiveSummaryBlock
    ],
    Field(discriminator="block_type")
]

# ─── Финальный отчёт ─────────────────────────────────────────────────────────

class ReportSchema(BaseModel):
    report_id: str
    title: str
    created_at: datetime
    query: str
    blocks: list[ReportBlock]
    toc: list[dict]
    metadata: ReportMetadata

class ReportMetadata(BaseModel):
    total_tokens_used: int
    processing_time_seconds: float
    departments_involved: list[str]
    files_analyzed: list[str]
    llm_provider: str
    model_name: str
    quality_score: float
    partial_blocks_count: int
```

---

## 7. Управление токенами и контекстом

### Стратегия «Минимальный достаточный контекст»

```
Каждый агент получает только то, что ему нужно:

Оркестратор:
  ✓ Метаданные документов (не содержимое)
  ✓ Описание задачи пользователя
  ✓ Сводка уже выполненных задач (не полные результаты)
  ✗ Содержимое файлов
  ✗ Промпты других агентов

Worker Отдела:
  ✓ Атомарная TaskSpec (150 токенов)
  ✓ Релевантные чанки (top-k=8, RAG)
  ✓ Описания инструментов своего отдела
  ✗ Результаты других отделов (если не указаны как depends_on)
  ✗ История всего разговора

Critic Отдела:
  ✓ Черновик блока (без контекста задачи)
  ✓ Чеклист проверки (статический, в системном промпте)
  ✓ Источники данных (ссылки на чанки, не сами чанки)
  ✗ Промпты Worker'а
```

### Технические меры экономии

| Мера | Реализация | Экономия |
|---|---|---|
| Кэширование промптов | Redis TTL=1h на системные промпты агентов | ~30% |
| Сжатый контекст задачи | TaskSpec ≤150 токенов | ~60% vs свободного описания |
| Контекстный RAG | Только top-8 релевантных чанков | ~70% vs полный документ |
| Модели по размеру задачи | gpt-small/deepseek-chat для Critic, большая для Orchestrator | ~40% стоимости |
| Структурированный вывод | `response_format=json_schema` (DeepSeek) → нет verbose JSON | ~20% |
| Параллельные задачи | Независимые задачи выполняются одновременно | ~50% времени |
| Переиспользование результатов | Результат инструмента кэшируется по хэшу аргументов | ~15% токенов |

### Модели по задачам

```python
class ModelConfig(BaseModel):
    orchestration: str = "deepseek-reasoner"   # планирование — нужен reasoning
    worker: str = "deepseek-chat"              # выполнение — баланс
    critic: str = "deepseek-chat"              # проверка — достаточно
    # эмбеддинги не используются — поиск через BM25

# LLaMA вариант (полностью локально через Ollama)
class LlamaModelConfig(BaseModel):
    orchestration: str = "llama3.3:70b"       # или qwen2.5:72b
    worker: str = "llama3.1:8b"
    critic: str = "llama3.1:8b"
    # эмбеддинги не используются — поиск через BM25
```

---

## 8. Бэкенд-архитектура (Python)

### Структура FastAPI приложения

```
backend/
├── app/
│   ├── main.py                    # FastAPI app, lifespan
│   ├── api/
│   │   ├── routes/
│   │   │   ├── sessions.py        # POST /sessions, GET /sessions/{id}
│   │   │   ├── reports.py         # GET /reports, GET /reports/{id}, GET /reports/{id}/stream
│   │   │   ├── files.py           # POST /files/upload, DELETE /files/{id}
│   │   │   └── health.py
│   │   └── deps.py                # Dependency injection
│   │
│   ├── agents/
│   │   ├── base.py                # BaseAgent абстракция
│   │   ├── orchestrator.py        # ChiefAgent
│   │   ├── departments/
│   │   │   ├── data_extraction/
│   │   │   │   ├── worker.py
│   │   │   │   └── critic.py
│   │   │   ├── quant_analysis/
│   │   │   ├── qual_analysis/
│   │   │   ├── visualization/
│   │   │   └── report_assembly/
│   │   └── loop_guard.py
│   │
│   ├── blackboard/
│   │   ├── board.py               # BlackboardManager
│   │   ├── models.py              # BlackboardMessage, TaskSpec
│   │   └── pubsub.py              # Redis pub/sub или asyncio
│   │
│   ├── tools/
│   │   ├── registry.py            # ToolRegistry + @tool декоратор
│   │   ├── data_extraction/       # pdf, excel, table, chunk_search
│   │   ├── math_engine/           # stats, trends, forecasting, finance
│   │   ├── nlp_tools/             # sentiment, keywords, ner, topics
│   │   └── viz_tools/             # vega-lite spec generators
│   │
│   ├── document_pipeline/
│   │   ├── pipeline.py            # DocumentPipeline координатор
│   │   ├── extractors/            # format-specific extractors
│   │   ├── chunker.py
│   │   ├── fingerprint.py         # NumericFingerprint
│   │   ├── embedder.py            # no-op заглушка (эмбеддинги отключены)
│   │   └── retriever.py           # BM25Retriever (rank-bm25, без векторов)
│   │
│   ├── schemas/
│   │   ├── blocks.py              # все ReportBlock Pydantic модели
│   │   ├── report.py              # ReportSchema
│   │   ├── tasks.py               # TaskSpec, CriticVerdict
│   │   └── api.py                 # Request/Response модели API
│   │
│   ├── llm/
│   │   ├── provider.py            # LLMProvider абстракция
│   │   ├── deepseek.py            # DeepSeek adapter
│   │   ├── ollama.py              # LLaMA через Ollama adapter
│   │   └── structured.py         # instructor-based structured output
│   │
│   ├── storage/
│   │   ├── postgres.py            # SQLAlchemy async
│   │   ├── vector_store.py        # pgvector
│   │   └── file_store.py          # S3 / local filesystem
│   │
│   └── core/
│       ├── config.py              # Pydantic Settings
│       ├── logging.py             # структурированные логи
│       └── telemetry.py           # OpenTelemetry трассировка
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── alembic/                       # миграции БД
├── pyproject.toml
└── docker-compose.yml
```

### Ключевые технические решения

**1. Structured Output через `instructor`:**
```python
import instructor
from openai import AsyncOpenAI

client = instructor.from_openai(
    AsyncOpenAI(base_url="https://api.deepseek.com/v1", api_key=...),
    mode=instructor.Mode.JSON
)

result = await client.chat.completions.create(
    model="deepseek-chat",
    response_model=OrchestratorPlan,   # Pydantic модель
    messages=[...],
    max_retries=2                      # автоматические retry при ошибке валидации
)
```

**2. Streaming SSE для фронтенда:**
```python
@router.get("/reports/{session_id}/stream")
async def stream_report(session_id: str):
    async def event_generator():
        async for event in blackboard.subscribe(session_id):
            if event.type == "block_approved":
                block = await get_block(event.block_id)
                yield f"data: {block.model_dump_json()}\n\n"
            elif event.type == "task_status":
                yield f"data: {event.model_dump_json()}\n\n"
    return EventSourceResponse(event_generator())
```

**3. Параллельное выполнение задач:**
```python
async def execute_parallel_group(tasks: list[TaskSpec]):
    async with asyncio.TaskGroup() as tg:
        for task in tasks:
            tg.create_task(dispatch_to_department(task))
```

---

## 9. Фронтенд-архитектура (React/TS/Vite/Shadcn)

### Структура

```
frontend/
├── src/
│   ├── app/
│   │   ├── App.tsx               # BrowserRouter + Routes
│   │   └── store.ts              # Zustand глобальный стор
│   │
│   ├── pages/
│   │   ├── Home.tsx              # "/" — загрузка файлов + генерация отчёта
│   │   ├── ReportsList.tsx       # "/reports" — список всех готовых отчётов
│   │   └── ReportViewer.tsx      # "/reports/:sessionId" — просмотр отчёта
│   │
│   ├── features/
│   │   ├── report-builder/
│   │   │   ├── ReportCanvas.tsx  # контейнер блоков (с BlockErrorBoundary)
│   │   │   └── BlockRenderer.tsx # диспетчер блоков по типу
│   │   │
│   │   ├── file-upload/
│   │   │   └── FileUploadZone.tsx
│   │   │
│   │   ├── query-input/
│   │   │   └── QueryForm.tsx
│   │   │
│   │   └── agent-monitor/
│   │       └── AgentMonitor.tsx
│   │
│   ├── components/
│   │   ├── BlockErrorBoundary.tsx  # React Error Boundary — защита от краша блока
│   │   ├── blocks/               # React-компоненты для каждого BlockType
│   │   │   ├── TextBlock.tsx
│   │   │   ├── KPICard.tsx
│   │   │   ├── TableBlock.tsx
│   │   │   ├── ChartBlock.tsx    # Vega-Lite через vega-embed
│   │   │   ├── InsightBlock.tsx
│   │   │   ├── ComparisonBlock.tsx
│   │   │   ├── ForecastBlock.tsx
│   │   │   ├── RiskMatrix.tsx
│   │   │   └── ExecutiveSummary.tsx
│   │   │
│   │   └── ui/                   # Radix UI / Shadcn компоненты
│   │
│   ├── hooks/
│   │   └── useReportStream.ts    # SSE подписка на блоки
│   │
│   ├── lib/
│   │   ├── api.ts                # fetch-клиент + типы ответов
│   │   └── utils.ts
│   │
│   └── types/
│       └── blocks.ts             # зеркало Pydantic схем на TypeScript
│
├── vite.config.ts
├── tailwind.config.ts
└── package.json
```

### BlockRenderer и защита от сбоев

Каждый блок оборачивается в `BlockErrorBoundary` — React Error Boundary класс-компонент. Если конкретный блок падает при рендере (например, невалидная Vega-Lite спецификация), страница **не становится белой**: вместо блока показывается сообщение об ошибке, остальные блоки продолжают работать.

```tsx
// ReportCanvas.tsx — каждый блок изолирован
{blocks.map(block => (
  <BlockErrorBoundary key={block.block_id}>
    <BlockRenderer block={block} />
  </BlockErrorBoundary>
))}
```

```tsx
// BlockRenderer — диспетчер по block_type
const BlockRenderer: React.FC<{ block: ReportBlock }> = ({ block }) => {
  switch (block.block_type) {
    case 'text':              return <TextBlockComponent {...block} />
    case 'kpi_card':          return <KPICardComponent {...block} />
    case 'table':             return <TableBlockComponent {...block} />
    case 'chart':             return <ChartBlockComponent {...block} />
    case 'insight':           return <InsightBlockComponent {...block} />
    case 'comparison':        return <ComparisonBlockComponent {...block} />
    case 'forecast':          return <ForecastBlockComponent {...block} />
    case 'risk_matrix':       return <RiskMatrixBlockComponent {...block} />
    case 'executive_summary': return <ExecutiveSummaryComponent {...block} />
    default: return <div>Неизвестный тип: {block.block_type}</div>
  }
};
```

### Роутинг (react-router-dom v6)

```tsx
// App.tsx
<BrowserRouter>
  <Routes>
    <Route path="/"                   element={<Home />} />
    <Route path="/reports"            element={<ReportsList />} />
    <Route path="/reports/:sessionId" element={<ReportViewer />} />
  </Routes>
</BrowserRouter>
```

| Маршрут | Компонент | Описание |
|---|---|---|
| `/` | `Home` | Загрузка файлов, ввод запроса, генерация отчёта в реальном времени |
| `/reports` | `ReportsList` | Список всех завершённых отчётов (авторизация не требуется) |
| `/reports/:id` | `ReportViewer` | Просмотр конкретного отчёта по session ID |

Nginx настроен с `try_files $uri $uri/ /index.html` — SPA-роутинг работает при прямом переходе по URL.

### Streaming блоков в реальном времени

```tsx
// useReportStream.ts — SSE подписка через Zustand store
export function useReportStream(sessionId: string | null) {
  const { addBlock, upsertTask, setGenerating } = useStore()

  useEffect(() => {
    if (!sessionId) return
    setGenerating(true)
    const es = new EventSource(`/api/reports/${sessionId}/stream`)

    es.onmessage = (e) => {
      const event = JSON.parse(e.data)
      if (event.type === 'block_approved') addBlock(event)
      else if (event.type === 'task_status') upsertTask(event)
      else if (event.type === 'session_done') { setGenerating(false); es.close() }
    }

    es.onerror = () => { setGenerating(false); es.close() }
    return () => { es.close(); setGenerating(false) }
  }, [sessionId])
}
```

---

## 10. LLM-провайдеры: DeepSeek / LLaMA

```python
class LLMProvider(ABC):
    @abstractmethod
    async def complete_structured(
        self,
        messages: list[Message],
        response_model: type[BaseModel],
        model: str,
        max_tokens: int,
        temperature: float = 0.1
    ) -> BaseModel: ...

    @abstractmethod
    async def complete_streaming(self, ...) -> AsyncIterator[str]: ...


class DeepSeekProvider(LLMProvider):
    """DeepSeek API (OpenAI-совместимый)."""
    # Использует deepseek-chat для worker/critic
    # deepseek-reasoner для orchestrator (встроенный CoT)
    # Поддерживает json_schema mode для structured output


class OllamaProvider(LLMProvider):
    """Локальный LLaMA через Ollama REST API."""
    # Использует llama3.3:70b или qwen2.5:72b для orchestrator
    # llama3.1:8b для worker/critic
    # Structured output через llama.cpp grammar-based sampling
    # Полностью офлайн, GDPR-compliant
```

**Выбор провайдера через конфигурацию (без смены кода):**
```yaml
# config.yaml
llm:
  provider: "deepseek"   # или "ollama"
  models:
    orchestration: "deepseek-reasoner"
    worker: "deepseek-chat"
    critic: "deepseek-chat"
  temperature: 0.1
  max_retries: 2
```

---

## 11. Схема базы данных

```sql
-- Сессии пользователей
CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    user_id UUID,
    query TEXT NOT NULL,
    status VARCHAR(20),      -- pending, running, complete, failed
    created_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    total_tokens INT,
    llm_provider VARCHAR(50)
);

-- Загруженные файлы
CREATE TABLE uploaded_files (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    filename TEXT,
    file_type VARCHAR(20),
    size_bytes INT,
    storage_path TEXT,
    processing_status VARCHAR(20),
    fingerprint_json JSONB      -- NumericFingerprint
);

-- Чанки документов (BM25-only поиск, pgvector не используется)
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY,
    file_id UUID REFERENCES uploaded_files(id),
    chunk_index INT,
    chunk_type VARCHAR(20),     -- text, table, numeric
    content TEXT,
    metadata JSONB,
    embedding vector(1024),     -- nullable, зарезервировано (не заполняется)
    numeric_density FLOAT
);
-- Индекс ivfflat не создаётся (векторный поиск не используется)

-- Граф задач
CREATE TABLE tasks (
    id VARCHAR(50) PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    department VARCHAR(50),
    status VARCHAR(20),
    spec_json JSONB,
    result_block_id VARCHAR(50),
    retries INT DEFAULT 0,
    tokens_used INT,
    created_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Блоки отчёта
CREATE TABLE report_blocks (
    id VARCHAR(50) PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    block_type VARCHAR(50),
    block_json JSONB NOT NULL,   -- полная Pydantic-сериализация
    "order" INT,
    status VARCHAR(20),
    quality_score FLOAT,
    created_at TIMESTAMPTZ
);

-- Audit log агентов
CREATE TABLE agent_audit (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    agent_name VARCHAR(100),
    action VARCHAR(50),
    task_id VARCHAR(50),
    tokens_in INT,
    tokens_out INT,
    latency_ms INT,
    created_at TIMESTAMPTZ
);
```

---

## 12. Безопасность и ограничения

- **Изоляция инструментов:** каждый инструмент выполняется в ограниченном контексте; нет доступа к файловой системе за пределами директории загрузок
- **Валидация входных данных:** все API-параметры проходят Pydantic-валидацию
- **Лимиты на задачу:** max_tokens, timeout, max_retries — жёсткие ограничения
- **Очистка файлов:** загруженные файлы удаляются через 24 часа
- **API-ключи:** только в env переменных, не в коде и не в БД

---

## 13. Структура проекта

```
MAS-Analytics/
├── backend/
│   ├── app/               (см. раздел 8)
│   ├── tests/
│   ├── alembic/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/               (см. раздел 9)
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── architecture.md
```

---

## 14. Зависимости и технологический стек

### Backend (Python ≥ 3.11)

```toml
[project]
dependencies = [
    # Web framework
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sse-starlette>=2.1",

    # LLM & structured output
    "instructor>=1.4",
    "openai>=1.40",           # DeepSeek API совместим
    "ollama>=0.3",            # LLaMA через Ollama

    # Pydantic
    "pydantic>=2.8",
    "pydantic-settings>=2.4",

    # Document processing
    "pymupdf>=1.24",          # PDF
    "pdfplumber>=0.11",       # PDF таблицы
    "python-docx>=1.1",       # DOCX
    "openpyxl>=3.1",          # XLSX
    "chardet>=5.2",           # кодировка CSV

    # Math & analytics
    "pandas>=2.2",
    "numpy>=2.0",
    "scipy>=1.13",
    "statsmodels>=0.14",      # ARIMA, STL
    "scikit-learn>=1.5",      # ML, anomaly detection
    "rapidfuzz>=3.9",         # нечёткий поиск для fingerprint

    # NLP (лёгкий набор — без локальных ML-моделей)
    "vaderSentiment>=3.3",         # sentiment analysis
    "nltk>=3.8",                   # токенизация, stopwords

    # Хранилище и поиск (BM25-only, pgvector не используется активно)
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "pgvector>=0.3",               # расширение установлено, но не используется для поиска
    "rank-bm25>=0.2",              # основной механизм retrieval

    # Caching & messaging
    "redis[asyncio]>=5.0",

    # Observability
    "opentelemetry-sdk>=1.25",
    "structlog>=24.2",
]
```

### Frontend

```json
{
  "dependencies": {
    "react": "^18",
    "react-dom": "^18",
    "react-router-dom": "^6",        // клиентский роутинг (/, /reports, /reports/:id)
    "typescript": "^5",
    "vite": "^5",
    "@tanstack/react-query": "^5",   // серверное состояние
    "vega-lite": "^5",               // графики
    "vega-embed": "^6",              // рендер Vega-Lite спецификаций
    "zustand": "^4",                 // глобальный стор
    "@radix-ui/react-*": "latest",   // UI-примитивы
    "tailwindcss": "^3",
    "class-variance-authority": "latest",
    "lucide-react": "latest"
  }
}
```

---

## 15. Docker-инфраструктура

Всё приложение упаковано в Docker и управляется через `docker-compose`. Разработка, тестирование и деплой выполняются **одной командой** без необходимости устанавливать Python, Node или PostgreSQL локально.

### Сервисы

| Сервис | Образ | Порт | Описание |
|---|---|---|---|
| `backend` | `./backend/Dockerfile` | 8000 | FastAPI приложение |
| `frontend` | `./frontend/Dockerfile` | 5173 (dev) / 80 (prod) | React + Vite |
| `postgres` | `pgvector/pgvector:pg16` | 5432 | PostgreSQL с расширением pgvector |
| `redis` | `redis:7-alpine` | 6379 | Blackboard pub/sub + кэш |
| `ollama` | `ollama/ollama` | 11434 | LLaMA-модели (опционально, только если `provider=ollama`; embedding-модели не загружаются) |
| `nginx` | `nginx:alpine` | 80/443 | Reverse proxy (только prod) |

### `docker-compose.yml`

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: ${BUILD_TARGET:-development}
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://mas:mas@postgres:5432/mas_analytics
      - REDIS_URL=redis://redis:6379/0
      - OLLAMA_BASE_URL=http://ollama:11434
      - LLM_PROVIDER=${LLM_PROVIDER:-deepseek}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - SECRET_KEY=${SECRET_KEY}
      - UPLOAD_DIR=/app/uploads
    volumes:
      - ./backend:/app            # hot-reload в dev
      - uploads_data:/app/uploads
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      target: ${BUILD_TARGET:-development}
    ports:
      - "5173:5173"
    environment:
      - VITE_API_BASE_URL=http://localhost:8000
    volumes:
      - ./frontend:/app           # hot-reload в dev
      - /app/node_modules
    depends_on:
      - backend

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: mas
      POSTGRES_PASSWORD: mas
      POSTGRES_DB: mas_analytics
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/alembic/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mas -d mas_analytics"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  ollama:
    image: ollama/ollama
    profiles: ["ollama"]          # запускается только при: --profile ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

volumes:
  postgres_data:
  redis_data:
  uploads_data:
  ollama_models:
```

### Многоэтапная сборка (`backend/Dockerfile`)

```dockerfile
# ── Этап 1: зависимости ──────────────────────────────────────────────────────
FROM python:3.11-slim AS dependencies
WORKDIR /app
RUN apt-get update && apt-get install -y \
    build-essential libpq-dev poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir uv && uv pip install --system -e ".[all]"

# ── Этап 2: разработка (с hot-reload) ────────────────────────────────────────
FROM dependencies AS development
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Этап 3: продакшн (оптимизированный) ──────────────────────────────────────
FROM dependencies AS production
COPY . .
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4", "--no-access-log"]
```

### Многоэтапная сборка (`frontend/Dockerfile`)

```dockerfile
# ── Этап 1: зависимости ──────────────────────────────────────────────────────
FROM node:20-alpine AS dependencies
WORKDIR /app
COPY package.json pnpm-lock.yaml .
RUN npm i -g pnpm && pnpm install --frozen-lockfile

# ── Этап 2: разработка ───────────────────────────────────────────────────────
FROM dependencies AS development
COPY . .
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

# ── Этап 3: сборка для продакшна ─────────────────────────────────────────────
FROM dependencies AS builder
COPY . .
RUN pnpm build

# ── Этап 4: продакшн (nginx) ─────────────────────────────────────────────────
FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### Команды для работы

```bash
# Первый запуск / разработка (DeepSeek)
cp .env.example .env        # заполнить DEEPSEEK_API_KEY
docker compose up --build

# Разработка с LLaMA (локально)
docker compose --profile ollama up --build
# Затем загрузить модель:
docker exec -it mas-analytics-ollama-1 ollama pull llama3.1:8b

# Применить миграции БД
docker compose exec backend alembic upgrade head

# Продакшн-сборка
BUILD_TARGET=production docker compose up --build -d

# Запустить тесты внутри контейнера
docker compose exec backend pytest tests/ -v
```

### `.env.example`

```dotenv
# LLM провайдер: "deepseek" или "ollama"
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...

# Безопасность
SECRET_KEY=change-me-in-production

# Опционально: кастомные URL
DATABASE_URL=postgresql+asyncpg://mas:mas@postgres:5432/mas_analytics
REDIS_URL=redis://redis:6379/0
OLLAMA_BASE_URL=http://ollama:11434

# Лимиты
MAX_UPLOAD_SIZE_MB=50
SESSION_TTL_HOURS=24
```

---

## 16. Поэтапный план разработки для LLM-агента

> Каждый этап — атомарная, самодостаточная единица работы. Агент выполняет один этап, делает коммит, переходит к следующему. Этапы 1–3 не требуют LLM API-ключей.

---

### Этап 0 — Инициализация репозитория (15 мин)

**Цель:** создать минимальную scaffold-структуру всего проекта.

**Задачи:**
1. Создать корневую структуру директорий согласно разделу 13
2. Создать `docker-compose.yml` (из раздела 15)
3. Создать `.env.example`
4. Создать `backend/pyproject.toml` с полным списком зависимостей (раздел 14)
5. Создать `frontend/package.json` с зависимостями (раздел 14)
6. Создать оба `Dockerfile` (backend + frontend)
7. Создать `backend/app/__init__.py`, `frontend/src/main.tsx` — пустые точки входа
8. Создать `.gitignore` для Python + Node + Docker

**Критерий готовности:** `docker compose up --build` поднимает все сервисы без ошибок (бэкенд возвращает `404`, фронт — пустую страницу).

---

### Этап 1 — Схемы и типы (30 мин)

**Цель:** определить все Pydantic-схемы до написания логики. Схемы — единственный источник истины.

**Задачи:**
1. Создать `backend/app/schemas/blocks.py` — все `ReportBlock`-классы из раздела 6 (TextBlock, KPICard, TableBlock, ChartBlock, InsightBlock, ComparisonBlock, ForecastBlock, RiskMatrixBlock, ExecutiveSummaryBlock, discriminated union `ReportBlock`)
2. Создать `backend/app/schemas/tasks.py` — `TaskSpec`, `CriticVerdict`, `CriticIssue`, `OrchestratorPlan`, `LoopGuard`, `EscalationPolicy`
3. Создать `backend/app/schemas/report.py` — `ReportSchema`, `ReportMetadata`
4. Создать `backend/app/schemas/api.py` — Request/Response модели для всех API-эндпоинтов
5. Создать `backend/app/schemas/blackboard.py` — `BlackboardMessage`, `TaskStatus`
6. Создать `backend/app/core/config.py` — `Settings` (Pydantic BaseSettings) с env-переменными
7. Сгенерировать OpenAPI JSON из схем: `python -c "import app; print(app.openapi_json)"` → `openapi.json`
8. В `frontend/src/types/blocks.ts` — написать TypeScript-типы, **зеркально** повторяющие Pydantic-схемы

**Критерий готовности:** `pytest tests/unit/test_schemas.py` — все блоки сериализуются и десериализуются без ошибок. TypeScript компилируется без ошибок.

---

### Этап 2 — База данных и миграции (30 мин)

**Цель:** поднять PostgreSQL + pgvector, создать все таблицы через Alembic.

**Задачи:**
1. Создать `backend/app/storage/postgres.py` — `AsyncSession`, `get_db` dependency
2. Создать ORM-модели SQLAlchemy (sessions, uploaded_files, document_chunks, tasks, report_blocks, agent_audit) согласно разделу 11
3. Создать `backend/alembic/` — `alembic.ini`, `env.py`, `versions/0001_initial.py`
4. Создать `backend/alembic/init.sql` — `CREATE EXTENSION IF NOT EXISTS vector;`
5. Создать `backend/app/storage/vector_store.py` — CRUD операции с pgvector: `upsert_chunks`, `search_similar`
6. Создать `backend/app/storage/file_store.py` — сохранение файлов в `/app/uploads`, удаление по TTL

**Критерий готовности:** `docker compose exec backend alembic upgrade head` выполняется без ошибок. `psql` показывает все таблицы с корректными типами, включая `vector(1024)`.

---

### Этап 3 — Конвейер обработки документов (60 мин)

**Цель:** реализовать весь пайплайн от загрузки файла до чанков в БД с отпечатками.

**Задачи:**
1. Создать `backend/app/document_pipeline/extractors/`:
   - `pdf_extractor.py` — PyMuPDF для текста + pdfplumber для таблиц
   - `excel_extractor.py` — openpyxl + pandas, сохранение формул как значений
   - `csv_extractor.py` — pandas + chardet (автодетект кодировки)
   - `docx_extractor.py` — python-docx
   - `base.py` — `BaseExtractor` абстракция, `ExtractedDocument` dataclass
2. Создать `backend/app/document_pipeline/chunker.py`:
   - `TextChunker` — `RecursiveCharacterTextSplitter` (chunk=512, overlap=64)
   - `TableChunker` — каждая таблица отдельным чанком, длинные таблицы дробятся с сохранением заголовков
   - `NumericSeriesChunker` — сегменты по 100 точек
3. Создать `backend/app/document_pipeline/fingerprint.py`:
   - `NumericExtractor` — регулярки + контекст для извлечения чисел из текста/таблиц
   - `NumericFingerprint` — построение каталога, SHA-256 хэши
   - `FingerprintVerifier.verify(value, context, file_id)` → `VerificationResult`
4. Создать `backend/app/document_pipeline/embedder.py` — `SentenceTransformerEmbedder`, батчевое вычисление, кэш
5. Создать `backend/app/document_pipeline/retriever.py` — `HybridRetriever` (BM25 + pgvector cosine, RRF слияние)
6. Создать `backend/app/document_pipeline/pipeline.py` — `DocumentPipeline.process(file_path, file_id)` оркестрирует все шаги
7. Написать тесты с реальными sample-файлами: `tests/integration/test_document_pipeline.py`

**Критерий готовности:** загрузка тестового PDF с таблицами → чанки в БД → эмбеддинги в pgvector → `retriever.search("выручка Q1")` возвращает релевантные чанки → `fingerprint.verify(1234.56, "выручка Q1")` возвращает `VERIFIED`.

---

### Этап 4 — Инструментарий агентов (90 мин)

**Цель:** реализовать все детерминированные инструменты из раздела 5. Это самый объёмный этап.

**Задачи:**
1. Создать `backend/app/tools/registry.py`:
   - `@tool` декоратор — оборачивает функцию, автоматически создаёт JSON Schema для LLM
   - `ToolRegistry` — реестр инструментов с привязкой к отделам
   - `ToolResult` — стандартизованный результат инструмента
2. Создать `backend/app/tools/data_extraction/`:
   - `search_chunks.py` — через `HybridRetriever`
   - `extract_table.py` — поиск таблицы по описанию + возврат `TableData`
   - `verify_number.py` — через `FingerprintVerifier`
   - `get_document_structure.py` — заголовки, разделы, типы контента
   - `find_numeric_context.py` — все числа рядом с термином
3. Создать `backend/app/tools/math_engine/`:
   - `statistics.py` — `calculate_statistics()` (pandas describe + custom percentiles)
   - `growth_rates.py` — `calculate_growth_rate()` (CAGR, YoY, MoM, QoQ)
   - `correlation.py` — `calculate_correlation()` (Pearson/Spearman/Kendall + p-value)
   - `trends.py` — `run_trend_analysis()` (scipy + statsmodels STL)
   - `forecasting.py` — `forecast_series()` (ARIMA, ETS — statsmodels)
   - `outliers.py` — `detect_outliers()` (IQR, Z-score, Isolation Forest)
   - `financial.py` — `calculate_financial_metrics()` (ROI, EBITDA, margin, P/E)
4. Создать `backend/app/tools/nlp_tools/`:
   - `summarize.py` — `summarize_text()` (TextRank extractive)
   - `sentiment.py` — `analyze_sentiment()` (VADER + transformers)
   - `keywords.py` — `extract_keywords()` (KeyBERT)
   - `entities.py` — `extract_named_entities()` (spaCy или transformers NER)
   - `topics.py` — `extract_topics()` (LDA через sklearn)
   - `risks.py` — `analyze_risk_factors()` (rule-based + zero-shot NLI)
5. Создать `backend/app/tools/viz_tools/`:
   - `chart_spec.py` — `generate_chart_spec()` → валидная Vega-Lite спецификация
   - `table_spec.py` — `generate_table_spec()` с форматированием
   - `suggest_chart.py` — `suggest_chart_type()` rule-based (по типу данных и цели)
   - `kpi_card.py` — `generate_kpi_card()` + `generate_sparkline()`
6. Написать unit-тесты для каждой группы инструментов с мок-данными

**Критерий готовности:** каждый инструмент вызывается напрямую с тестовыми данными и возвращает корректно типизированный результат. `ToolRegistry.get_tools_for_dept(DepartmentEnum.QUANT_ANALYSIS)` возвращает только инструменты этого отдела.

---

### Этап 5 — LLM-провайдеры и structured output (30 мин)

**Цель:** абстрагировать работу с LLM, подключить `instructor` для гарантированного Pydantic-вывода.

**Задачи:**
1. Создать `backend/app/llm/provider.py` — абстрактный `LLMProvider` с методами `complete_structured`, `complete_streaming`, `count_tokens`
2. Создать `backend/app/llm/deepseek.py` — `DeepSeekProvider`:
   - `instructor.from_openai(AsyncOpenAI(base_url=deepseek_url))`
   - поддержка `response_format=json_schema` для structured output
   - автоматические retry при ошибке валидации Pydantic (`max_retries=2`)
3. Создать `backend/app/llm/ollama.py` — `OllamaProvider`:
   - `instructor.from_openai(AsyncOpenAI(base_url=ollama_url))`
   - grammar-based sampling для гарантированного JSON
4. Создать `backend/app/llm/structured.py` — `StructuredLLM` фасад:
   - выбор провайдера по `Settings.llm_provider`
   - логирование токенов в `agent_audit`
   - rate-limiting + retry с экспоненциальным backoff
5. Написать тесты с мок-провайдером (`MockLLMProvider`)

**Критерий готовности:** `await llm.complete_structured(messages, OrchestratorPlan, model="deepseek-chat")` возвращает валидный `OrchestratorPlan`. При ошибке валидации — автоматический retry.

---

### Этап 6 — Blackboard (40 мин)

**Цель:** реализовать разделяемое хранилище состояния с pub/sub.

**Задачи:**
1. Создать `backend/app/blackboard/models.py` — все dataclass/Pydantic модели доски
2. Создать `backend/app/blackboard/board.py` — `BlackboardManager`:
   - `write_task(task_spec)` — атомарная запись TaskSpec
   - `read_task(task_id)` → `TaskSpec`
   - `write_draft(task_id, block)` — черновик блока
   - `write_verdict(task_id, verdict)` — вердикт критика
   - `write_approved_block(block)` — финальный блок
   - `get_session_state(session_id)` → сводка для Оркестратора (без полных блоков)
   - `increment_retry(task_id)` + проверка `LoopGuard`
3. Создать `backend/app/blackboard/pubsub.py`:
   - `RedisPublisher/Subscriber` (prod) + `AsyncioPublisher/Subscriber` (dev/test)
   - подписка: `subscribe(session_id, callback)`
   - публикация: `publish(session_id, event_type, payload_ref)`
4. Написать интеграционные тесты с Redis

**Критерий готовности:** Оркестратор публикует TaskSpec → Worker получает уведомление через подписку → записывает черновик → Critic получает уведомление. Всё без прямых вызовов.

---

### Этап 7 — Агенты: Worker и Critic (90 мин)

**Цель:** реализовать базовый класс агента и все агенты отделов.

**Задачи:**
1. Создать `backend/app/agents/base.py` — `BaseAgent`:
   - `run(task_spec)` — основной метод с LoopGuard
   - `_build_context(task_spec)` — собирает минимальный контекст
   - `_call_tool(tool_name, **kwargs)` — вызов инструмента через ToolRegistry
   - автоматическая запись в `agent_audit`
   - подсчёт токенов
2. Создать `backend/app/agents/departments/data_extraction/worker.py` — `DataWorker`:
   - системный промпт: роль + список инструментов отдела + формат вывода
   - логика: RAG → verify numbers → формирование блока
   - вывод строго через `instructor` с указанием `response_model`
3. Создать `backend/app/agents/departments/data_extraction/critic.py` — `DataCritic`:
   - чеклист: все числа верифицированы? нет `[UNVERIFIED]`? ссылки на источники указаны?
   - вывод: `CriticVerdict`
4. Повторить шаги 2–3 для всех отделов:
   - `quant_analysis/` — QuantWorker (все вычисления через инструменты, LLM только интерпретирует) + QuantCritic (проверка формул, единиц измерения)
   - `qual_analysis/` — QualWorker + QualCritic (проверка цитат, тональности)
   - `visualization/` — VizWorker (выбор типа графика, вызов `generate_chart_spec`) + VizCritic (валидность Vega-Lite spec)
   - `report_assembly/` — AssemblyWorker + AssemblyCritic
5. Создать `backend/app/agents/loop_guard.py` — `LoopGuardMiddleware`

**Критерий готовности:** `DataWorker.run(task_spec)` с реальными чанками из БД возвращает валидный `TableBlock` или `KPICard`. `DataCritic.run(draft)` возвращает `CriticVerdict` с `status="APPROVED"` или `"REJECT"` с конкретными `issues`.

---

### Этап 8 — Оркестратор (45 мин)

**Цель:** реализовать главного агента — планировщика и маршрутизатора.

**Задачи:**
1. Создать `backend/app/agents/orchestrator.py` — `ChiefAgent`:
   - `run(session_id, query, file_ids)` — главный метод; запускается как фоновая задача FastAPI
   - `_plan(query, file_metas)` → `OrchestratorPlan` (structured LLM output через `deepseek-reasoner` / `llama3.3:70b`); при сбое — `_default_plan()`
   - `_execute_group(session_id, task_ids, ...)` → `list[dict]` — параллельное выполнение через `asyncio.gather`
   - `_execute_task(task, file_ids, db, existing_blocks)` → `list[dict]` — цикл Worker → Critic с retry до `settings.max_task_retries`
   - `_assemble_report(session_id, query, all_blocks, ...)` → `ReportSchema` — вызов `AssemblyWorker`
   - `_persist_report(db, session_id, report)` — сохранение блоков в PostgreSQL
2. Зависимости задач задаются **порядком групп** в `execution_order` — задачи следующей группы стартуют только после завершения текущей
3. Передача контекста между группами: накопленный список `all_blocks` передаётся каждому `_execute_task` как `existing_blocks` для доступа к результатам предыдущих отделов
4. Реализовать резервный план `_default_plan()` на случай сбоя LLM при планировании

**Критерий готовности:** на тестовом сценарии (CSV-файл + запрос «проанализируй продажи») Оркестратор создаёт корректный граф из 4–6 задач, часть выполняется параллельно, итоговый `ReportSchema` содержит ≥3 разных типа блоков.

---

### Этап 9 — API и SSE-стриминг (30 мин)

**Цель:** соединить агентов с HTTP-слоем FastAPI.

**Задачи:**
1. Создать `backend/app/main.py` — FastAPI app с lifespan (подключение к Redis/Postgres при старте)
2. Создать `backend/app/api/routes/files.py`:
   - `POST /api/files/upload` — мультифайл, запуск `DocumentPipeline` в фоне
   - `GET /api/files/{id}/status` — статус обработки
   - `DELETE /api/files/{id}`
3. Создать `backend/app/api/routes/sessions.py`:
   - `POST /api/sessions` — создание сессии, запуск Оркестратора в фоне (`asyncio.create_task`)
   - `GET /api/sessions/{id}` — статус сессии + метаданные
4. Создать `backend/app/api/routes/reports.py`:
   - `GET /api/reports` — список завершённых отчётов (без авторизации)
   - `GET /api/reports/{session_id}` — полный `ReportSchema` (по завершении)
   - `GET /api/reports/{session_id}/stream` — SSE: события `block_approved`, `task_status`, `error`
5. Настроить CORS для `localhost:5173`
6. Настроить OpenAPI автодокументацию с примерами схем

**Критерий готовности:** `curl -N http://localhost:8000/api/reports/{id}/stream` выводит поток JSON-событий по мере выполнения агентов.

---

### Этап 10 — Базовый фронтенд: загрузка и запрос (45 мин)

**Цель:** создать рабочий UI для отправки запроса и загрузки файлов.

**Задачи:**
1. Инициализировать Vite + React + TypeScript проект
2. Установить и настроить Shadcn/ui (`npx shadcn@latest init`)
3. Настроить Tailwind CSS, темёмная/светлая тема
4. Создать `frontend/src/lib/api.ts` — типобезопасный клиент через `openapi-fetch` (используя `openapi.json` из этапа 1)
5. Создать страницу `Home.tsx`:
   - `FileUploadZone.tsx` — drag-and-drop загрузка, прогресс, список файлов, поддержка PDF/XLSX/CSV/DOCX
   - `QueryForm.tsx` — textarea для запроса, выбор LLM (DeepSeek / LLaMA), кнопка «Создать отчёт»
   - Shadcn: `Card`, `Button`, `Progress`, `Badge`, `Select`
6. Создать `frontend/src/hooks/useFileUpload.ts` — TanStack Query mutation

**Критерий готовности:** пользователь загружает файл, вводит запрос, нажимает кнопку — в консоли браузера появляется `session_id` из ответа API.

---

### Этап 11 — Фронтенд: компоненты блоков (60 мин)

**Цель:** реализовать React-компонент для каждого типа блока.

**Задачи:**
1. Создать `frontend/src/components/blocks/TextBlock.tsx` — `prose` стиль Tailwind, поддержка `callout` и `quote`
2. Создать `frontend/src/components/blocks/KPICard.tsx` — значение, дельта, стрелка тренда, цветовое кодирование, источник
3. Создать `frontend/src/components/blocks/TableBlock.tsx` — Shadcn `Table`, сортировка, пагинация, экспорт CSV, условное форматирование
4. Создать `frontend/src/components/blocks/ChartBlock.tsx` — `react-vega` рендерит `vega_lite_spec`, подпись, интерактивность
5. Создать `frontend/src/components/blocks/InsightBlock.tsx` — иконка по типу (finding/anomaly/risk), severity badge, ссылки на источники
6. Создать `frontend/src/components/blocks/ComparisonBlock.tsx` — карточки рядом с визуальным выделением победителя
7. Создать `frontend/src/components/blocks/ForecastBlock.tsx` — линейный график с историческими данными + прогноз + доверительный интервал
8. Создать `frontend/src/components/blocks/RiskMatrix.tsx` — матрица 3x3 (probability × impact), точки рисков
9. Создать `frontend/src/components/blocks/ExecutiveSummary.tsx` — key findings список, recommendations список, итоговый вывод
10. Создать `frontend/src/features/report-builder/BlockRenderer.tsx` — диспетчер по `block_type`

**Критерий готовности:** Storybook (или page с mock-данными) показывает все блоки с тестовыми данными. Все TypeScript типы совпадают с Pydantic-схемами.

---

### Этап 12 — Фронтенд: Report Canvas и стриминг (45 мин)

**Цель:** собрать отчёт из приходящих по SSE блоков в реальном времени.

**Задачи:**
1. Создать `frontend/src/hooks/useReportStream.ts`:
   - подписка на SSE `GET /api/reports/{session_id}/stream`
   - добавление блоков по мере прихода, сортировка по `order`
   - обработка статусов задач
2. Создать страницу `Report.tsx`:
   - `ReportCanvas.tsx` — скроллируемый список блоков, анимация появления (Tailwind transitions)
   - `AgentMonitor.tsx` — боковая панель с прогрессом задач (отделы, статусы, токены)
   - `TokenCounter.tsx` — живой счётчик использованных токенов
   - Скелетоны (Shadcn `Skeleton`) для блоков в процессе выполнения
3. Реализовать `Table of Contents` — липкий sidebar, якоря к блокам
4. Создать `ReportExport.tsx` — кнопки «Экспорт PDF» (html2canvas + jsPDF) и «Экспорт JSON»

**Критерий готовности:** при создании отчёта страница открывается немедленно, блоки появляются один за другим по мере готовности. Агент-монитор показывает какой отдел сейчас работает.

---

### Этап 13 — Интеграционное тестирование E2E (45 мин)

**Цель:** проверить полный сквозной сценарий.

**Задачи:**
1. Подготовить 3 тестовых файла:
   - `tests/fixtures/sales_report.xlsx` — финансовые данные с таблицами
   - `tests/fixtures/market_analysis.pdf` — текстовый аналитический отчёт
   - `tests/fixtures/metrics.csv` — временной ряд с метриками
2. Написать `tests/integration/test_e2e.py`:
   - Тест 1: загрузка CSV → запрос «покажи тренды продаж» → `ReportSchema` содержит `ChartBlock` + `ForecastBlock`
   - Тест 2: загрузка PDF → запрос «выдели ключевые риски» → `ReportSchema` содержит `RiskMatrixBlock` + `InsightBlock`
   - Тест 3: загрузка XLSX с неправильными числами → все числа верифицированы через Fingerprint или помечены `PARTIAL`
3. Тест производительности: полный отчёт по CSV за ≤ 60 секунд, токены ≤ 4000

**Критерий готовности:** все тесты проходят с реальным LLM API.

---

### Этап 14 — Полировка и production-ready (30 мин)

**Цель:** подготовить к демонстрации и развёртыванию.

**Задачи:**
1. Настроить структурированное логирование (`structlog`) — JSON-формат, уровни, трассировка `session_id`
2. Добавить OpenTelemetry трассировки для агентских вызовов
3. Настроить `nginx.conf` для prod: раздача статики, proxy_pass на бэкенд, gzip
4. Настроить Alembic autogenerate для будущих миграций
5. Добавить `healthcheck` эндпоинт с проверкой всех зависимостей (Postgres, Redis, LLM API)
6. Написать `README.md` с инструкцией запуска в 3 команды
7. Настроить `pre-commit` хуки: `ruff`, `mypy`, `pytest -x`

**Критерий готовности:** `BUILD_TARGET=production docker compose up -d` — всё работает за nginx, логи в JSON, `GET /health` возвращает `{"status": "ok"}`.

---

### Итоговая карта этапов

```
Этап 0:  Scaffolding          ████░░░░░░░░░░░░░░░░  15 мин
Этап 1:  Схемы и типы         ████████░░░░░░░░░░░░  30 мин
Этап 2:  БД и миграции        ████████░░░░░░░░░░░░  30 мин
Этап 3:  Конвейер документов  ████████████████░░░░  60 мин  ← критический
Этап 4:  Инструментарий       ████████████████████  90 мин  ← самый объёмный
Этап 5:  LLM-провайдеры       ████████░░░░░░░░░░░░  30 мин
Этап 6:  Blackboard           ██████████░░░░░░░░░░  40 мин
Этап 7:  Worker + Critic       ████████████████████  90 мин  ← ключевая логика
Этап 8:  Оркестратор          ████████████░░░░░░░░  45 мин
Этап 9:  API + SSE            ████████░░░░░░░░░░░░  30 мин
Этап 10: Фронт: загрузка      ████████████░░░░░░░░  45 мин
Этап 11: Фронт: блоки         ████████████████░░░░  60 мин
Этап 12: Фронт: Canvas        ████████████░░░░░░░░  45 мин
Этап 13: E2E тесты            ████████████░░░░░░░░  45 мин
Этап 14: Production           ████████░░░░░░░░░░░░  30 мин
─────────────────────────────────────────────────────
Итого:                                           ~745 мин (~12 ч чистой работы)
```

**Порядок приоритетов при ограниченном времени:**  
`0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9` — минимально работающий бэкенд  
`10 → 11 → 12` — подключить UI  
`13 → 14` — качество и деплой

---

---

## 17. Журнал архитектурных решений (ADR)

### ADR-001 — Переход с Hybrid RAG (BM25 + pgvector) на BM25-only

**Дата:** 2026-06-13  
**Статус:** Принято

**Контекст:**  
Оригинальная архитектура использовала `sentence-transformers` (модель `BAAI/bge-m3`, 1024 измерений) для создания векторных эмбеддингов при загрузке каждого файла. Это требовало:
- загрузки модели (~500 МБ) в память при старте backend'а
- 5–30 секунд на батчевое embedding при загрузке документа
- GPU для приемлемой скорости (на CPU — крайне медленно)

**Решение:**  
Удалены `sentence-transformers`, `keybert` и `spacy` из зависимостей. Retrieval переведён на **BM25-only** через `rank-bm25`. Поле `embedding` в БД оставлено nullable для возможного возврата.

**Последствия:**
- ✅ Загрузка документа: с ~20 с до <1 с
- ✅ Startup time backend'а: с ~15 с до ~2 с
- ✅ Нет зависимости от GPU / тяжёлых ML-библиотек
- ⚠️ Ухудшение recall на парафразах и синонимах (~10–15% в типичных аналитических запросах)
- ⚠️ KeyBERT заменён на частотный TF-анализ в `extract_keywords`

---

### ADR-002 — Добавление React Error Boundary для блоков

**Дата:** 2026-06-13  
**Статус:** Принято

**Контекст:**  
При рендере некорректной Vega-Lite спецификации или невалидных данных блока React выбрасывал uncaught exception, что приводило к размонтированию всего дерева компонентов — страница становилась белой.

**Решение:**  
Создан `BlockErrorBoundary` (класс-компонент с `componentDidCatch`). Каждый блок в `ReportCanvas` и `ReportViewer` обёрнут в `<BlockErrorBoundary>`.

**Последствия:**
- ✅ Сбой одного блока не влияет на остальные
- ✅ Пользователь видит локальное сообщение об ошибке вместо белой страницы

---

### ADR-003 — Страницы просмотра отчётов без авторизации

**Дата:** 2026-06-13  
**Статус:** Принято

**Контекст:**  
Приложение не имело механизма просмотра ранее сгенерированных отчётов. После перезагрузки страницы или в новом браузере отчёты были недоступны.

**Решение:**  
- Добавлен эндпоинт `GET /api/reports` (список всех завершённых сессий)
- Установлен `react-router-dom v6`, добавлены маршруты `/reports` и `/reports/:sessionId`
- Страницы `ReportsList` и `ReportViewer` не требуют авторизации

---

*Документ актуален на 2026-06-13. Обновляется при каждом значимом архитектурном изменении.*

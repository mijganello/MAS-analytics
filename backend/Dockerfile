FROM python:3.11-slim AS dependencies
WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential libpq-dev poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install setuptools first to ensure build backend is available
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy only the dependency manifest and install deps (no editable install)
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] sse-starlette python-multipart \
    instructor openai ollama \
    pydantic pydantic-settings \
    pymupdf pdfplumber python-docx openpyxl chardet \
    pandas numpy scipy statsmodels scikit-learn rapidfuzz \
    sentence-transformers vaderSentiment keybert nltk \
    sqlalchemy[asyncio] asyncpg pgvector alembic rank-bm25 \
    "redis[asyncio]" structlog httpx aiofiles \
    pytest pytest-asyncio pytest-cov ruff

# Download NLTK data (ignore failures in case of no network)
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')" || true

FROM dependencies AS development
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM dependencies AS production
COPY . .
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser
ENV PYTHONPATH=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--no-access-log"]

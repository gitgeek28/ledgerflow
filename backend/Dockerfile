# Build context: repository root (needs data/fixtures for the sample catalogue).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.9.28 /uv /bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
COPY data/fixtures /app/data/fixtures
RUN useradd -m ledgerflow && mkdir -p /app/backend/storage && chown -R ledgerflow /app/backend/storage
USER ledgerflow
EXPOSE 8000
# Default: API. The worker uses the same image with `python -m app.workers.runner`.
CMD ["sh", "-c", "uv run --no-sync alembic upgrade head && uv run --no-sync python -m app.seed.seed && uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

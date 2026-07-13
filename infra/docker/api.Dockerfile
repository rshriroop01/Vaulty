# Vaultly API — used for local dev (compose mounts the source for hot reload)
# and as the base for production images later.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so source edits don't bust the layer cache.
COPY pyproject.toml ./
RUN pip install -e ".[dev]" 2>/dev/null || true
COPY . .
RUN pip install -e ".[dev]"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

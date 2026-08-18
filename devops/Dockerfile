FROM python:3.12-slim AS python-base

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONPATH=/app

WORKDIR /app

# ==========================================================
# Builder Base
# ==========================================================

FROM python-base AS build-base

ENV POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/poetry/bin:/opt/venv/bin:${PATH}"

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        gcc \
        curl \
        libpq-dev \
 && curl -sSL https://install.python-poetry.org | python3 - \
 && python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && rm -rf /var/lib/apt/lists/*

# ==========================================================
# Development Base (shared dependencies)
# ==========================================================

FROM build-base AS development-base

COPY poetry.lock pyproject.toml ./

RUN poetry install --with dev --no-root

# ==========================================================
# Development
# ==========================================================

FROM development-base AS development

COPY . .

# ==========================================================
# Development API (FastAPI + Strawberry GraphQL)
# ==========================================================

FROM development AS development-api

CMD ["uvicorn", "main.asgi:fastapp", "--host", "0.0.0.0", "--port", "8500", "--reload"]

# ==========================================================
# Development Admin (Django)
# ==========================================================

FROM development AS development-admin

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Use Python 3.11 as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

RUN uv sync

# Copy application code
COPY . .

# Expose the FastAPI port
EXPOSE 8000

ARG DB_CONNECTION
ARG LOG_DIR
ARG LOG_MAX_SIZE
ARG LOG_MAX_FILES
ARG LOG_RETENTION_DAYS

ENV DB_CONNECTION=${DB_CONNECTION}
ENV LOG_DIR=${LOG_DIR}
ENV LOG_MAX_SIZE=${LOG_MAX_SIZE}
# Run database migrations and start the server
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn server:app --host 0.0.0.0 --port 8000"]


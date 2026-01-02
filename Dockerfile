# Use Python 3.11 as base image
FROM python:3.12-slim


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

# Install submodule as editable package using uv
RUN uv pip install -e alpha-miner

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

RUN uv pip install mlflow==3.6.0 numpy==2.3.5 psutil==7.1.3 pyarrow==21.0.0 scikit-learn==1.7.2

CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn server:app --host 0.0.0.0 --port 8000"]


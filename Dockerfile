# ── Stage 1: dependency installer ──────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

# Copy only dependency manifests first to maximise layer cache reuse.
COPY pyproject.toml uv.lock* ./

# Install production dependencies into /app/.venv.
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime image ──────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

# Create a non-root user so the container does not run as root (security best practice).
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy the pre-built virtualenv from the builder stage.
COPY --from=builder /app/.venv /app/.venv

# Copy application source.
COPY src/ ./src/

# Ensure the data directory exists and is writable by appuser.
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Healthcheck: probe the /health endpoint every 30 s, allow 10 s start-up time.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

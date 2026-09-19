# syntax=docker/dockerfile:1

# ── build stage: compile/install pinned dependencies into a virtualenv ─────────────────────────────
FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements/lock.txt requirements/lock.txt
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements/lock.txt

# ── runtime stage: no compilers, no pip cache, non-root user ───────────────────────────────────────
FROM python:3.11-slim AS runtime

# Secure by default: refuse to boot with development secrets. docker-compose.yml overrides this for local use.
ENV ENVIRONMENT=production \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8501 \
    HOME=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=app:app backend backend
COPY --chown=app:app frontend frontend
COPY --chown=app:app .streamlit .streamlit
RUN mkdir -p /data/uploads /app/models && chown -R app:app /data /app/models

USER app
EXPOSE 8501

# The worker container has no HTTP server; docker-compose disables this check for it.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/_stcore/health' % os.environ['PORT'], timeout=4)"

CMD ["streamlit", "run", "frontend/customer_app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]

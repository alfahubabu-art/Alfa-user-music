# Debian bookworm ships glibc 2.36 → satisfies ntgcalls manylinux_2_28 wheels.
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 alfa

WORKDIR /app

# Dependencies first so the layer caches across code-only changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=alfa:alfa . .

RUN mkdir -p /app/media && chown -R alfa:alfa /app/media

USER alfa

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8080}/health" || exit 1

CMD ["python", "main.py"]

# Videl Render backend: Pyrogram bot, Flask internal API and MongoDB.
# The Next.js control panel is a separate Vercel deployment (webapp/).
FROM python:3.11-slim

LABEL maintainer="Beasgohan-code <https://github.com/Beasgohan-code/Videl0>" \
      org.opencontainers.image.title="Videl0 Render Backend" \
      org.opencontainers.image.source="https://github.com/Beasgohan-code/Videl0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=10000 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg curl build-essential python3-dev ca-certificates fonts-dejavu-core fonts-noto-core && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt scripts/check_voice_dependencies.py ./
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    python -c "import pyrogram, flask, waitress, pymongo; print('Videl backend dependencies OK')" && \
    python check_voice_dependencies.py

COPY vendor ./vendor
COPY videl ./videl
COPY config.py main.py start cookies.txt sample.env .env.example ./
RUN chmod +x start && mkdir -p downloads logs data && \
    python -m compileall -q videl config.py main.py

RUN useradd -m -s /bin/bash videl && chown -R videl:videl /app
USER videl

EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=8s --start-period=30s --retries=3 \
  CMD sh -c 'curl -fs http://127.0.0.1:${PORT:-10000}/health || exit 1'
CMD ["python", "main.py"]

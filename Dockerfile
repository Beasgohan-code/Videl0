# Videl0 • All-in-one image — bot + FastAPI keep-alive
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# system deps for ffmpeg + tgcalls
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git curl nodejs npm && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps first (cache)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Webapp build (optional — if you also host via same container, otherwise Vercel handles)
COPY webapp webapp
RUN if [ -f webapp/package.json ]; then cd webapp && npm install && npm run build || true; cd ..; fi

# App code
COPY bot bot
COPY server server
COPY .env.example .env.example
COPY bot/main.py bot/main.py

# non-root
RUN useradd -m videl && chown -R videl:videl /app
USER videl

EXPOSE 8000

# keep-alive server + bot polling concurrently
CMD ["bash","-c","python -m bot.main & uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8000}"]

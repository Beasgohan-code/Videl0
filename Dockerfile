# ── Videl Perfect • Production • Kurigram + aiogram + Full Stack ──────────────
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# system deps: ffmpeg for VC + nodejs for webapp
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git curl nodejs npm && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps (upstream Videl + Videl0 extras)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# webapp (Vercel hosts prod, but image keeps it for VPS)
COPY webapp webapp
RUN if [ -f webapp/package.json ]; then cd webapp && npm install && npm run build || true; cd ..; fi

# app code — production videl/ + full-stack bot/ + server
COPY videl videl
COPY bot bot
COPY server server
COPY config.py .
COPY main.py .
COPY start .
COPY cookies.txt ./cookies.txt
COPY .env.example .env.example

RUN chmod +x start

# non-root for safety
RUN useradd -m videl && chown -R videl:videl /app
USER videl

EXPOSE 10000

# Production: Flask health (10000) inside videl/__main__ already binds PORT
# Here we run videl (Pyrogram) + FastAPI keep-alive together
CMD ["bash","-c","python main.py & uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-10000} --log-level warning & wait"]

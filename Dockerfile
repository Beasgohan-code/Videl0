# ◍ Vɪᴅᴇʟ Perfect — Production Dockerfile • Cyber Dark
# Python 3.11 • ffmpeg • Node 20 • single PORT (Flask owns it)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ── System deps: ffmpeg (VC) + git/curl + Node 20 (webapp build) ─────────────
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg git curl ca-certificates gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/* && \
    node -v && npm -v && ffmpeg -version | head -1

WORKDIR /app

# ── Python deps (pinned) ──────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt && \
    # Force fresh yt-dlp (often stale in lock)
    pip install -U yt-dlp

# ── Webapp (built but runtime served via Vercel — kept for VPS) ─────────────
COPY webapp ./webapp
RUN if [ -f webapp/package.json ]; then \
      cd webapp && npm ci --include=dev 2>&1 | tail -5; npm run build 2>&1 | tail -20; cd ..; \
    fi

# ── App code ──────────────────────────────────────────────────────────────────
COPY videl ./videl
COPY bot ./bot
COPY server ./server
COPY config.py main.py start cookies.txt sample.env .env.example ./
RUN chmod +x start && ls -lh main.py config.py cookies.txt

# Optional: .env mounted at runtime; .env.example is fallback

# ── Non-root ─────────────────────────────────────────────────────────────────
RUN useradd -m -s /bin/bash videl && chown -R videl:videl /app
USER videl

EXPOSE 10000 8000

# ── Entrypoint ────────────────────────────────────────────────────────────────
# videl/__main__.py owns PORT (Flask health+ Eldian API)
# server/app.py (FastAPI keep-alive) runs on KEEPALIVE_PORT if set, else disabled to avoid port clash.
# This fixes the old bug where both bound :10000 simultaneously.
#
# For Render/Koyeb single-port: only videl runs → passes healthCheckPath: /health
# For VPS with two ports: set KEEPALIVE_PORT=8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fs http://127.0.0.1:${PORT:-10000}/health || exit 1

CMD ["bash", "-c", "\
if [ -n \"$KEEPALIVE_PORT\" ]; then \
  echo \"◍ ᴠɪᴅᴇʟ ᴘᴇʀғᴇᴄᴛ — videl:$PORT + keep-alive:$KEEPALIVE_PORT ◍\"; \
  uvicorn server.app:app --host 0.0.0.0 --port \"$KEEPALIVE_PORT\" --log-level warning & \
  python main.py; \
else \
  echo \"◍ ᴠɪᴅᴇʟ ᴘᴇʀғᴇᴄᴛ — videl:$PORT ◍\"; \
  exec python main.py; \
fi \
"]

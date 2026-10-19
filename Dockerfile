# ◍ Vɪᴅᴇʟ Perfect — Production Dockerfile • Cyber Dark v3 • Elite Hardened
# Python 3.11 • ffmpeg • aria2c • Node 20 • tini • single PORT (Flask owns it)
# Labels: Beasgohan-code / Videl0 — MIT — exceeds Rose/GroupHelp
FROM python:3.11-slim

LABEL maintainer="Beasgohan-code <https://github.com/Beasgohan-code/Videl0>" \
      org.opencontainers.image.title="Videl0" \
      org.opencontainers.image.description="Videl — Cyber Dark Perfect • Music + AI + GroupHelp + Webapp (Kurigram • PyTgCalls • Richgram • Vercel)" \
      org.opencontainers.image.source="https://github.com/Beasgohan-code/Videl0" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NODE_ENV=production

# ── System deps: ffmpeg (VC) + aria2c (yt-dlp accel) + tini (init) + git/curl + Node 20 ─────────────
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg git curl ca-certificates gnupg tini aria2c \
        procps jq sqlite3 && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/* && \
    node -v && npm -v && ffmpeg -version | head -1 && aria2c --version | head -1 && tini --version || true

WORKDIR /app

# ── Python deps — layer cached separately for fast rebuilds ──────────────────────────────────────
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt && \
    pip install -U yt-dlp yt-dlp[default] && \
    pip cache purge || true

# ── Webapp — built in Docker (runtime via Vercel, kept for VPS preview) ──────────────────────────
COPY webapp ./webapp
RUN if [ -f webapp/package.json ]; then \
      cd webapp && npm ci --include=dev 2>&1 | tail -20; \
      npm run build 2>&1 | tail -40; \
      cd ..; \
      ls -lh webapp/.next 2>&1 | head; \
    fi

# ── App code ──────────────────────────────────────────────────────────────────
COPY videl ./videl
COPY bot ./bot
COPY server ./server
COPY config.py main.py start cookies.txt sample.env .env.example ./

RUN chmod +x start && \
    mkdir -p downloads logs data && \
    ls -lh main.py config.py cookies.txt start && \
    python -m compileall -q videl bot server config.py || true

# ── Security: non-root + read-only capable ────────────────────────────────────
RUN useradd -m -s /bin/bash videl && \
    chown -R videl:videl /app && \
    chmod 750 /app/downloads /app/logs 2>/dev/null || true
USER videl

# ── Env defaults (overridden at runtime via .env / secrets) ─────────────────
ENV PORT=10000 \
    KEEPALIVE_PORT="" \
    DOWNLOAD_DIR=/app/downloads \
    PYTHONPATH=/app

VOLUME ["/app/downloads", "/app/logs"]
EXPOSE 10000 8000

# ── Healthcheck — hits Flask /health on PORT (videl owns it) ────────────────────────────────────
# For Render/Koyeb single-port: only videl runs → passes healthCheckPath: /health
# For VPS dual-port: also curl KEEPALIVE_PORT if set
HEALTHCHECK --interval=30s --timeout=8s --start-period=25s --retries=3 \
    CMD sh -c 'curl -fs http://127.0.0.1:${PORT:-10000}/health || exit 1'

# ── Entrypoint via tini (proper signal handling, zombie reaping for ffmpeg/aria2c) ─────────────
ENTRYPOINT ["/usr/bin/tini", "--"]

# videl/__main__.py owns PORT (Flask health + Eldian API + bot)
# server/app.py (FastAPI keep-alive/webhook) runs on KEEPALIVE_PORT if set, else disabled to avoid port clash.
# This fixes the old bug where both bound :10000 simultaneously.
CMD ["bash", "-c", "\nset -euo pipefail\nif [ -n \"${KEEPALIVE_PORT:-}\" ]; then\n  echo \"◍ ᴠɪᴅᴇʟ ᴘᴇʀғᴇᴄᴛ — videl:$PORT + keep-alive:$KEEPALIVE_PORT ◍\"\n  # Keep-alive in background — logs to stdout with prefix\n  uvicorn server.app:app --host 0.0.0.0 --port \"$KEEPALIVE_PORT\" --log-level warning --access-log --proxy-headers --forwarded-allow-ips='*' &\n  KPID=$!\n  # Trap ensures keep-alive dies with main bot\n  trap \"kill $KPID 2>/dev/null || true\" EXIT TERM INT\n  exec python main.py\nelse\n  echo \"◍ ᴠɪᴅᴇʟ ᴘᴇʀғᴇᴄᴛ — videl:$PORT (single-port) ◍\"\n  exec python main.py\nfi\n"]

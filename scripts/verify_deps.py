#!/usr/bin/env python3
"""
Proper solution verifier — run locally or in Docker to catch 404 pins before Render.
Usage: python scripts/verify_deps.py  (or pip install --dry-run -r requirements.txt)
"""
import subprocess, sys

checks = [
    ("pyrogram import", "import pyrogram; print(pyrogram.__version__)"),
    ("tgcrypto import", "import tgcrypto; print('tgcrypto ok')"),
    ("flask import", "import flask; print(flask.__version__)"),
    ("pymongo import", "import pymongo; print(pymongo.version)"),
    ("aiohttp import", "import aiohttp; print(aiohttp.__version__)"),
    ("bot imports", "from videl import bot, assistant, call_py; print('bot imports ok')"),
]

ok = True
for name, code in checks:
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    status = "✅" if r.returncode == 0 else "❌"
    print(f"{status} {name}: {(r.stdout or r.stderr).strip()[:120]}")
    if r.returncode != 0:
        ok = False

# Dry-run
print("\n--- pip dry-run ---")
r = subprocess.run([sys.executable, "-m", "pip", "install", "--dry-run", "-r", "requirements.txt"], capture_output=True, text=True)
if r.returncode == 0:
    print("✅ pip dry-run ok — all pins exist on PyPI")
else:
    print("❌ pip dry-run failed:\n", r.stderr[-2000:])
    ok = False

sys.exit(0 if ok else 1)

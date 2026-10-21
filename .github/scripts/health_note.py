"""Print a GitHub annotation for a /health payload read from stdin.

A deploy can be perfectly healthy while Telegram is unreachable. That is worth
saying out loud in the workflow summary, but it is not a broken release, so the
job stays green.
"""
import json
import sys


def main():
    try:
        health = json.load(sys.stdin)
    except ValueError:
        return 0
    status = health.get("bot_status")
    if status != "online":
        reason = health.get("bot_error") or "no error recorded"
        print(f"::warning title=Bot not online::bot_status={status} — {reason}")
    elif health.get("degraded"):
        reasons = ", ".join(health.get("degraded_reasons") or [])
        print(f"::warning title=Backend degraded::{reasons}")
    else:
        print("Bot online, backend not degraded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

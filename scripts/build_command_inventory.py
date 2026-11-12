"""Refresh runtime columns in the historical/current command audit CSV.

Run from the repository root. Registry metadata is derived from the live
command catalog and declarative manifest. Legacy permissions remain linked to
the original decorator/handler evidence; discovery is not authorization.
"""
from __future__ import annotations

import csv
from pathlib import Path

from videl.app.routes import COMMANDS as MANIFEST
from videl.utils.bot_commands import command_menu
from videl.utils.command_catalog import commands

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "COMMAND_INVENTORY_AUDIT.csv"
RUNTIME_FIELDS = (
    "registry_status",
    "runtime_category",
    "catalog_context_hint",
    "runtime_summary",
    "runtime_source",
    "runtime_handler",
    "runtime_auth_policy",
    "runtime_required_telegram_rights",
    "runtime_block_policy",
    "bot_command_menu_scopes",
)


def main() -> None:
    with INVENTORY.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    live = {entry["name"]: entry for entry in commands()}
    manifest = {item.name: item for item in MANIFEST}
    public_menu = {item["command"] for item in command_menu(owner=False)}
    owner_menu = {item["command"] for item in command_menu(owner=True)}
    by_name = {row["command"]: row for row in rows}
    if len(by_name) != len(rows):
        raise SystemExit("Historical inventory contains duplicate command names")

    for name, entry in live.items():
        if name not in by_name:
            row = {field: "" for field in fields}
            row.update({
                "command": name,
                "description": entry["summary"],
                "current_category": entry["category"],
                "handler_location": f"{entry['source']}::{entry['handler']}",
                "permission_requirements": "New live registry entry; audit permissions in source before changing policy.",
                "availability": entry["context"],
                "dependencies": "Not populated; inspect handler imports and call chain.",
                "disposition": "Live; requires Stage C command-by-command review.",
            })
            rows.append(row)
            by_name[name] = row

    for row in rows:
        name = row["command"]
        entry = live.get(name)
        if entry is None:
            values = {field: "" for field in RUNTIME_FIELDS}
            values["registry_status"] = "removed/historical"
        else:
            command = manifest.get(name)
            if command is None:
                policy = "legacy decorator + handler; inspect permission_requirements/source"
                rights = "handler-specific; inspect source"
                block_policy = "legacy handler/filter"
            else:
                policy = command.policy
                rights = ",".join(command.rights) or "none declared"
                block_policy = command.block_policy
            scopes = []
            if name in public_menu:
                scopes.append("public")
            if name in owner_menu:
                scopes.append("owner")
            values = {
                "registry_status": "live",
                "runtime_category": entry["category"],
                "catalog_context_hint": entry["context"],
                "runtime_summary": entry["summary"],
                "runtime_source": entry["source"],
                "runtime_handler": entry["handler"],
                "runtime_auth_policy": policy,
                "runtime_required_telegram_rights": rights,
                "runtime_block_policy": block_policy,
                "bot_command_menu_scopes": ",".join(scopes) or "not in curated BotCommand menu",
            }
        row.update(values)

    # Keep the historical baseline rows but label their current registration
    # state. Live commands are sorted first; removed rows remain for traceability.
    rows.sort(key=lambda row: (row["registry_status"] != "live", row["command"]))
    for field in RUNTIME_FIELDS:
        if field not in fields:
            fields.append(field)
    with INVENTORY.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {sum(row['registry_status'] == 'live' for row in rows)} live and "
          f"{sum(row['registry_status'] != 'live' for row in rows)} historical rows to {INVENTORY.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

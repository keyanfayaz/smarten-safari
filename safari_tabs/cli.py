"""CLI for collecting, filtering, and inspecting Safari tab sources."""

import argparse
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import sys
from time import perf_counter

from .adapters import catalog, groups, icloud, windows
from .coverage import check as check_coverage
from .database import inspect_schema
from .model import QueryError, scope_dict
from .verification import verify


ADAPTERS = {"windows": windows.read, "groups": groups.read, "icloud": icloud.read,
            "profiles": catalog.read_profiles, "session": catalog.read_session}
INVENTORIES = {"windows": "windows", "groups": "groups", "devices": "icloud",
               "profiles": "profiles", "session": "session"}


def parser() -> argparse.ArgumentParser:
    """Describe source selection and reject unsupported filter combinations."""
    root = argparse.ArgumentParser(description="Smarten for Safari: read Safari tabs using independent experimental adapters.")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("verify", help="Cross-check live windows using JXA and AppleScript")
    commands.add_parser("doctor", help="Check source availability and limits without printing browsing content")
    tabs = commands.add_parser("tabs", help="List tab titles, URLs, and source-local scope IDs")
    tabs.add_argument("--source", choices=ADAPTERS, default="windows")
    tabs.add_argument("--db", help="Explicit SQLite file (database sources only)")
    tabs.add_argument("--window-id", help="Exact local window ID")
    tabs.add_argument("--group", help="Exact stored group/container name")
    tabs.add_argument("--group-id", help="Exact stored group/container ID")
    tabs.add_argument("--device", help="Exact synced device name")
    tabs.add_argument("--device-id", help="Exact synced device UUID")
    tabs.add_argument("--profile-id", help="Exact discovered profile ID (groups/profiles/session)")
    tabs.add_argument("--stored-window-id", help="Exact stored window ID (session source)")
    tabs.add_argument("--search", help="Case-insensitive substring in titles or URLs")
    tabs.add_argument("--format", choices=("json", "titles", "urls"), default="json")
    for command in INVENTORIES:
        inventory = commands.add_parser(command, help=f"List {command} and tab counts")
        if command != "windows":
            inventory.add_argument("--db", help="Explicit SQLite file")
    schema = commands.add_parser("schema", help="Inspect SQLite table definitions without browsing data")
    schema.add_argument("--source", required=True, choices=("groups", "icloud"))
    schema.add_argument("--db", help="Explicit SQLite file")
    return root


def main(argv: list[str] | None = None) -> int:
    """Print JSON by default; failures go to stderr and return a nonzero status."""
    arguments = parser()
    args = arguments.parse_args(argv)
    source = args.source if args.command in ("tabs", "schema") else INVENTORIES.get(args.command)
    path = getattr(args, "db", None)
    if source == "windows" and path is not None:
        arguments.error("--db requires a database source: groups, icloud, profiles, or session")
    if args.command == "tabs":
        allowed = {"window_id": "windows", "group": "groups", "group_id": "groups",
                   "device": "icloud", "device_id": "icloud", "stored_window_id": "session"}
        for option, expected in allowed.items():
            if getattr(args, option) is not None and source != expected:
                arguments.error(f"--{option.replace('_', '-')} requires --source {expected}")
        if args.profile_id is not None and source not in ("groups", "profiles", "session"):
            arguments.error("--profile-id requires --source groups, profiles, or session")
    try:
        if args.command == "doctor":
            report = check_coverage(ADAPTERS)
            print(json.dumps(report, indent=2))
            return 0 if report["status"] == "available" else 1
        if args.command == "verify":
            print(json.dumps(verify(), indent=2))
            return 0
        if args.command == "schema":
            print(json.dumps(inspect_schema(source, path), indent=2))
            return 0
        started = perf_counter()
        snapshot = ADAPTERS[source]() if source == "windows" else ADAPTERS[source](path)
        elapsed = round((perf_counter() - started) * 1000, 2)
        if args.command == "tabs":
            scope_id = next((value for value in (args.window_id, args.group_id, args.device_id, args.stored_window_id)
                             if value is not None), None)
            name = args.group if args.group is not None else args.device
            scopes = [scope for scope in snapshot.scopes
                      if (scope_id is None or scope.id == scope_id)
                      and (name is None or scope.name == name)
                      and (args.profile_id is None or scope.profile_id == args.profile_id)]
            scope_ids = {scope.id for scope in scopes}
            search = (args.search or "").casefold()
            tabs = [tab for tab in snapshot.tabs if tab.scope_id in scope_ids
                    and (search in (tab.title or "").casefold() or search in (tab.url or "").casefold())]
            snapshot = replace(snapshot, scopes=scopes, tabs=tabs)
            if args.format != "json":
                for warning in snapshot.warnings:
                    print(f"warning: {warning}", file=sys.stderr)
                for tab in tabs:
                    value = tab.title if args.format == "titles" else tab.url
                    print((value or "").replace("\r", " ").replace("\n", " "))
                return 0
        output = asdict(snapshot)
        output["scopes"] = [scope_dict(scope) for scope in snapshot.scopes]
        counts = Counter(tab.scope_id for tab in snapshot.tabs)
        for scope in output["scopes"]:
            scope["tab_count"] = counts[scope["id"]]
        if args.command != "tabs":
            del output["tabs"]
        output["collected_at"] = datetime.now(timezone.utc).isoformat()
        output["elapsed_ms"] = elapsed
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except QueryError as error:
        print(f"error [{error.code}]: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

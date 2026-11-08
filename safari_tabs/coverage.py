"""Probe source availability without returning browsing content."""

from datetime import datetime, timezone
from time import perf_counter

from .model import QueryError


LIMITATIONS = {
    "windows": [
        "Only tabs exposed by each open window's selected group are included.",
        "Window IDs are not mapped to named Tab Groups or Safari profiles.",
    ],
    "groups": [
        "Profiled schemas distinguish named groups; reduced schemas retain experimental container output.",
        "Classification uses observed private-schema fields and is version-dependent.",
    ],
    "icloud": [
        "Devices are discovered from the local sync cache; remote liveness and sync freshness are unknown.",
        "Remote window membership and complete Apple Account device coverage are unavailable.",
    ],
    "profiles": ["Profiles come from stored subtype-2 records; tab counts cover named groups."],
    "session": [
        "Stored window/group/profile relationships may describe a previous session.",
        "Stored IDs are not mapped to live Apple Events window IDs; pinned-tab coverage varies by profile.",
    ],
}


def check(adapters: dict) -> dict:
    """Attempt each reader once, preserving partial success and omitting all record contents."""
    sources = []
    for source, read in adapters.items():
        started = perf_counter()
        result = {"source": source, "limitations": LIMITATIONS[source]}
        try:
            snapshot = read()
            result.update(status="available", scope_count=len(snapshot.scopes), tab_count=len(snapshot.tabs))
        except QueryError as error:
            result.update(status="unavailable", error={"code": error.code, "message": str(error)})
        result["elapsed_ms"] = round((perf_counter() - started) * 1000, 2)
        sources.append(result)
    available = sum(source["status"] == "available" for source in sources)
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "status": "available" if available == len(sources) else "partial" if available else "unavailable",
        "sources": sources,
        "limitations": [
            "Availability means a read succeeded, not that every requested capability is implemented.",
            "Sources are separate observations; collected_at is not an iCloud sync timestamp.",
            "Sources overlap; do not sum their tab counts into a unique global total.",
            "Private-browsing exclusion and complete profile coverage are not established.",
        ],
    }

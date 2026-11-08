"""Experimental parent/child interpretation of SafariTabs.db."""

from pathlib import Path

from ..database import database_path, open_database, require_columns
from ..model import Scope, Snapshot, Tab
from . import catalog


def read(path: str | Path | None = None) -> Snapshot:
    """Read live folder rows and their direct tab children from the local store."""
    result = Snapshot("groups", warnings=[
        "Experimental private schema: scopes are stored containers, including internal folders; "
        "not every scope is a named Safari Tab Group. No device ownership is inferred."
    ])
    with open_database(database_path("groups", path)) as connection:
        available = require_columns(connection, "bookmarks", {"id", "parent", "type", "title", "url"})
        if catalog.PROFILE_COLUMNS <= available:
            return catalog.collect(connection)
        conditions = []
        if "deleted" in available:
            conditions.append("COALESCE(deleted, 0) = 0")
        else:
            result.warnings.append("No deleted column: deleted records cannot be excluded.")
        if "date_closed" in available:
            conditions.append("COALESCE(date_closed, 0) = 0")
        else:
            result.warnings.append("No date_closed column: closed records cannot be excluded.")
        position = "order_index" if "order_index" in available else "NULL"
        where = " AND ".join(conditions) or "1"
        rows = list(connection.execute(
            f"SELECT id, parent, type, title, url, {position} AS position "
            f"FROM bookmarks WHERE {where} ORDER BY position, id"
        ))
    folders = {row["id"]: row for row in rows if row["type"] == 1}

    def has_live_ancestry(folder_id):
        # Closed/deleted parents and cycles must not resurrect their descendants.
        seen = set()
        while folder_id in folders:
            if folder_id in seen:
                return False
            seen.add(folder_id)
            folder_id = folders[folder_id]["parent"]
        return folder_id is None or folder_id == 0

    live_ids = {folder_id for folder_id in folders if has_live_ancestry(folder_id)}
    result.scopes = [
        Scope(str(row["id"]), row["title"] or "", "group")
        for row in rows if row["id"] in live_ids
    ]
    result.tabs = [
        Tab(str(row["id"]), str(row["parent"]), row["title"], row["url"], row["position"])
        for row in rows
        if row["type"] != 1 and row["parent"] in live_ids
        and row["url"] is not None and row["url"].strip()
    ]
    return result

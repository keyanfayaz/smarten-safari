"""Device-scoped records from Safari's locally synced iCloud cache."""

from pathlib import Path

from ..database import database_path, open_database, require_columns
from ..model import Scope, Snapshot, Tab


def read(path: str | Path | None = None) -> Snapshot:
    """Read cached device tabs without asserting remote liveness or window membership."""
    result = Snapshot("icloud", warnings=[
        "This is a local sync cache, not a live remote-device query; "
        "remote windows and named Tab Group membership are unavailable."
    ])
    with open_database(database_path("icloud", path)) as connection:
        require_columns(connection, "cloud_tab_devices", {"device_uuid", "device_name"})
        available = require_columns(connection, "cloud_tabs", {"tab_uuid", "device_uuid", "title", "url"})
        result.scopes = [
            Scope(str(row["device_uuid"]), row["device_name"] or "", "device")
            for row in connection.execute(
                "SELECT device_uuid, device_name FROM cloud_tab_devices ORDER BY device_name, device_uuid"
            )
        ]
        position = "position" if "position" in available else "NULL"
        result.tabs = [
            Tab(str(row["tab_uuid"]), str(row["device_uuid"]), row["title"], row["url"], row["position"])
            for row in connection.execute(
                f"SELECT tab_uuid, device_uuid, title, url, {position} AS position "
                "FROM cloud_tabs ORDER BY device_uuid, position, tab_uuid"
            )
        ]
    known = {scope.id for scope in result.scopes}
    for tab in result.tabs:
        if tab.scope_id not in known:
            result.scopes.append(Scope(tab.scope_id, "", "device"))
            known.add(tab.scope_id)
            result.warnings.append(f"Device metadata missing for {tab.scope_id}.")
    return result

"""Device-scoped records from Safari's locally synced iCloud cache."""

import json
import math
from pathlib import Path
import zlib

from ..database import database_path, open_database, require_columns
from ..model import Scope, Snapshot, Tab


def decode_position(value):
    """Accept numeric ranks and the observed single-component compressed rank format."""
    if isinstance(value, bytes):
        try:
            decoder = zlib.decompressobj()
            decoded = decoder.decompress(value, 8193)
            if len(decoded) > 8192 or not decoder.eof or decoder.unused_data:
                return None
            data = json.loads(decoded)
            parts = data.get("sortValues") if isinstance(data, dict) else None
            if not isinstance(parts, list) or len(parts) != 1 or not isinstance(parts[0], dict):
                return None
            value = parts[0].get("sortValue")
        except (ValueError, UnicodeError, zlib.error):
            return None
    if type(value) is int and -(2 ** 63) <= value < 2 ** 63:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    return None


def read(path: str | Path | None = None) -> Snapshot:
    """Read cached device tabs without asserting remote liveness or window membership."""
    result = Snapshot("icloud", warnings=[
        "This is a local sync cache, not a live remote-device query; "
        "remote windows and named Tab Group membership are unavailable."
    ])
    with open_database(database_path("icloud", path)) as connection:
        device_columns = require_columns(connection, "cloud_tab_devices", {"device_uuid", "device_name"})
        available = require_columns(connection, "cloud_tabs", {"tab_uuid", "device_uuid", "title", "url"})
        device_type = "device_type_identifier" if "device_type_identifier" in device_columns else "NULL"
        result.scopes = [
            Scope(str(row["device_uuid"]), row["device_name"] or "", "device", device_type=row["device_type"])
            for row in connection.execute(
                f"SELECT device_uuid, device_name, {device_type} AS device_type "
                "FROM cloud_tab_devices ORDER BY device_name, device_uuid"
            )
        ]
        position = "position" if "position" in available else "NULL"
        rows = list(connection.execute(
                f"SELECT tab_uuid, device_uuid, title, url, {position} AS position "
                "FROM cloud_tabs ORDER BY device_uuid, tab_uuid"
            ))
        unknown = 0
        for row in rows:
            rank = decode_position(row["position"])
            unknown += row["position"] is not None and rank is None
            result.tabs.append(Tab(str(row["tab_uuid"]), str(row["device_uuid"]), row["title"], row["url"], rank))
        result.tabs.sort(key=lambda tab: (tab.scope_id, tab.position is None,
                                         tab.position if tab.position is not None else 0, tab.id))
        if unknown:
            result.warnings.append(f"{unknown} ordering values are unsupported; those tabs use stable ID order.")
    known = {scope.id for scope in result.scopes}
    for tab in result.tabs:
        if tab.scope_id not in known:
            result.scopes.append(Scope(tab.scope_id, "", "device"))
            known.add(tab.scope_id)
            result.warnings.append(f"Device metadata missing for {tab.scope_id}.")
    return result

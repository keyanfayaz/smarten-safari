"""Profile and stored-window relationships observed in Safari's profiled database layout."""

from dataclasses import replace

from ..database import database_path, open_database, require_columns
from ..model import QueryError, Scope, Snapshot, Tab, scope_dict


PROFILE_COLUMNS = {"id", "parent", "type", "title", "url", "order_index", "subtype",
                   "hidden", "special_id", "external_uuid", "deleted", "date_closed"}


def collect(connection, source="groups") -> Snapshot:
    """Use stored relationships; never equate SQLite window IDs with Apple Events IDs."""
    require_columns(connection, "bookmarks", PROFILE_COLUMNS)
    rows = list(connection.execute(
        "SELECT id,parent,type,title,url,order_index,subtype,hidden,special_id,external_uuid "
        "FROM bookmarks WHERE COALESCE(deleted,0)=0 AND COALESCE(date_closed,0)=0 ORDER BY order_index,id"
    ))
    folders = {row["id"]: row for row in rows if row["type"] == 1}

    def visible_ancestry(folder_id):
        visited = set()
        while folder_id in folders:
            row = folders[folder_id]
            if folder_id in visited or row["hidden"] or row["special_id"]:
                return False
            visited.add(folder_id)
            folder_id = row["parent"]
        return folder_id is None or folder_id == 0

    profiles = {row["id"]: row for row in folders.values()
                if row["subtype"] == 2 and row["parent"] == 0 and visible_ancestry(row["id"])}
    default_ids = [key for key, row in profiles.items() if row["external_uuid"] == "DefaultProfile"]
    default_id = default_ids[0] if len(default_ids) == 1 else None

    def profile_fields(profile_id):
        row = profiles.get(profile_id)
        if row is None:
            return {}
        return {"profile_id": str(profile_id),
                "profile_name": row["title"] or ("Default profile" if profile_id == default_id else "")}

    profile_scopes = [Scope(str(key), profile_fields(key)["profile_name"], "profile", **profile_fields(key))
                      for key in profiles]
    named = {key: row for key, row in folders.items()
             if key != 0 and row["subtype"] == 0 and row["parent"] in {0, *profiles}
             and visible_ancestry(key)}
    tabs_by_parent = {}
    for row in rows:
        if row["type"] == 0:
            tabs_by_parent.setdefault(row["parent"], []).append(row)
    warnings = [
        "Uses an observed private Safari schema; layouts on other versions may differ.",
        "Named groups are visible subtype-0 folders under the root or a subtype-2 profile; "
        "recovered, hidden, device, and auxiliary containers are excluded from the group inventory.",
    ]
    if default_id is None:
        warnings.append("The default profile could not be identified; root groups have no profile assignment.")

    def group_tabs(group_id, scope_id, prefix="", pinned=None):
        return [Tab(prefix + str(row["id"]), scope_id, row["title"], row["url"], row["order_index"],
                    group_id=str(group_id), pinned=pinned) for row in tabs_by_parent.get(group_id, [])]

    scopes, tabs = [], []
    if source in ("groups", "profiles"):
        for key, row in named.items():
            profile_id = row["parent"] if row["parent"] in profiles else default_id
            scopes.append(Scope(str(key), row["title"] or "", "group", **profile_fields(profile_id)))
            tabs.extend(group_tabs(key, str(key)))
            auxiliary = [child for child in folders.values() if child["parent"] == key and child["subtype"] == 1
                         and visible_ancestry(child["id"])]
            for child in auxiliary:
                nested = group_tabs(child["id"], str(key))
                if nested:
                    tabs.extend(replace(tab, group_id=str(key)) for tab in nested)
                    warnings.append("Auxiliary child-container tabs are included; their pin state/order is unknown.")
        if source == "profiles":
            assignments = {scope.id: scope.profile_id for scope in scopes}
            tabs = [replace(tab, scope_id=assignments[tab.scope_id]) for tab in tabs
                    if assignments[tab.scope_id] is not None]
            scopes = profile_scopes
            warnings.append("Profile tab counts cover named groups; use the session source for stored window tabs.")
    elif source == "session":
        require_columns(connection, "windows", {"id", "uuid", "active_tab_group_id", "active_profile_id",
                                                "private_tab_group_id", "date_closed", "is_last_session"})
        pinned = {row["title"].casefold(): row["id"] for row in folders.values()
                  if row["parent"] is None and row["hidden"] and row["title"] in ("pinned", "privatePinned")}
        windows = list(connection.execute(
            "SELECT id,uuid,active_tab_group_id,active_profile_id,private_tab_group_id,is_last_session "
            "FROM windows WHERE COALESCE(date_closed,0)=0 ORDER BY id"
        ))
        for window in windows:
            group_id = window["active_tab_group_id"]
            group = folders.get(group_id)
            window_id = str(window["id"])
            private = group_id is not None and group_id == window["private_tab_group_id"]
            scopes.append(Scope(window_id, "Stored window " + window_id, "stored_window",
                                **profile_fields(window["active_profile_id"]),
                                group_id=str(group_id) if group_id is not None else None,
                                group_name=group["title"] if group is not None else None,
                                window_uuid=window["uuid"], is_private=private))
            if group is None:
                warnings.append(f"Stored window {window_id} has no readable active group.")
                continue
            pin_group = pinned.get("privatepinned" if private else "pinned")
            if pin_group is not None and window["active_profile_id"] == default_id:
                tabs.extend(group_tabs(pin_group, window_id, window_id + ":", pinned=True))
            tabs.extend(group_tabs(group_id, window_id, window_id + ":", pinned=False))
        warnings.append("Stored window IDs/UUIDs differ from live Apple Events IDs; records may describe a previous session.")
        warnings.append("Global default-profile pinned tabs are included; profile/group-specific pin layouts are not established.")
    else:
        raise QueryError("Unknown catalog source", "unsupported_source")
    return Snapshot(source, scopes, tabs, list(dict.fromkeys(warnings)),
                    context={"profiles": [scope_dict(scope) for scope in profile_scopes],
                             "layout": "profiled_bookmarks", "default_profile_id": str(default_id) if default_id is not None else None})


def read_profiles(path=None):
    with open_database(database_path("groups", path)) as connection:
        return collect(connection, "profiles")


def read_session(path=None):
    with open_database(database_path("groups", path)) as connection:
        return collect(connection, "session")

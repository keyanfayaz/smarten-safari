"""Read-only SQLite access and schema discovery for Safari's private stores."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3

from .model import QueryError


DATABASES = {"groups": "SafariTabs.db", "icloud": "CloudTabs.db"}


def database_path(source: str, override: str | Path | None = None) -> Path:
    """Choose an explicit file or the first existing standard Safari location."""
    if override is not None:
        return Path(override).expanduser().resolve()
    roots = (
        Path.home() / "Library/Containers/com.apple.Safari/Data/Library/Safari",
        Path.home() / "Library/Safari",
    )
    for root in roots:
        candidate = root / DATABASES[source]
        if candidate.is_file():
            return candidate
    raise QueryError(f"{DATABASES[source]} not found; supply --db PATH.")


@contextmanager
def open_database(path: Path):
    """Read a consistent transaction, including committed WAL data, without SQL writes."""
    connection = None
    try:
        # KEEP: mode=ro must not become immutable=1; Safari may have live WAL data.
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        yield connection
    except sqlite3.Error as error:
        raise QueryError(
            f"Cannot read {path.name}: {error}. Check the path and schema; for live Safari "
            "data, the terminal or host app may need Full Disk Access."
        ) from error
    finally:
        if connection is not None:
            connection.close()


def columns(connection: sqlite3.Connection, table: str) -> set[str]:
    """Return column names without interpolating SQL identifiers."""
    return {row["name"] for row in connection.execute("SELECT name FROM pragma_table_info(?)", (table,))}


def require_columns(connection: sqlite3.Connection, table: str, required: set[str]) -> set[str]:
    """Reject incompatible schemas with an actionable error."""
    available = columns(connection, table)
    missing = required - available
    if missing:
        raise QueryError(
            f"Unsupported schema: {table} is missing {', '.join(sorted(missing))}; "
            "inspect it with the schema command."
        )
    return available


def inspect_schema(source: str, path: str | Path | None = None) -> dict:
    """Return table definitions only, without tab titles or URLs."""
    with open_database(database_path(source, path)) as connection:
        tables = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
        return {"source": source, "tables": [dict(row) for row in tables]}

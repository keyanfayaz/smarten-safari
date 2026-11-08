"""Read-only SQLite access and schema discovery for Safari's private stores."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
import stat

from .model import QueryError


DATABASES = {"groups": "SafariTabs.db", "icloud": "CloudTabs.db"}


def access_error(path: Path) -> QueryError:
    return QueryError(
        f"Permission denied reading {path.name}. Check System Settings > Privacy & Security > "
        "Full Disk Access for the application running this reader; the CLI and tunnel may have "
        "different permissions. Full Disk Access is a broad macOS grant, not limited to Safari.",
        "permission_denied",
    )


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
        try:
            mode = candidate.stat().st_mode
        except FileNotFoundError:
            continue
        except PermissionError as error:
            raise access_error(candidate) from error
        except OSError as error:
            raise QueryError(f"Cannot inspect {candidate.name}: {error.strerror}.", "database_unavailable") from error
        if stat.S_ISREG(mode):
            return candidate
    raise QueryError(f"{DATABASES[source]} not found; supply --db PATH.", "database_missing")


@contextmanager
def open_database(path: Path):
    """Read a consistent transaction, including committed WAL data, without SQL writes."""
    connection = None
    try:
        # SQLite's CANTOPEN alone cannot distinguish an absent file from a denied read.
        with path.open("rb"):
            pass
        # KEEP: mode=ro must not become immutable=1; Safari may have live WAL data.
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        yield connection
    except PermissionError as error:
        raise access_error(path) from error
    except FileNotFoundError as error:
        raise QueryError(f"{path.name} not found; supply --db PATH.", "database_missing") from error
    except OSError as error:
        raise QueryError(f"Cannot read {path.name}: {error.strerror}.", "database_unavailable") from error
    except sqlite3.Error as error:
        sqlite_code = getattr(error, "sqlite_errorcode", 0) & 0xff
        # Python 3.10 does not expose SQLite result-code constants or exception codes.
        code = {
            5: "database_busy", 6: "database_busy",
            26: "invalid_database", 11: "invalid_database",
        }.get(sqlite_code, "database_unavailable")
        raise QueryError(
            f"Cannot read {path.name}: {error}. Check the database and its WAL/shared-memory "
            "sidecar access; an open failure alone does not establish a permission problem.", code,
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
            "inspect it with the schema command.", "unsupported_schema",
        )
    return available


def inspect_schema(source: str, path: str | Path | None = None) -> dict:
    """Return table definitions only, without tab titles or URLs."""
    with open_database(database_path(source, path)) as connection:
        tables = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
        return {"source": source, "tables": [dict(row) for row in tables]}

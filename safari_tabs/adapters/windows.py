"""Live windows through macOS JavaScript for Automation (Apple Events)."""

import json
from pathlib import Path
import subprocess
import sys

from ..model import QueryError, Scope, Snapshot, Tab


def read() -> Snapshot:
    """Bulk-read titles and URLs per window in one bounded osascript process."""
    if sys.platform != "darwin":
        raise QueryError("The windows adapter requires macOS and Safari.")
    try:
        completed = subprocess.run(
            ["/usr/bin/osascript", "-l", "JavaScript", str(Path(__file__).with_suffix(".js"))],
            capture_output=True, text=True, timeout=30, check=True,
        )
    except subprocess.TimeoutExpired as error:
        raise QueryError("Safari did not respond within 30 seconds; check Automation permission and retry.") from error
    except subprocess.CalledProcessError as error:
        raise QueryError(
            "Safari automation failed; check System Settings > Privacy & Security > Automation. "
            + error.stderr.strip()
        ) from error
    except OSError as error:
        raise QueryError(f"Could not run osascript: {error}") from error
    try:
        data = json.loads(completed.stdout)
        return Snapshot(
            "windows",
            [Scope(**scope) for scope in data["scopes"]],
            [Tab(**tab) for tab in data["tabs"]],
            ["Only tabs exposed by each window's selected group are included. "
             "Tab IDs are window:index values and may change after reordering; collection is not atomic."],
        )
    except (ValueError, KeyError, TypeError) as error:
        raise QueryError("Safari automation returned an unexpected response.") from error

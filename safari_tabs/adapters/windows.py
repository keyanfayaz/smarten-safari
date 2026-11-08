"""Live windows through macOS JavaScript for Automation (Apple Events)."""

import json
from pathlib import Path
import subprocess
import sys

from ..model import QueryError, Scope, Snapshot, Tab


def read() -> Snapshot:
    """Require two matching observations within one bounded osascript process."""
    if sys.platform != "darwin":
        raise QueryError("The windows adapter requires macOS and Safari.", "unsupported_platform")
    try:
        completed = subprocess.run(
            ["/usr/bin/osascript", "-l", "JavaScript", str(Path(__file__).with_suffix(".js"))],
            capture_output=True, text=True, timeout=30, check=True,
        )
    except subprocess.TimeoutExpired as error:
        raise QueryError("Safari did not respond within 30 seconds; check Automation permission and retry.", "timeout") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip()
        code = "automation_denied" if "-1743" in detail else "source_unavailable"
        if "Safari tabs changed during collection" in detail:
            raise QueryError("Safari tabs changed during collection; retry when the session settles.",
                             "unstable_session") from error
        raise QueryError(
            "Safari automation failed; check System Settings > Privacy & Security > Automation. "
            + detail, code,
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
             "Two consecutive observations matched, but collection is not atomic. "
             "Tab IDs are window:index values and may change after reordering."],
        )
    except (ValueError, KeyError, TypeError) as error:
        raise QueryError("Safari automation returned an unexpected response.", "invalid_response") from error

"""Cross-check the live JXA adapter against an independent AppleScript query."""

from datetime import datetime, timezone
import json
import subprocess
from time import perf_counter

from .adapters import windows
from .model import QueryError


APPLE_SCRIPT = '''use framework "Foundation"
set values to {{}, {}, {}}
tell application "Safari"
    if running then
        set windowIds to id of every window
        set tabNames to name of every tab of every window
        set tabURLs to URL of every tab of every window
        set values to {windowIds, tabNames, tabURLs}
    end if
end tell
set jsonData to current application's NSJSONSerialization's dataWithJSONObject:values options:0 |error|:(missing value)
return (current application's NSString's alloc()'s initWithData:jsonData encoding:(current application's NSUTF8StringEncoding)) as text
'''


def verify() -> dict:
    """Check stable window IDs, titles, URLs, and order without printing browsing data."""
    started = perf_counter()
    before = windows.read()
    try:
        completed = subprocess.run(
            ["/usr/bin/osascript", "-l", "AppleScript", "-e", APPLE_SCRIPT],
            capture_output=True, text=True, check=True, timeout=30,
        )
        independent = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise QueryError("Independent AppleScript verification failed; check Safari Automation access.") from error
    after = windows.read()
    if before.scopes != after.scopes or before.tabs != after.tabs:
        raise QueryError("Safari changed during verification; retry when the session is stable.")
    expected = [
        [int(scope.id) for scope in before.scopes],
        [[tab.title for tab in before.tabs if tab.scope_id == scope.id] for scope in before.scopes],
        [[tab.url for tab in before.tabs if tab.scope_id == scope.id] for scope in before.scopes],
    ]
    if independent != expected:
        raise QueryError("JXA and AppleScript disagree on window IDs, titles, URLs, or order; retry the query.")
    return {
        "verified": True,
        "methods": ["JXA", "AppleScript"],
        "matched": ["window_ids", "titles", "urls", "order"],
        "windows": len(before.scopes),
        "tabs": len(before.tabs),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_ms": round((perf_counter() - started) * 1000, 2),
        "limitations": "Checks open-window observations only; not saved groups, remote devices, or atomicity.",
    }

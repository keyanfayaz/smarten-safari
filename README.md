# Safari Tabs Lab

A small, read-only CLI for experimenting with ways to query Safari tab titles and URLs.
Python 3.10+, no runtime dependencies. Run directly from this directory without installing anything.

For read-only MCP tools, an installable local plugin, and the private ChatGPT tunnel setup,
see [MCP and plugin setup](docs/MCP.md).

```sh
python3 -m safari_tabs windows
python3 -m safari_tabs tabs --source windows
python3 -m safari_tabs tabs --source windows --window-id 42 --format titles
python3 -m safari_tabs verify

python3 -m safari_tabs groups
python3 -m safari_tabs tabs --source groups --group 'Work' --format titles
python3 -m safari_tabs tabs --source groups --group-id 123 --search github

python3 -m safari_tabs devices
python3 -m safari_tabs tabs --source icloud
python3 -m safari_tabs tabs --source icloud --device 'My iPhone'
python3 -m safari_tabs tabs --source icloud --device-id DEVICE_UUID --format urls
```

Use `windows`, `groups`, and `devices` to discover actual IDs and names before filtering.
Names match exactly and may select multiple scopes; IDs disambiguate duplicate names.
`--search` is a case-insensitive substring match over titles and URLs.
The default source for `tabs` is `windows`; source-specific filters require their matching `--source`.

## Methods

| Source | Method | What it can tell you |
| --- | --- | --- |
| `windows` | JXA through `osascript`, using Safari's Apple Events dictionary | Tabs exposed by each currently open window's selected group |
| `groups` | Read-only SQLite query of `SafariTabs.db` | Stored tab containers and their direct tab children, including inactive named groups |
| `icloud` | Read-only SQLite query of `CloudTabs.db` | Cached tabs by synced device ID/name |

The windows adapter makes one subprocess call and bulk-reads titles and URLs per window.
It requires two consecutive matching observations within at most three samples, under a 30-second
process timeout; count changes, navigation, or reordering must settle before a result is returned.
It does not activate Safari, navigate tabs, or launch Safari if it is not running.
This detects observed instability but does not make Safari's scripting interface transactional.
Safari changes during collection can produce an error; retry when needed.
Window tab IDs are `window-id:position` and change when tabs are reordered.

`verify` cross-checks window IDs, titles, URLs, and order using an independent AppleScript query between
two JXA reads. It fails if the observations change or disagree, and reports counts and timing without
printing titles or URLs. It does not validate saved groups or iCloud data.
See [live experiment results](docs/experiments.md) for what has actually been verified.

The database adapters use a read transaction and `mode=ro`; they do not execute writes or create
missing databases. They read committed WAL data rather than using `immutable=1`, which can miss
recent changes. SQLite may still need access to its WAL/shared-memory sidecar files.

The groups adapter is deliberately experimental: it treats `bookmarks.type = 1` rows as containers
and associates tabs with their direct parent. Internal folders and profile containers may appear
alongside named groups. Nested/pinned containers are separate scopes, not merged into their ancestors.
It excludes deleted/closed records and descendants when those state columns exist, and warns if
they do not. The supported ancestry layout terminates at parent `0` or `NULL`; cycles and orphaned
containers are excluded. Safari's undocumented schema can change, so inspect it before extending
the mapping. This is not a guaranteed complete inventory of every Safari profile or private tab.

iCloud results describe a local sync cache, not the current state of a remote device. Named groups
sync across devices and are not assigned to a device here. Remote window membership is not inferred.
The CLI does not deduplicate records across sources: matching URLs are not proof of identical tabs.

## Device discovery

No device registration or configured device list is needed. Each iCloud query discovers all device
records in the selected local cache, including devices with no cached tabs. New device records appear
on the next query after Safari syncs them. Device names in examples are optional filters, not setup.
Omit `--device` and `--device-id` to query tabs across all discovered devices; use a discovered ID when
names are duplicated or change.

This inventory covers the selected Safari cache, not every device associated with an Apple Account.
Safari must be enabled in iCloud on devices using the same Apple Account, and results depend on what
has synced to this Mac. Safari's Start Page also limits iCloud Tabs to the current profile; the adapter
does not claim complete coverage across profiles. See Apple's [Safari sync setup](https://support.apple.com/guide/icloud/set-up-safari-mm5400ef10c4/icloud)
and [profile behavior](https://support.apple.com/en-ie/105100).

The CLI returns the full discovered inventory. MCP returns bounded pages with `total_matching` and
`next_offset`; a first page is not necessarily the entire inventory. See [MCP usage](docs/MCP.md).

Database paths are resolved relative to the current user's home directory. Device names and IDs come
from runtime data; credentials and tunnel/account configuration belong outside the repository and
the distributable plugin. Fixtures use synthetic data. The package's author and repository metadata
identify the project, not the account or devices it queries.

## Output

JSON is the default. It includes `source`, `collected_at` (UTC collection time, not sync freshness),
`elapsed_ms` (adapter time), `warnings`, and `scopes`; the `tabs` command also includes `tabs`.
Each tab has an `id`, `scope_id`, `title`, `url`, and optional `position` value.
IDs are strings and meaningful only within their source/database. Position values follow each source's
convention; windows use one-based indices. Titles and URLs can be null.

```json
{
  "source": "groups",
  "scopes": [{"id": "12", "name": "Work", "kind": "group", "tab_count": 1}],
  "tabs": [{"id": "34", "scope_id": "12", "title": "Example", "url": "https://example.test", "position": 0}],
  "warnings": ["Experimental private schema; see actual command output for details."],
  "collected_at": "2026-01-01T00:00:00+00:00",
  "elapsed_ms": 2.5
}
```

Inventory commands include empty scopes and omit tab contents. On filtered tab queries, counts
refer to matching tabs. `--format titles` and `--format urls` print one item per line, replace embedded
newlines with spaces, and send warnings to stderr; JSON preserves original text. No matches is a
successful empty result. Source failures return status 1; invalid arguments return status 2.

## Access and local experiments

Live window queries require macOS and may trigger the system Automation permission prompt for Safari.
They do not require Safari's **Allow JavaScript from Apple Events** setting because the script does not
execute JavaScript inside web pages. Database queries can run on other operating systems with a suitable
SQLite snapshot.

Safari database access may require **System Settings > Privacy & Security > Full Disk Access** for
the terminal or app running Python, followed by restarting that app. An unreadable database produces
an error rather than a misleading empty list. Administrator privileges alone may not grant this access.

The default database locations, tried in order, are:

```text
~/Library/Containers/com.apple.Safari/Data/Library/Safari/
~/Library/Safari/
```

Override the file for a profile, fixture, or consistent SQLite backup:

```sh
python3 -m safari_tabs schema --source groups
python3 -m safari_tabs schema --source groups --db /path/to/SafariTabs.db
python3 -m safari_tabs tabs --source groups --db /path/to/SafariTabs.db
```

The `schema` command returns table definitions, not tab data. To copy a live SQLite store for experiments,
use SQLite's backup API or `.backup` command; copying only the `.db` file can lose committed WAL changes.
Keep personal exports under the gitignored `exports/` directory. Database files and sidecars are also
gitignored. Fixtures in this repository are synthetic and use `example.test` URLs.

## Development

```sh
python3 -m unittest discover -s tests -v
```

Tests run offline on synthetic SQLite stores, including a live WAL transaction, and mock the macOS
automation boundary. On macOS, tests also execute the real JXA script with a fake Application object
to exercise stable/unstable observations without contacting Safari. They cover lifecycle filtering,
empty groups/devices, duplicate names, malformed schemas, Unicode, filters, verification failures,
and the CLI entrypoint. They never query your browsing session.
GitHub Actions runs Python 3.10 and 3.14 on Linux, plus Python 3.14 on macOS for the JXA tests.

To add another collection method:

1. Add a module under `safari_tabs/adapters/` with `read()` returning `model.Snapshot`.
2. Register it in `cli.ADAPTERS` and add the relevant CLI arguments/inventory mapping.
3. Test against synthetic fixtures or a mocked system boundary; document what its IDs and freshness mean.

The adapters are ordinary Python functions and can also be called directly:

```python
from safari_tabs.adapters import groups

snapshot = groups.read('/path/to/SafariTabs.db')
work = {scope.id for scope in snapshot.scopes if scope.name == 'Work'}
titles = [tab.title for tab in snapshot.tabs if tab.scope_id in work]
```

Optional installation into a virtual environment provides the `safari-tabs` command:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/safari-tabs --help
```

Only optional packaging needs setuptools; running the module and tests needs the standard library alone.

## References

- Safari's installed scripting dictionary: `/Applications/Safari.app/Contents/Resources/Safari.sdef`.
- [safaricloudtabs](https://github.com/shokk/homebrew-safaricloudtabs): observed parent/child storage for groups.
- [iLEAPP Safari parser](https://github.com/abrignoni/iLEAPP/blob/main/scripts/artifacts/safariTabs.py): observed lifecycle columns and device/tab relationships.
- [Apple's iCloud Tabs guide](https://support.apple.com/en-us/108409): sync requirements and user-facing behavior.

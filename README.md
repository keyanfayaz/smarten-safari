# Smarten for Safari

*Your apps, connected to AI.*

A lightweight, read-only CLI and MCP server for querying Safari tab names and URLs across live Mac
windows, saved tab groups, stored profiles, and the local iCloud Tabs cache.
Python 3.10+, no runtime dependencies, no configured device list. Run directly from this directory.

Use it from a terminal, an installable local plugin, or a private ChatGPT connection through a Secure
MCP Tunnel. The readers have been exercised against a live Safari installation and through ChatGPT;
the database adapters remain experimental because Safari's private schema can change.

[MCP and plugin setup](docs/MCP.md) · [Validation evidence](docs/experiments.md) · [Remaining work](docs/ROADMAP.md)

## The Smarten family

Smarten for Safari is part of **Smarten**, alongside
[Smarten for Things](https://github.com/keyanfayaz/smarten-things).

The `safari_tabs` Python module, `safari-tabs` / `safari-tabs-mcp` command aliases,
plugin ID `safari-tabs`, and marketplace ID `safari-local` remain available for
existing configurations.
MCP discovery advertises the new display title while retaining its existing
server and tool identifiers. An existing hosted connection must be renamed in
its owning client; updating this repository does not change account-level names.

## Coverage and limitations

| Source | What you can query | What it does not establish |
| --- | --- | --- |
| `windows` | Live window IDs and each window's selected-group tabs: names, URLs, and order | Inactive groups, or a reliable mapping of live windows to named groups/profiles |
| `groups` | Saved named groups, including inactive groups, their tabs, and stored profile assignments | Which device has a group open, complete profile/group-specific pinned-tab coverage, or compatibility with every Safari schema |
| `profiles` | Stored profile IDs/names, named-group tabs, and filtering by profile | Every default/ungrouped or pinned tab belonging to a profile |
| `session` | Stored window UUIDs, active group/profile relationships, privacy flags, and tabs | Live freshness or a mapping from stored window IDs to live Apple Events window IDs |
| `icloud` | Automatically discovered device IDs/names/types and their cached tab names/URLs | Remote window boundaries, profile/group membership, exact sync freshness, or every Apple Account device |

- **iCloud means device → cached tabs**, not device → profile → window/group → tabs.
- **Groups and profiles describe this Mac's stored catalog**, which may contain synced groups; groups are not assigned to remote devices here.
- **Sources overlap:** profile counts reuse named-group tabs, and local windows can also appear in the iCloud cache; do not sum counts into a unique total.
- **Collection time is not sync time:** a read now does not prove a remote device synced now, and stored session records can lag live Safari.
- **Private browsing is not excluded:** local readers may return private tabs; do not rely on this tool to filter them out.

Run `doctor` or the MCP `get_safari_coverage` tool to check availability in the current host.
"Available" means the read succeeded, not that every capability above is complete.

## Quick start

Live queries require macOS with Safari and Python 3.10+. Cloning requires repository access while
this repository is private. No `pip install` is needed:

```sh
git clone https://github.com/keyanfayaz/smarten-safari.git
cd smarten-safari
python3 -m safari_tabs doctor
python3 -m safari_tabs windows
python3 -m safari_tabs tabs --source windows --format titles
python3 -m safari_tabs verify
```

The first live-window query may prompt for Safari Automation access. Database readers may require
Full Disk Access for the app running the command; see [access and local experiments](#access-and-local-experiments).
An unavailable source is an error, not a claim that no tabs exist; other readers can still work.

**URL defaults differ by interface:** CLI JSON includes URLs; use `--format titles` for names only.
MCP omits URLs unless `include_urls: true`. Neither interface navigates, opens, moves, or closes tabs.

## Query examples

```sh
python3 -m safari_tabs tabs --source windows --window-id WINDOW_ID --format titles

python3 -m safari_tabs groups
python3 -m safari_tabs tabs --source groups --group 'Work' --format titles
python3 -m safari_tabs tabs --source groups --group-id GROUP_ID --search github
python3 -m safari_tabs profiles
python3 -m safari_tabs tabs --source groups --group 'Tools' --profile-id PROFILE_ID
python3 -m safari_tabs session
python3 -m safari_tabs tabs --source session --stored-window-id STORED_WINDOW_ID

python3 -m safari_tabs devices
python3 -m safari_tabs tabs --source icloud
python3 -m safari_tabs tabs --source icloud --device 'My iPhone'
python3 -m safari_tabs tabs --source icloud --device-id DEVICE_UUID --format urls
```

Use `windows`, `groups`, `devices`, `profiles`, and `session` to discover actual IDs and names before
filtering; replace uppercase placeholders with returned IDs. Example names are illustrative filters.
Names match exactly and may select multiple scopes; IDs disambiguate duplicate names.
`--search` is a case-insensitive substring match over titles and URLs.
The default source for `tabs` is `windows`; source-specific filters require their matching `--source`.

## MCP and ChatGPT

| Tool | Purpose |
| --- | --- |
| `list_safari_scopes` | Discover windows, groups, devices, profiles, or stored windows with tab counts |
| `read_safari_tabs` | Read/search tab names with exact scope and profile filters; URLs are opt-in |
| `verify_safari_windows` | Compare live window observations through independent JXA and AppleScript reads |
| `get_safari_coverage` | Report source availability, counts, errors, and limits without returning browsing records |

All five sources are selectable through the list/read tools. Results default to 20 records and are
capped at 50 per page; follow `next_offset` until `null` when requesting a complete inventory.

For example, call `list_safari_scopes` with `{"source":"icloud"}`, then `read_safari_tabs` with
`{"source":"icloud","scope_id":"RETURNED_DEVICE_ID","limit":20}`.

See [MCP and plugin setup](docs/MCP.md) for stdio, portable local packaging, and the private ChatGPT
tunnel. A local plugin alone does not provide web/mobile access: the Safari-hosting Mac and tunnel
must be running. Automatic startup is a separate setup step, not installed by the package.

## How the readers work

`windows` uses JXA through `osascript` and Safari's Apple Events dictionary. `groups`, `profiles`, and
`session` read `SafariTabs.db`; `icloud` reads `CloudTabs.db`.

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

The groups adapter recognizes the observed profiled layout: visible subtype-0 folders under the root
or a subtype-2 profile are named groups. Recovered, hidden, device, and auxiliary containers are
excluded from the inventory. Auxiliary child-container tabs are included with an ordering warning
if present. `DefaultProfile` identifies the default profile, whose unnamed stored title is displayed
as "Default profile". Reduced schemas retain the older experimental container output with warnings.
Deleted/closed records, invalid ancestors, cycles, and orphans are excluded where the schema permits.
Safari's undocumented schema can change; field compatibility alone does not establish completeness.

The `session` source follows `windows.active_tab_group_id` and `active_profile_id` directly.
Its IDs are SQLite window IDs, distinct from live Apple Events IDs; it also returns stored window UUIDs.
These persisted records can lag live Safari, including titles and private-tab URLs. Use `windows`
for current observations. Default-profile global pinned tabs are included per stored window;
profile/group-specific pin layouts are not fully established. A stored relationship is never inferred
from matching titles or URLs. Profile tab counts cover named groups; session tabs are a separate view.
The profiled reader retains Start Page tabs even when their URL is empty.

iCloud results describe a local sync cache, not the current state of a remote device. Named groups
sync across devices and are not assigned to a device here. Remote window membership is not inferred.
Device type identifiers help distinguish devices with the same name. The reader supports numeric
ordering ranks and the observed single-component zlib/JSON `sortValues` format; unknown or composite
ranks become `null` and use stable ID order with a warning. Binary data is never emitted into JSON.
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
Each tab has an `id`, `scope_id`, `title`, `url`, and optional `position`, `group_id`, and `pinned` values.
Scopes may include source-specific profile, group, device-type, privacy, and stored-window UUID fields.
Profiled database results include a `context` with profile identifiers and names.
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

Run `python3 -m safari_tabs doctor` to check all five sources in the current process context.
It returns counts, availability, error codes, and coverage limits without printing browsing records.
It exits with status 1 if any source is unavailable, while preserving the other sources' results.
An available source means the reader succeeded; it does not establish complete coverage.

File errors distinguish `permission_denied`, `database_missing`, `unsupported_schema`, and
`database_unavailable`. On Python 3.11+, SQLite can also identify `database_busy` and `invalid_database`.
An unstable live window read reports `unstable_session`; retry after Safari stops changing.

Check permissions in the actual host that will run the reader. A terminal, coding app, and detached
tunnel runtime can have different macOS grants. Full Disk Access is broader than Safari access;
the software does not change it automatically. After an intentional permission change, rerun
`doctor` in both the CLI host and the MCP runtime before claiming database support works.
See [remaining implementation and validation work](docs/ROADMAP.md).

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
2. Register it in `cli.ADAPTERS`, add relevant CLI inventory/filter mappings, and register it in `mcp.ADAPTERS` if exposing it through MCP.
3. Add its limits to `coverage.LIMITATIONS` and test against synthetic fixtures or a mocked system boundary; document what its IDs and freshness mean.

The adapters are ordinary Python functions and can also be called directly:

```python
from safari_tabs.adapters import groups

snapshot = groups.read('/path/to/SafariTabs.db')
work = {scope.id for scope in snapshot.scopes if scope.name == 'Work'}
titles = [tab.title for tab in snapshot.tabs if tab.scope_id in work]
```

Optional installation into a virtual environment provides the `smarten-safari` command:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/smarten-safari --help
```

Only optional packaging needs setuptools; running the module and tests needs the standard library alone.

## References

- Safari's installed scripting dictionary: `/Applications/Safari.app/Contents/Resources/Safari.sdef`.
- [safaricloudtabs](https://github.com/shokk/homebrew-safaricloudtabs): observed parent/child storage for groups.
- [iLEAPP Safari parser](https://github.com/abrignoni/iLEAPP/blob/main/scripts/artifacts/safariTabs.py): observed lifecycle columns and device/tab relationships.
- [Apple's iCloud Tabs guide](https://support.apple.com/en-us/108409): sync requirements and user-facing behavior.

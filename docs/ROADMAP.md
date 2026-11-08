# Remaining capability work

The target is read-only queries for local windows, named tab groups, and tabs synced from other
devices, with automatic discovery and portable configuration. The project remains dependency-free
at runtime. Synthetic tests establish adapter behavior, not coverage of a live Safari installation.

| Capability | Current evidence | Required completion check |
| --- | --- | --- |
| Local window tab names and optional URLs | Live CLI and ChatGPT reads; independent JXA/AppleScript agreement | Keep both checks passing after releases |
| Search, filters, and bounded MCP pages | Live window/group/device checks and offline tests | Keep representative host queries passing after releases |
| Availability and meaningful errors | CLI doctor and MCP coverage check | Run from each installed host, since permissions differ |
| Named groups and inactive group tabs | Live profiled classification; default-profile sidebar counts and an inactive group's titles matched | Broaden representative checks to other Safari versions and auxiliary pin layouts |
| Group-to-window association | Implemented from stored window/group/profile keys through the session source | A separate authoritative live Apple Events ID to stored UUID bridge remains unresolved; stored titles/URLs can lag |
| Synced device discovery and tabs | Live device inventory and JSON-safe tab queries; automatic discovery fixtures | Continue checking sync freshness and unsupported ordering formats; retain device IDs for duplicate names |
| Safari profiles | Four stored profiles discovered; named-group profile filters implemented | Profile-specific pinned/default-device containers are not completely mapped |
| Persistence across login | Tunnel currently runs as a managed process | Install automatic startup only with explicit user authorization, then test restart behavior |

## Next validation sequence

1. Keep `doctor` and representative queries passing from both the CLI and installed ChatGPT connection.
2. Validate profile-specific pins and default-device containers against Safari before extending classification.
3. Establish an authoritative live-window identity bridge before equating stored windows with Apple Events IDs.
4. Test other Safari schemas with synthetic regression fixtures; keep personal browsing records out of source control.
5. Refresh host tool discovery whenever the MCP schema changes, then repeat representative queries through ChatGPT.

## Limits to preserve

- iCloud results describe a synced cache, with unknown freshness unless a verified timestamp is available.
- A Mac cannot guarantee an inventory of every Apple Account device from the local Safari cache alone.
- Remote window boundaries are not currently available; do not infer them from titles or matching URLs.
- Window-index IDs can change on reordering, and pages from separate observations can shift.
- Full Disk Access grants broad OS access even though these tools query only Safari; no automatic grants or permission workarounds are implemented.
- The CLI and MCP readers must fail visibly on inaccessible data or incompatible schemas.
- Do not publish real device names, browsing records, home paths, credentials, or tunnel configuration in the repository or package.

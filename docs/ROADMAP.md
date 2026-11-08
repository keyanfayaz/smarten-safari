# Remaining capability work

The target is read-only queries for local windows, named tab groups, and tabs synced from other
devices, with automatic discovery and portable configuration. The project remains dependency-free
at runtime. Synthetic tests establish adapter behavior, not coverage of a live Safari installation.

| Capability | Current evidence | Required completion check |
| --- | --- | --- |
| Local window tab names and optional URLs | Live CLI and ChatGPT reads; independent JXA/AppleScript agreement | Keep both checks passing after releases |
| Search, filters, and bounded MCP pages | Live window checks and offline tests | Exercise real group/device collections after access is available |
| Availability and meaningful errors | CLI doctor and MCP coverage check | Run from each installed host, since permissions differ |
| Named groups and inactive group tabs | Fixture-tested container adapter; separate UI observations | Inspect live schema, distinguish named groups from internal containers, compare representative empty/nonempty/inactive groups with Safari |
| Group-to-window association | Not implemented | Identify stored stable keys or an authorized read-only UI interface; verify mappings against live windows, including duplicate group names and pinned tabs |
| Synced device discovery and tabs | Fixture-tested cache adapter, including additions and pagination | Compare live discovered devices and tab titles with Safari's iCloud view; retain IDs for duplicate names |
| Safari profiles | Not established | Discover profile metadata from observed storage, preserve profile identity in results and filters, verify across profiles |
| Persistence across login | Tunnel currently runs as a managed process | Install automatic startup only with explicit user authorization, then test restart behavior |

## Next validation sequence

1. Obtain the intended macOS file-access grant for the coding host, with the user's consent.
2. Run `doctor`, then `schema --source groups` and `schema --source icloud`; inspect definitions before interpreting additional fields.
3. Correct adapters against the observed schemas and add synthetic regression fixtures without personal browsing records.
4. Compare group/device results with Safari's normal interface without opening, closing, or moving tabs.
5. Implement group/window/profile relationships only where an observed key or interface supports them; report unknown/ambiguous relationships explicitly.
6. Build and install the versioned package, verify the tunnel runtime's own access, refresh host tool discovery, and repeat representative queries through ChatGPT.

## Limits to preserve

- iCloud results describe a synced cache, with unknown freshness unless a verified timestamp is available.
- A Mac cannot guarantee an inventory of every Apple Account device from the local Safari cache alone.
- Remote window boundaries are not currently available; do not infer them from titles or matching URLs.
- Window-index IDs can change on reordering, and pages from separate observations can shift.
- Full Disk Access grants broad OS access even though these tools query only Safari; no automatic grants or permission workarounds are implemented.
- The CLI and MCP readers must fail visibly on inaccessible data or incompatible schemas.
- Do not publish real device names, browsing records, home paths, credentials, or tunnel configuration in the repository or package.

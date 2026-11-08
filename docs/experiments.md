# Live collection experiments

Validated on Safari 27.0.1 on macOS, November 7, 2026 (Pacific time).
Only counts and method notes are recorded here; no real titles, URLs, database files, or exports are committed.

| Method | Observed result | Status |
| --- | --- | --- |
| JXA / Safari Apple Events | Three consecutive observations matched: 4 windows and 28 tabs | Live verified |
| Independent AppleScript | Every title matched the JXA observations | Live verified |
| `python3 -m safari_tabs verify` | Window IDs, titles, URLs, and order matched; 4 windows / 28 tabs in about 1.4 seconds | Live verified |
| CLI window-ID + title search | Returned the expected single title from a chosen window | Live verified |
| Safari accessibility sidebar | Read all 8 tab names in an inactive named group without selecting it | UI experiment only; not implemented as a CLI adapter |
| Safari iCloud Tabs popover | Read tab titles under synced phone and tablet headings | UI sample only; not a complete device inventory or CLI adapter |
| `SafariTabs.db` and `CloudTabs.db` | Raw read attempts returned macOS `EPERM`, including outside the command sandbox | Live database validation blocked by access permissions |

## Repeating the window check

```sh
python3 -m safari_tabs verify
python3 -m safari_tabs windows
python3 -m safari_tabs tabs --source windows --window-id WINDOW_ID --format titles
```

Run from a terminal or host app authorized to automate Safari. Sandboxed execution can report
“Application can't be found” even with Safari installed; that differs from database file permissions.
The verification result represents the session at collection time, not a lasting guarantee.

## Inactive groups through the sidebar

This fallback uses Safari's normal accessibility interface; it does not read protected database files.

1. Note the selected group/tab and whether the sidebar is visible.
2. Show the sidebar if necessary.
3. Expand an inactive group's disclosure control using its accessibility **Expand** action; do not select the group or a tab.
4. Read the child rows' names/descriptions; some tab names occur only in the accessibility description.
5. Collapse that group and restore the sidebar to its original state.

In the live experiment the original selected group and tab remained selected, and the expanded group
and sidebar were restored. No tabs were opened, closed, moved, or navigated by these queries.

This establishes that inactive group titles can be obtained through the UI. It does not establish a
reliable CLI adapter, complete coverage of other profiles, or URL availability from those rows.
Accessibility IDs and layout can change between observations; reacquire them after each UI action.

## Database validation after permission grant

On November 8, 2026, the user approved ChatGPT Full Disk Access and authenticated in System Settings.
Both the coding host and existing private tunnel could then read the two Safari databases.
No database writes, protected-file copies through alternate processes, or broad filesystem scans were used.

| Check | Observation |
| --- | --- |
| Raw container inventory | 116 containers / 491 nonempty-URL tab records; includes internal records and is not a named-group count |
| Profiled classification | 39 named groups / 459 tabs across 4 stored profiles, including 10 Start Page tabs with empty URLs |
| Default-profile sidebar | All 20 visible named-group counts agreed with the classified database records |
| Inactive-group title check | All 8 titles and their order matched the sidebar; group and sidebar restored afterward |
| Synced devices | 6 device records / 329 cached tabs at observation time, including the current Mac and two same-name phones |
| iCloud serialization | Actual position fields were zlib-compressed JSON, requiring rank decoding before JSON output |
| Stored session | 4 stored window records / 30 tab entries; explicit group/profile links were readable |
| Stored versus live windows | The three normal windows had matching URL multisets but one stale title each; the private window's stored URLs differed |
| Installed MCP 0.4.1 | All five sources available; four tools advertised; actual ChatGPT queries returned group/device titles and profile/session inventories |
| Live-window verification | JXA and independent AppleScript agreed on 4 windows / 30 tabs; one initial tunnel call timed out, and the sequential retry succeeded |

The stored-window observations establish persistence relationships, not live identity or freshness.
The snapshot is not a completeness guarantee for every device, profile-specific pin layout, or Safari version.
All committed regression fixtures remain synthetic.

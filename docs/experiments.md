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

## Database access remains separate

The database adapters have fixture tests, not live validation on this machine. Full Disk Access for
the host application may be required; ordinary unsandboxed execution did not resolve `EPERM`.
No permissions were changed, and no protected data was copied through an alternate process.

After the user grants access, inspect the actual schema first, then compare one named group's results
against Safari's sidebar before trusting the experimental parent/child mapping more broadly.

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from safari_tabs.adapters import groups, icloud, windows
from safari_tabs.model import QueryError


class SQLiteAdaptersTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "fixture.db"

    def test_groups_exclude_closed_deleted_orphaned_and_cyclic_records(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TABLE bookmarks (
                id INTEGER PRIMARY KEY, parent INTEGER, type INTEGER, title TEXT,
                url TEXT, deleted INTEGER, date_closed REAL, order_index INTEGER
            )""")
            db.executemany("INSERT INTO bookmarks VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
                (1, 0, 1, "Root", None, 0, None, 0),
                (2, 1, 1, "Work", None, 0, None, 0),
                (3, 1, 1, "Work", None, 0, 0, 1),
                (4, 1, 1, "Empty", None, None, None, 2),
                (5, 1, 1, "Deleted group", None, 1, None, 3),
                (6, 1, 1, "Closed group", None, 0, 123, 4),
                (7, 5, 1, "Nested under deleted", None, 0, None, 0),
                (8, 9, 1, "Cycle A", None, 0, None, 0),
                (9, 8, 1, "Cycle B", None, 0, None, 0),
                (10, 2, 0, "Café\n\"quoted\"", "https://example.test/a", 0, None, 1),
                (11, 2, 0, None, "about:blank", None, 0, 0),
                (12, 3, 0, "Other work", "https://example.test/b", 0, None, 0),
                (13, 2, 0, "Deleted", "https://example.test", 1, None, 2),
                (14, 2, 0, "Closed", "https://example.test", 0, 123, 3),
                (15, 2, 0, "No URL", None, 0, None, 4),
                (16, 5, 0, "Deleted parent", "https://example.test", 0, None, 0),
                (17, 7, 0, "Deleted ancestor", "https://example.test", 0, None, 0),
                (18, 6, 0, "Closed parent", "https://example.test", 0, None, 0),
                (19, 8, 0, "Cycle", "https://example.test", 0, None, 0),
                (20, 999, 0, "Orphan", "https://example.test", 0, None, 0),
                (21, 2, 0, "Whitespace URL", "  ", 0, None, 0),
            ])
        snapshot = groups.read(self.path)
        self.assertEqual([tab.id for tab in snapshot.tabs], ["11", "12", "10"])
        self.assertEqual({scope.id for scope in snapshot.scopes}, {"1", "2", "3", "4"})
        self.assertEqual(sum(scope.name == "Work" for scope in snapshot.scopes), 2)
        self.assertEqual(snapshot.tabs[2].title, 'Café\n"quoted"')

    def test_reduced_schema_reports_missing_lifecycle_columns(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE bookmarks (id INTEGER, parent INTEGER, type INTEGER, title TEXT, url TEXT)")
            db.execute("INSERT INTO bookmarks VALUES (1, 0, 1, 'Empty', NULL)")
        snapshot = groups.read(self.path)
        self.assertEqual(len(snapshot.scopes), 1)
        self.assertTrue(any("deleted column" in warning for warning in snapshot.warnings))
        self.assertTrue(any("date_closed column" in warning for warning in snapshot.warnings))

    def test_unknown_schema_fails_instead_of_reporting_no_tabs(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE bookmarks (id INTEGER)")
        with self.assertRaisesRegex(QueryError, "Unsupported schema"):
            groups.read(self.path)

    def test_devices_preserve_empty_devices_duplicate_names_and_orphans(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE cloud_tab_devices (device_uuid TEXT, device_name TEXT)")
            db.execute("CREATE TABLE cloud_tabs (tab_uuid TEXT, device_uuid TEXT, title TEXT, url TEXT, position INTEGER)")
            db.executemany("INSERT INTO cloud_tab_devices VALUES (?, ?)", [("a", "Phone"), ("b", "Phone")])
            db.executemany("INSERT INTO cloud_tabs VALUES (?, ?, ?, ?, ?)", [
                ("t2", "a", "Second", "https://example.test/2", 2),
                ("t1", "a", "First", "https://example.test/1", 1),
                ("t3", "missing", None, None, 0),
            ])
        snapshot = icloud.read(self.path)
        self.assertEqual([tab.id for tab in snapshot.tabs], ["t1", "t2", "t3"])
        self.assertEqual({scope.id for scope in snapshot.scopes}, {"a", "b", "missing"})
        self.assertTrue(any("metadata missing" in warning for warning in snapshot.warnings))

    def test_devices_support_schema_without_position(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE cloud_tab_devices (device_uuid TEXT, device_name TEXT)")
            db.execute("CREATE TABLE cloud_tabs (tab_uuid TEXT, device_uuid TEXT, title TEXT, url TEXT)")
            db.execute("INSERT INTO cloud_tabs VALUES ('t', 'd', 'Title', 'https://example.test')")
        self.assertIsNone(icloud.read(self.path).tabs[0].position)


@patch("safari_tabs.adapters.windows.sys.platform", "darwin")
class WindowsTests(unittest.TestCase):
    @patch("safari_tabs.adapters.windows.subprocess.run")
    def test_json_preserves_unicode_quotes_and_newlines(self, run):
        run.return_value.stdout = json.dumps({
            "scopes": [{"id": "42", "name": "Window 42", "kind": "window"}],
            "tabs": [{"id": "42:1", "scope_id": "42", "title": 'Café\n"title"',
                      "url": "https://example.test/?a=1&b=2", "position": 1}],
        })
        snapshot = windows.read()
        self.assertEqual(snapshot.tabs[0].title, 'Café\n"title"')
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.kwargs["timeout"], 30)

    @patch("safari_tabs.adapters.windows.subprocess.run")
    def test_empty_session(self, run):
        run.return_value.stdout = '{"scopes": [], "tabs": []}'
        self.assertEqual(windows.read().tabs, [])

    @patch("safari_tabs.adapters.windows.subprocess.run")
    def test_invalid_response(self, run):
        for response in ("bad json", "{}", "null", '{"scopes": null, "tabs": []}'):
            with self.subTest(response=response):
                run.return_value.stdout = response
                with self.assertRaisesRegex(QueryError, "unexpected response"):
                    windows.read()

    @patch("safari_tabs.adapters.windows.subprocess.run")
    def test_changing_session_has_distinct_retryable_error(self, run):
        run.side_effect = subprocess.CalledProcessError(
            1, "osascript", stderr="Error: Safari tabs changed during collection; retry the query.")
        with self.assertRaises(QueryError) as caught:
            windows.read()
        self.assertEqual(caught.exception.code, "unstable_session")
        self.assertNotIn("permission", str(caught.exception).lower())

    @patch("safari_tabs.adapters.windows.subprocess.run")
    def test_timeout(self, run):
        run.side_effect = subprocess.TimeoutExpired("osascript", 30)
        with self.assertRaisesRegex(QueryError, "30 seconds"):
            windows.read()

    @patch("safari_tabs.adapters.windows.subprocess.run")
    def test_permission_denied(self, run):
        run.side_effect = subprocess.CalledProcessError(1, "osascript", stderr="Not authorized (-1743)")
        with self.assertRaisesRegex(QueryError, "Automation.*Not authorized"):
            windows.read()

    def test_non_macos_error(self):
        with patch("safari_tabs.adapters.windows.sys.platform", "linux"):
            with self.assertRaisesRegex(QueryError, "requires macOS"):
                windows.read()

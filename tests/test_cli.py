from contextlib import closing, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from safari_tabs.cli import main
from safari_tabs.model import QueryError, Scope, Snapshot, Tab


class CLITests(unittest.TestCase):
    def call(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def snapshot(self):
        return Snapshot("groups", [Scope("1", "Work", "group"), Scope("2", "Work", "group"),
                                   Scope("3", "Empty", "group")], [
            Tab("a", "1", "Café\nDocs", "https://example.test/a"),
            Tab("b", "2", "Other", "https://example.test/b"),
        ], ["Fixture warning"])

    def test_filters_and_json_output(self):
        with patch.dict("safari_tabs.cli.ADAPTERS", {"groups": lambda path: self.snapshot()}):
            code, out, error = self.call("tabs", "--source", "groups", "--group", "Work",
                                         "--group-id", "1", "--search", "CAFÉ")
        result = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(error, "")
        self.assertEqual([tab["id"] for tab in result["tabs"]], ["a"])
        self.assertEqual(result["scopes"][0]["tab_count"], 1)
        self.assertIn("collected_at", result)
        self.assertIn("elapsed_ms", result)

    def test_duplicate_name_returns_both_scopes(self):
        with patch.dict("safari_tabs.cli.ADAPTERS", {"groups": lambda path: self.snapshot()}):
            _, out, _ = self.call("tabs", "--source", "groups", "--group", "Work")
        self.assertEqual(len(json.loads(out)["tabs"]), 2)

    def test_name_is_literal_and_no_match_is_success(self):
        with patch.dict("safari_tabs.cli.ADAPTERS", {"groups": lambda path: self.snapshot()}):
            code, out, _ = self.call("tabs", "--source", "groups", "--group", "' OR 1=1 --")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["tabs"], [])

    def test_inventory_includes_empty_scope_but_no_tabs(self):
        with patch.dict("safari_tabs.cli.ADAPTERS", {"groups": lambda path: self.snapshot()}):
            _, out, _ = self.call("groups")
        result = json.loads(out)
        self.assertNotIn("tabs", result)
        self.assertEqual(result["scopes"][2]["tab_count"], 0)

    def test_plain_titles_put_warnings_on_stderr(self):
        with patch.dict("safari_tabs.cli.ADAPTERS", {"groups": lambda path: self.snapshot()}):
            _, out, error = self.call("tabs", "--source", "groups", "--format", "titles")
        self.assertEqual(out, "Café Docs\nOther\n")
        self.assertIn("Fixture warning", error)

    def test_wrong_source_filters_and_database_fail_before_query(self):
        for args in (("--group", "Work"), ("--device", "Phone"), ("--db", "file.db")):
            with self.subTest(args=args), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main(["tabs", *args])
                self.assertEqual(error.exception.code, 2)

    def test_source_failure_is_not_empty_success(self):
        def fail():
            raise QueryError("Permission denied")
        with patch.dict("safari_tabs.cli.ADAPTERS", {"windows": fail}):
            code, out, error = self.call("tabs")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Permission denied", error)

    def test_module_entrypoint_reads_fixture_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.db"
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("CREATE TABLE cloud_tab_devices (device_uuid TEXT, device_name TEXT)")
                db.execute("CREATE TABLE cloud_tabs (tab_uuid TEXT, device_uuid TEXT, title TEXT, url TEXT)")
                db.execute("INSERT INTO cloud_tab_devices VALUES ('phone-1', 'Phone')")
                db.execute("INSERT INTO cloud_tabs VALUES ('tab-1', 'phone-1', 'Example', 'https://example.test')")
            completed = subprocess.run(
                [sys.executable, "-m", "safari_tabs", "tabs", "--source", "icloud", "--db", str(path),
                 "--device-id", "phone-1", "--format", "titles"],
                capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1], check=True,
            )
        self.assertEqual(completed.stdout, "Example\n")
        self.assertIn("local sync cache", completed.stderr)

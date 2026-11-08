from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from safari_tabs import mcp
from safari_tabs.model import QueryError, Scope, Snapshot, Tab


class MCPTests(unittest.TestCase):
    def snapshot(self):
        return Snapshot("windows", [Scope("1", "Work", "window"), Scope("2", "Work", "window")],
                        [Tab(str(i), "1" if i < 55 else "2", f"Café {i}", f"https://example.test/{i}", i)
                         for i in range(60)], ["Test warning"])

    def request(self, name, arguments=None):
        return mcp.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": name, "arguments": arguments or {}}})

    def test_discovery_never_reads_safari(self):
        with patch.dict(mcp.ADAPTERS, {"windows": lambda: self.fail("Unexpected read")}):
            initialized = mcp.dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                        "params": {"protocolVersion": "2025-06-18"}})
            listed = mcp.dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(initialized["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(len(listed["result"]["tools"]), 4)
        self.assertTrue(all(tool["annotations"]["readOnlyHint"] for tool in listed["result"]["tools"]))

    def test_notifications_never_read(self):
        with patch.dict(mcp.ADAPTERS, {"windows": lambda: self.fail("Unexpected read")}):
            self.assertIsNone(mcp.dispatch({"jsonrpc": "2.0", "method": "tools/call",
                                           "params": {"name": "read_safari_tabs"}}))

    def test_bounded_page_omits_urls_by_default(self):
        with patch.dict(mcp.ADAPTERS, {"windows": self.snapshot}):
            result = self.request("read_safari_tabs")["result"]
        data = result["structuredContent"]
        self.assertEqual(len(data["tabs"]), 20)
        self.assertEqual(data["next_offset"], 20)
        self.assertEqual(data["total_matching"], 60)
        self.assertNotIn("url", data["tabs"][0])
        self.assertEqual(json.loads(result["content"][0]["text"]), data)

    def test_filters_pagination_and_url_opt_in(self):
        with patch.dict(mcp.ADAPTERS, {"windows": self.snapshot}):
            result = self.request("read_safari_tabs", {"scope_id": "2", "search": "CAFÉ", "offset": 2,
                                                        "limit": 2, "include_urls": True})["result"]["structuredContent"]
        self.assertEqual([tab["id"] for tab in result["tabs"]], ["57", "58"])
        self.assertEqual(result["next_offset"], 4)
        self.assertTrue(all("url" in tab for tab in result["tabs"]))

    def test_inventory_has_no_tab_contents(self):
        with patch.dict(mcp.ADAPTERS, {"windows": self.snapshot}):
            data = self.request("list_safari_scopes")["result"]["structuredContent"]
        self.assertEqual([scope["tab_count"] for scope in data["scopes"]], [55, 5])
        self.assertNotIn("Café", json.dumps(data))

    def test_icloud_discovers_devices_across_pages_and_refreshes_without_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            cache = home / "Library/Safari/CloudTabs.db"
            cache.parent.mkdir(parents=True)
            devices = [(f"device-{i}", f"Device {i}") for i in range(61)]
            with closing(sqlite3.connect(cache)) as db, db:
                db.execute("CREATE TABLE cloud_tab_devices (device_uuid TEXT, device_name TEXT)")
                db.execute("CREATE TABLE cloud_tabs (tab_uuid TEXT, device_uuid TEXT, title TEXT, url TEXT)")
                db.executemany("INSERT INTO cloud_tab_devices VALUES (?, ?)", devices)
            with patch("safari_tabs.database.Path.home", return_value=home):
                found, offset = [], 0
                for _ in range(4):
                    page = self.request("list_safari_scopes", {"source": "icloud", "offset": offset})[
                        "result"]["structuredContent"]
                    self.assertEqual(page["total_matching"], 61)
                    self.assertLessEqual(len(page["scopes"]), 20)
                    found.extend(page["scopes"])
                    offset = page["next_offset"]
                    if offset is None:
                        break
                self.assertIsNone(offset)
                self.assertEqual(len(found), 61)
                self.assertEqual({scope["id"] for scope in found}, {device[0] for device in devices})
                self.assertTrue(all(scope["tab_count"] == 0 for scope in found))

                with closing(sqlite3.connect(cache)) as db, db:
                    db.execute("INSERT INTO cloud_tab_devices VALUES ('new-device', 'New device')")
                    db.execute("INSERT INTO cloud_tabs VALUES ('new-tab', 'new-device', 'Example', 'https://example.test')")
                refreshed = self.request("list_safari_scopes", {"source": "icloud", "offset": 60})[
                    "result"]["structuredContent"]
                self.assertEqual(refreshed["total_matching"], 62)
                self.assertIn({"id": "new-device", "name": "New device", "kind": "device", "tab_count": 1},
                              refreshed["scopes"])
                tabs = self.request("read_safari_tabs", {"source": "icloud"})["result"]["structuredContent"]
                self.assertEqual([(tab["scope_id"], tab["title"]) for tab in tabs["tabs"]],
                                 [("new-device", "Example")])

    def test_invalid_args_rejected_before_access(self):
        cases = [{"limit": 51}, {"limit": True}, {"offset": -1}, {"source": "private-files"},
                 {"db": "/private/file"}, {"command": "anything"}, {"scope_id": ""},
                 {"search": "a" * 257}, {"include_urls": "true"}, {"limit": 0}]
        with patch.dict(mcp.ADAPTERS, {"windows": lambda: self.fail("Unexpected read")}):
            for args in cases:
                with self.subTest(args=args):
                    self.assertEqual(self.request("read_safari_tabs", args)["error"]["code"], -32602)

    def test_source_failure_is_tool_error_not_empty_success(self):
        def fail():
            raise QueryError("Access denied")
        with patch.dict(mcp.ADAPTERS, {"windows": fail}):
            result = self.request("read_safari_tabs")["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["error"]["code"], "source_unavailable")

    def test_coverage_reports_partial_access(self):
        def denied():
            raise QueryError("Permission denied", "permission_denied")

        with patch.dict(mcp.ADAPTERS, {"windows": self.snapshot, "groups": denied, "icloud": denied}):
            result = self.request("get_safari_coverage")["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["status"], "partial")
        self.assertNotIn("Café", json.dumps(result))

    def test_protocol_errors(self):
        self.assertEqual(mcp.dispatch([])["error"]["code"], -32600)
        self.assertEqual(self.request("close_safari_tab")["error"]["code"], -32602)
        result = mcp.dispatch({"jsonrpc": "2.0", "id": True, "method": "ping"})
        self.assertEqual(result["error"]["code"], -32600)

    @patch("safari_tabs.mcp.verify", return_value={"verified": True, "tabs": 3})
    def test_verification_tool(self, verify):
        self.assertTrue(self.request("verify_safari_windows")["result"]["structuredContent"]["verified"])

    def test_stdio_protocol_and_parse_recovery(self):
        frames = ["bad json", json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
                  json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                  json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})]
        process = subprocess.run([sys.executable, "-B", "-m", "safari_tabs.mcp"],
                                 input="\n".join(frames) + "\n", capture_output=True, text=True,
                                 cwd=Path(__file__).resolve().parents[1], timeout=10, check=True)
        results = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["error"]["code"], -32700)
        self.assertEqual(len(results[2]["result"]["tools"]), 4)
        self.assertEqual(process.stderr, "")

    def test_oversized_frame_terminates_without_echo(self):
        process = subprocess.run([sys.executable, "-B", "-m", "safari_tabs.mcp"],
                                 input="x" * 65537, capture_output=True, text=True,
                                 cwd=Path(__file__).resolve().parents[1], timeout=10)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(process.stdout, "")

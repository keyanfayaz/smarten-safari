import json
import unittest

from safari_tabs.coverage import check
from safari_tabs.model import QueryError, Scope, Snapshot, Tab


class CoverageTests(unittest.TestCase):
    def test_partial_access_preserves_success_without_leaking_records(self):
        calls = []

        def windows():
            calls.append("windows")
            return Snapshot("windows", [Scope("PRIVATE_ID", "PRIVATE_NAME", "window")],
                            [Tab("PRIVATE_TAB_ID", "PRIVATE_ID", "PRIVATE_TITLE", "https://private.test")],
                            ["Private warning mentioning PRIVATE_ID"])

        def denied():
            calls.append("groups")
            raise QueryError("Permission denied", "permission_denied")

        def icloud():
            calls.append("icloud")
            return Snapshot("icloud")

        report = check({"windows": windows, "groups": denied, "icloud": icloud})
        self.assertEqual(calls, ["windows", "groups", "icloud"])
        self.assertEqual(report["status"], "partial")
        local, groups, remote = report["sources"]
        self.assertEqual((local["scope_count"], local["tab_count"]), (1, 1))
        self.assertEqual(groups["error"]["code"], "permission_denied")
        self.assertNotIn("tab_count", groups)
        self.assertEqual((remote["status"], remote["tab_count"]), ("available", 0))
        for value in ("PRIVATE_ID", "PRIVATE_NAME", "PRIVATE_TAB_ID", "PRIVATE_TITLE", "https://private.test"):
            self.assertNotIn(value, json.dumps(report))

    def test_successful_empty_sources_still_report_coverage_limits(self):
        report = check({source: lambda: Snapshot("test") for source in ("windows", "groups", "icloud")})
        self.assertEqual(report["status"], "available")
        self.assertTrue(all(source["limitations"] for source in report["sources"]))
        self.assertIn("not that every requested capability", report["limitations"][0])

    def test_all_sources_unavailable(self):
        def fail():
            raise QueryError("Missing schema", "unsupported_schema")

        report = check({"groups": fail, "icloud": fail})
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(all(source["error"]["code"] == "unsupported_schema" for source in report["sources"]))

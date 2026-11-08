from contextlib import redirect_stdout
import io
import json
import subprocess
import unittest
from unittest.mock import patch

from safari_tabs.cli import main
from safari_tabs.model import QueryError, Scope, Snapshot, Tab
from safari_tabs.verification import verify


class VerificationTests(unittest.TestCase):
    def snapshot(self, title="Example"):
        return Snapshot("windows", [Scope("42", "Window 42", "window")],
                        [Tab("42:1", "42", title, "https://example.test", 1)])

    @patch("safari_tabs.verification.subprocess.run")
    @patch("safari_tabs.verification.windows.read")
    def test_independent_match_reports_counts_without_tab_contents(self, read, run):
        read.return_value = self.snapshot()
        run.return_value.stdout = json.dumps([[42], [["Example"]], [["https://example.test"]]])
        result = verify()
        self.assertTrue(result["verified"])
        self.assertEqual(result["tabs"], 1)
        self.assertNotIn("https://example.test", json.dumps(result))

    @patch("safari_tabs.verification.subprocess.run")
    @patch("safari_tabs.verification.windows.read")
    def test_independent_mismatch_does_not_report_success(self, read, run):
        read.return_value = self.snapshot()
        run.return_value.stdout = json.dumps([[42], [["Different"]], [["https://example.test"]]])
        with self.assertRaisesRegex(QueryError, "disagree"):
            verify()

    @patch("safari_tabs.verification.subprocess.run")
    @patch("safari_tabs.verification.windows.read")
    def test_session_changes_during_verification(self, read, run):
        read.side_effect = [self.snapshot(), self.snapshot("Changed")]
        run.return_value.stdout = "[]"
        with self.assertRaisesRegex(QueryError, "changed during verification"):
            verify()

    @patch("safari_tabs.verification.subprocess.run")
    @patch("safari_tabs.verification.windows.read")
    def test_independent_query_timeout(self, read, run):
        read.return_value = self.snapshot()
        run.side_effect = subprocess.TimeoutExpired("osascript", 30)
        with self.assertRaisesRegex(QueryError, "verification failed"):
            verify()

    @patch("safari_tabs.cli.verify", return_value={"verified": True})
    def test_verification_command(self, verify_mock):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["verify"]), 0)
        self.assertTrue(json.loads(output.getvalue())["verified"])

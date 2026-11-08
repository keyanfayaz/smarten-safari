"""Exercise the actual JXA script with a fake Application; never contact Safari."""

import json
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(sys.platform == "darwin", "JXA runtime requires macOS")
class WindowScriptTests(unittest.TestCase):
    def run_script(self, samples, running=True):
        script = Path(__file__).resolve().parents[1] / "safari_tabs/adapters/windows.js"
        fixture = f"const samples = {json.dumps(samples)}; const isRunning = {json.dumps(running)};"
        fixture += '''
let cursor = 0;
function fakeApplication(name) {
    return {
        running: function () { return isRunning; },
        windows: function () {
            if (!isRunning) throw new Error("Must not query a stopped application");
            const sample = samples[Math.min(cursor++, samples.length - 1)];
            return sample.map(function (w) {
                return {id: function () {return w.id;}, tabs: {
                    name: function () {return w.titles;},
                    url: function () {return w.urls;}
                }};
            });
        }
    };
}
'''
        isolated = ("function run() {\n" + fixture + "\nreturn (function(Application) {\n"
                    + script.read_text() + "\nreturn run();\n})(fakeApplication);\n}")
        return subprocess.run(
            ["/usr/bin/osascript", "-l", "JavaScript"], input=isolated,
            capture_output=True, text=True, timeout=10,
        )

    def sample(self, title="First", url="https://example.test/1"):
        return [{"id": 42, "titles": [title], "urls": [url]}]

    def test_stable_titles_preserve_special_characters(self):
        result = self.run_script([self.sample('Café\n"title"')])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["tabs"][0]["title"], 'Café\n"title"')

    def test_count_mismatch_recovers_when_session_settles(self):
        mismatch = [{"id": 42, "titles": ["Old", "Extra"], "urls": ["https://example.test"]}]
        result = self.run_script([mismatch, self.sample(), self.sample()])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_same_count_navigation_must_settle(self):
        result = self.run_script([self.sample(), self.sample("Next"), self.sample("Final")])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed during collection", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_stopped_safari_is_not_queried(self):
        result = self.run_script([], running=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"scopes": [], "tabs": []})

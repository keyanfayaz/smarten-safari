import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from build_plugin import build


class PluginTests(unittest.TestCase):
    def test_relocated_package_discovery_and_archive_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "build"
            plugin = build(output)
            manifest = json.loads((plugin / "plugin.json").read_text())
            interface = manifest["extensions"]["com.openai"]["interface"]
            self.assertLessEqual(len(interface["shortDescription"]), 30)
            self.assertEqual(manifest["name"], "safari-tabs")
            config = json.loads((plugin / "mcp.json").read_text())
            self.assertEqual(config["mcpServers"]["safari-tabs"]["type"], "stdio")
            with zipfile.ZipFile(output / "safari-tabs.zip") as archive:
                names = archive.namelist()
                self.assertTrue(all(name.startswith("safari-tabs/") for name in names))
                self.assertIn("safari-tabs/server/safari_tabs/adapters/windows.js", names)
                self.assertFalse(any(".db" in name or "token" in name or "exports/" in name for name in names))
            result = subprocess.run(["/bin/sh", str(plugin / "scripts/launch_mcp.sh")],
                                    input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n",
                                    capture_output=True, text=True, timeout=10, check=True)
            self.assertEqual(len(json.loads(result.stdout)["result"]["tools"]), 4)
            self.assertEqual(result.stderr, "")
            with self.assertRaises(FileExistsError):
                build(output)

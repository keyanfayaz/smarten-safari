"""Package allowlisted code for local plugins or a private Secure MCP Tunnel host."""

import argparse
import json
from pathlib import Path
import shutil
import zipfile


ROOT = Path(__file__).resolve().parent
VERSION = "0.2.0"
SOURCES = (
    "__init__.py", "model.py", "database.py", "verification.py", "mcp.py",
    "adapters/__init__.py", "adapters/groups.py", "adapters/icloud.py",
    "adapters/windows.py", "adapters/windows.js",
)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def build(output):
    """Build a new self-contained marketplace and single-plugin archive; no credentials."""
    output = Path(output).absolute()
    inputs = [(ROOT / "safari_tabs" / name, "server/safari_tabs/" + name) for name in SOURCES]
    inputs += [(ROOT / "plugin/launch_mcp.sh", "scripts/launch_mcp.sh"), (ROOT / "docs/MCP.md", "README.md")]
    if any(path.is_symlink() or not path.is_file() for path, _ in inputs):
        raise ValueError("Missing or symlinked package input")
    output.mkdir(parents=True, exist_ok=False)
    plugin = output / "plugins/safari-tabs"
    for source, relative in inputs:
        target = plugin / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o644)
    interface = {
        "displayName": "My Safari Tabs", "shortDescription": "Read and search Safari tabs",
        "longDescription": "Read Safari tab names by window, saved group, or synced device. "
                           "Read-only; URLs are optional. Saved group/device access depends on macOS permissions.",
        "developerName": "Keyan Fayaz", "category": "Productivity", "capabilities": ["Read"],
        "defaultPrompt": ["What tabs are open in my Safari windows?", "Find my Safari tabs about Python."],
    }
    manifest = {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "safari-tabs", "version": VERSION, "description": interface["longDescription"],
                "author": {"name": "Keyan Fayaz"}, "repository": "https://github.com/keyanfayaz/safari-tabs-lab",
                "extensions": {"com.openai": {"requires_local_executor": True, "interface": interface}}}
    mcp = {"$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json", "mcpServers": {
        "safari-tabs": {"type": "stdio", "command": "/bin/sh",
                        "args": ["${PLUGIN_ROOT}/scripts/launch_mcp.sh"], "cwd": "${PLUGIN_ROOT}"}}}
    write_json(plugin / "plugin.json", manifest)
    write_json(plugin / "mcp.json", mcp)
    write_json(plugin / ".mcp.json", {"mcpServers": mcp["mcpServers"]})
    write_json(plugin / ".codex-plugin/plugin.json", {
        "name": "safari-tabs", "version": VERSION, "description": manifest["description"],
        "mcpServers": "./.mcp.json", "requires_local_executor": True, "interface": interface,
    })
    write_json(output / ".agents/plugins/marketplace.json", {
        "name": "safari-local", "interface": {"displayName": "Safari Local"},
        "plugins": [{"name": "safari-tabs", "source": {"source": "local", "path": "./plugins/safari-tabs"},
                     "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                     "category": "Productivity"}],
    })
    with zipfile.ZipFile(output / "safari-tabs.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(plugin.rglob("*")):
            if path.is_file():
                archive.write(path, "safari-tabs/" + path.relative_to(plugin).as_posix())
    return plugin


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/safari-local")
    args = parser.parse_args()
    print(build(args.output))

"""Resolve paths.yaml into absolute, OS-correct paths for the current machine.

Run standalone to sanity-check path resolution:
    uv run python scripts/load_paths.py
"""

from __future__ import annotations

import pathlib
import platform
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: run `uv add pyyaml`")

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_FILE = REPO_ROOT / "paths.yaml"


def _platform_key() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "mac"
    if system == "windows":
        return "windows"
    return "linux"


def load_vis_layout() -> dict:
    """The `vis_outputs` block: the names a renderer writes INSIDE the vis
    directory. The directory itself is machine-specific and comes from
    BI2M_VIS_DIR, never from here - see paths.yaml's own note."""
    config = yaml.safe_load(CONFIG_FILE.read_text())
    return config["vis_outputs"]


def load_paths() -> dict[str, pathlib.Path]:
    config = yaml.safe_load(CONFIG_FILE.read_text())

    resolved = {name: REPO_ROOT / rel for name, rel in config["paths"].items()}

    key = _platform_key()
    resolved["venv_activate"] = REPO_ROOT / config["venv"][key]["activate"]
    resolved["venv_python"] = REPO_ROOT / config["venv"][key]["python"]

    return resolved


if __name__ == "__main__":
    for name, path in load_paths().items():
        print(f"{name}: {path}")
    print(f"vis_outputs (inside $BI2M_VIS_DIR): {load_vis_layout()}")

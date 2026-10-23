"""Machine-specific settings from the repository's gitignored `.env`.

Paths that only exist on one machine (the IFC corpus, its visual outputs)
are never written into the code. They come from the environment, and
`load_local_env()` fills the environment from `<repo>/.env` first, so a
script run from any shell sees the same values as the viewer's server
(server/api.mjs reads the same file with Node's process.loadEnvFile).
`.env.example` lists the variables.

Variables already set in the environment win over the file, and an empty
value counts as unset, matching Node's behaviour.
"""
import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_local_env(path=ENV_FILE):
    """Copy KEY=VALUE lines from `path` into os.environ without overriding
    anything already set. A missing file is not an error."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and value and not os.environ.get(key):
            os.environ[key] = value


def env_path(name):
    """The variable as a Path, or None when it is unset or empty."""
    load_local_env()
    value = os.environ.get(name)
    return Path(value).expanduser() if value else None

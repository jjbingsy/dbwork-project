"""Centralised path configuration loaded from trust1.env."""

from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent
_ENV_FILE = _PROJECT_ROOT / "trust1.env"


def _load_env(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file (ignores comments and blank lines)."""
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


_env = _load_env(_ENV_FILE)

BASE_DIR = Path(_env.get("BASE_DIR", str(_PROJECT_ROOT)))

DB_PATH = str(BASE_DIR / "unified.db")
GURU_DB_PATH = str(BASE_DIR / "GuruBase.db")
IMAGES_DIR = BASE_DIR / "images"

"""Load GOOGLE_API_KEY from .env, environment, or the paste file. Never logs the secret."""
from __future__ import annotations

import os
from pathlib import Path

_PLACEHOLDERS = {
    "",
    "your-key-here",
    "PASTE_YOUR_GOOGLE_API_KEY_HERE",
    "PASTE_YOUR_GOOGLE_GEMINI_API_KEY_ON_THE_NEXT_LINE_THEN_SAVE",
}


def _parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def _first_non_placeholder_line(path: Path) -> str:
    if not path.exists():
        return ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip().strip('"').strip("'")
        if not line or line.startswith("#"):
            continue
        if line.upper().startswith("GOOGLE_API_KEY="):
            line = line.split("=", 1)[1].strip().strip('"').strip("'")
        if line not in _PLACEHOLDERS:
            return line
    return ""


def load_gemini_credentials(project_root: Path | None = None) -> tuple[str, str]:
    """
    Returns (api_key, model_name).
    Search order: process env, .env, PASTE_GOOGLE_API_KEY_HERE.txt, API_KEY.txt.
    """
    root = project_root or Path.cwd()
    env_file = _parse_dotenv(root / ".env")

    key = (
        os.environ.get("GOOGLE_API_KEY", "").strip()
        or os.environ.get("GEMINI_API_KEY", "").strip()
        or env_file.get("GOOGLE_API_KEY", "").strip()
        or env_file.get("GEMINI_API_KEY", "").strip()
        or _first_non_placeholder_line(root / "PASTE_GOOGLE_API_KEY_HERE.txt")
        or _first_non_placeholder_line(root / "API_KEY.txt")
    )
    if key in _PLACEHOLDERS:
        key = ""

    model = (
        os.environ.get("GEMINI_MODEL", "").strip()
        or env_file.get("GEMINI_MODEL", "").strip()
        or "gemini-3.6-flash"
    )
    if key:
        os.environ["GOOGLE_API_KEY"] = key
        os.environ["GEMINI_MODEL"] = model
    return key, model


def require_gemini_key(project_root: Path | None = None) -> tuple[str, str]:
    key, model = load_gemini_credentials(project_root)
    if not key:
        raise RuntimeError(
            "GOOGLE_API_KEY is missing. Paste it into PASTE_GOOGLE_API_KEY_HERE.txt "
            "(second line) or set it in .env, then re-run. Do not paste the key in chat."
        )
    return key, model

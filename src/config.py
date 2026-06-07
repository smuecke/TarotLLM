from __future__ import annotations

import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_LANGUAGES = {"en", "de"}


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def app_language() -> str:
    configured = os.getenv("APP_LANGUAGE", "en").strip().lower()
    if configured.startswith("de"):
        return "de"
    if configured.startswith("en"):
        return "en"
    return "en"


def deck_name() -> str:
    configured = os.getenv("DECK_NAME", "tarot").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", configured):
        return "tarot"
    return configured

"""
app_settings.py
Small JSON-backed app settings store.
"""

import json
from pathlib import Path


SETTINGS_FILE = Path("sessions") / "ui_settings.json"


def _ensure_parent_dir():
    SETTINGS_FILE.parent.mkdir(exist_ok=True)


def load_settings() -> dict:
    _ensure_parent_dir()
    if not SETTINGS_FILE.exists():
        return {}

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(settings: dict) -> None:
    _ensure_parent_dir()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

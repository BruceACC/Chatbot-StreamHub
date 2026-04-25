"""
session_manager.py
Manages Playwright browser sessions for each Kick.com account.
Sessions are stored as JSON files so they persist across app restarts.
"""

import json
import threading
from pathlib import Path

SESSIONS_DIR = Path("sessions")
ACCOUNTS_FILE = SESSIONS_DIR / "accounts.json"


def _ensure_dirs():
    SESSIONS_DIR.mkdir(exist_ok=True)


def load_accounts() -> list[dict]:
    """Return list of saved accounts: [{name, status}]"""
    _ensure_dirs()
    if ACCOUNTS_FILE.exists():
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_accounts(accounts: list[dict]):
    _ensure_dirs()
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2)


def get_session_path(name: str) -> Path:
    return SESSIONS_DIR / name / "state.json"

def parse_proxy(proxy_str: str) -> dict | None:
    if not proxy_str:
        return None
    proxy_str = proxy_str.strip()
    if proxy_str.startswith("http"):
        return {"server": proxy_str}
    parts = proxy_str.split(":")
    if len(parts) == 2:
        return {"server": f"http://{parts[0]}:{parts[1]}"}
    if len(parts) == 4:
        return {
            "server": f"http://{parts[0]}:{parts[1]}",
            "username": parts[2],
            "password": parts[3]
        }
    return {"server": proxy_str}

def get_proxy(name: str) -> dict | None:
    for acc in load_accounts():
        if acc["name"] == name:
            p = acc.get("proxy")
            return parse_proxy(p) if p else None
    return None

def has_session(name: str) -> bool:
    return get_session_path(name).exists()


def delete_account(name: str):
    """Remove account and its session data."""
    accounts = load_accounts()
    accounts = [a for a in accounts if a["name"] != name]
    _save_accounts(accounts)
    session_path = get_session_path(name)
    if session_path.exists():
        session_path.unlink()
    parent = session_path.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()


def add_account(name: str, proxy: str = None, on_done: callable = None, on_error: callable = None):
    """
    Uses the shared Chromium browser so the user can log in to Kick.com.
    When login is detected (avatar appears), saves the session and closes.
    Runs in a background thread so the GUI isn't blocked.
    """
    def _run():
        try:
            _ensure_dirs()
            session_dir = SESSIONS_DIR / name
            session_dir.mkdir(parents=True, exist_ok=True)
            pw_proxy = parse_proxy(proxy)
            from core.browser_manager import get_shared_browser_manager

            browser_manager = get_shared_browser_manager()
            logged_in = browser_manager.login_account(name, pw_proxy)

            if logged_in:
                # Update accounts list
                accounts = load_accounts()
                names = [a["name"] for a in accounts]
                if name not in names:
                    accounts.append({"name": name, "status": "idle", "proxy": proxy})
                    _save_accounts(accounts)
                else:
                    # Update proxy if account exists
                    for a in accounts:
                        if a["name"] == name:
                            a["proxy"] = proxy
                    _save_accounts(accounts)
                if on_done:
                    on_done(name)
            else:
                if on_error:
                    on_error(name, "Login window closed without completing login.")

        except Exception as e:
            if on_error:
                on_error(name, str(e))

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t

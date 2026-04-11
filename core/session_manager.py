"""
session_manager.py
Manages Playwright browser sessions for each Kick.com account.
Sessions are stored as JSON files so they persist across app restarts.
"""

import json
import os
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright

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
    Opens a headed Chromium browser so the user can log in to Kick.com.
    When login is detected (avatar appears), saves the session and closes.
    Runs in a background thread so the GUI isn't blocked.
    """
    def _run():
        try:
            _ensure_dirs()
            session_dir = SESSIONS_DIR / name
            session_dir.mkdir(parents=True, exist_ok=True)
            state_path = get_session_path(name)

            pw_proxy = parse_proxy(proxy)

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    channel="chrome",  # Use the system's real Google Chrome!
                    headless=False,
                    args=[
                        "--start-maximized",
                        "--disable-blink-features=AutomationControlled"
                    ],
                    ignore_default_args=["--enable-automation"],
                    proxy=pw_proxy if pw_proxy else None
                )
                
                # Setup context without a hardcoded user-agent (real Chrome handles it)
                context = browser.new_context(
                    storage_state=str(state_path) if state_path.exists() else None,
                    viewport=None,
                )
                
                # Hide webdriver property via initialization script
                context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                page = context.new_page()

                def _has_email_password_form() -> bool:
                    try:
                        has_email = page.locator('input[type="email"], input[name*="email" i]').count() > 0
                        has_password = page.locator('input[type="password"], input[name*="password" i]').count() > 0
                        return has_email and has_password
                    except Exception:
                        return False

                def _try_open_email_login() -> None:
                    # Kick can render different auth flows depending on region/account.
                    # We try common routes and then try sign-in controls from home.
                    candidate_urls = [
                        "https://kick.com/login",
                        "https://kick.com/auth/login",
                        "https://kick.com/",
                    ]

                    for target in candidate_urls:
                        try:
                            page.goto(target, wait_until="domcontentloaded", timeout=30_000)
                        except Exception:
                            continue
                        if _has_email_password_form():
                            return

                    sign_in_labels = ["Log in", "Sign in", "Iniciar sesion", "Iniciar sesion"]
                    for label in sign_in_labels:
                        try:
                            btn = page.get_by_role("button", name=label)
                            if btn.count() > 0:
                                btn.first.click(timeout=5_000)
                                page.wait_for_timeout(800)
                                if _has_email_password_form():
                                    return
                        except Exception:
                            pass

                        try:
                            link = page.get_by_role("link", name=label)
                            if link.count() > 0:
                                link.first.click(timeout=5_000)
                                page.wait_for_timeout(800)
                                if _has_email_password_form():
                                    return
                        except Exception:
                            pass

                _try_open_email_login()

                # Poll until the user is logged in (avatar element appears)
                # or until they close the window
                logged_in = False
                page.set_default_timeout(300_000)  # 5 minute max

                try:
                    # Wait for avatar/profile menu or URL change indicating login
                    # We also accept wait_for_function that checks if auth cookie exists
                    page.wait_for_function(
                        """
                        () => {
                            // Check if avatar is present
                            const avatar = document.querySelector('button[aria-label="Open user menu"], [data-testid="user-menu-button"], img[alt*="avatar"], .user-profile-picture, [class*="UserMenu"], [class*="user-menu"]');
                            // Or check if there's a specific button like "Obtén KICKs"
                            const kickBtn = Array.from(document.querySelectorAll('button')).find(el => el.textContent.includes("Obtén KICKs"));

                            // Treat session as logged in only when clear user UI is present.
                            return (avatar !== null || kickBtn !== undefined);
                        }
                        """,
                        timeout=300_000,
                    )
                    logged_in = True
                except Exception:
                    # Fallback check just in case it closed manually but user was logged in
                    pass

                if logged_in:
                    context.storage_state(path=str(state_path))

                context.close()
                browser.close()

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
